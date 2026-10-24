"""Controller-owned research transitions over the canonical ledger.

Only the built-in finite cache environment executes here. Model-authored code is
never evaluated. Imported statements and human judgments cannot certify tests.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import UUID, uuid5

from doxa.core.models import (
    Agent,
    Annotation,
    Challenge,
    Checkpoint,
    Claim,
    Decision,
    Event,
    EventType,
    Evidence,
    Experiment,
    Memory,
    ModelCall,
    Provenance,
    Record,
    ReflectionDecision,
    Role,
    RunState,
    ScopedRecord,
    Trajectory,
    TrajectoryState,
    Verification,
)
from doxa.core.research_commands import (
    AdjudicateCommand,
    AnnotateCommand,
    ChallengeCommand,
    CheckpointCommand,
    CheckpointManifest,
    ClaimCommand,
    CloseBranchCommand,
    Command,
    DecisionCommand,
    EnvironmentCommand,
    EvaluateCommand,
    EvidenceCommand,
    ForkCommand,
    LifecycleCommand,
    ReflectCommand,
    RespondCommand,
    VerifyCommand,
)
from doxa.environments.cache_policy import (
    CacheEnvironment,
    CacheFixture,
    Candidate,
    fixture_hash,
)
from doxa.environments.cache_verifier import CacheIndependentVerifier
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.database import connection
from doxa.storage.ledger import LedgerConflict
from doxa.systems.research import Signals, branch_events, commitments, impact, reflection_rule

if TYPE_CHECKING:
    from doxa.core.controller import Controller


class ResearchRuntime:
    def __init__(self, controller: "Controller", run_id: UUID, branch_id: UUID):
        self.controller = controller
        self.ledger = controller.ledger
        self.run = controller.inspect(run_id).run
        self.events = self.ledger.events(run_id)
        self.branch = branch_id
        self.original_branch = branch_id
        self.visible = branch_events(self.events, branch_id)
        self.experiment = cast(Experiment, self.ledger.get(self.run.experiment_id))
        self.store = ArtifactStore(controller.settings.data_dir / "artifacts")
        if (self.experiment.task_id, self.experiment.task_version) != ("cache-policy", "1"):
            raise ValueError("Research executor supports only cache-policy v1")

    def scope(self, provenance: Provenance = Provenance.SYSTEM_INFERENCE) -> dict[str, Any]:
        return dict(
            experiment_id=self.run.experiment_id,
            run_id=self.run.id,
            trajectory_id=self.branch,
            provenance=provenance,
        )

    def identity(self, suffix: str) -> UUID:
        return uuid5(self.namespace, suffix)

    def participant(self, identity: UUID) -> Agent:
        for agent in self.experiment.agents:
            if agent.id == identity and agent.enabled:
                return agent
        raise ValueError("Unknown or disabled participant")

    def get(self, identity: UUID, kind: type[Any]) -> Any:
        value = self.ledger.get(identity)
        if not isinstance(value, kind) or not isinstance(value, ScopedRecord):
            raise ValueError("Wrong record type")
        if value.run_id != self.run.id or identity not in {
            r.id for e in self.visible for r in e.payload
        }:
            raise ValueError("Record is not visible on this branch")
        return value

    def event(
        self,
        event_type: EventType,
        records: tuple[Record, ...],
        actor: Agent | None = None,
        provenance: Provenance = Provenance.SYSTEM_INFERENCE,
    ) -> Event:
        return Event(
            **self.scope(provenance),
            id=self.identity("event"),
            sequence=1,
            type=event_type,
            payload=records,
            idempotency_key=self.key,
            parent_event_ids=(self.visible[-1].id,),
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else Role.ORCHESTRATOR,
            model=actor.model if actor else None,
            command_digest=self.digest,
            expected_cursor=self.visible[-1].id,
            expected_trajectory_id=self.original_branch,
        )

    def evidence(self, source: str, data: dict[str, Any], name: str = "evidence") -> Evidence:
        raw = json.dumps(data, sort_keys=True).encode()
        return Evidence(
            **self.scope(Provenance.DETERMINISTIC_VERIFIER),
            id=self.identity(name),
            description=json.dumps(data, sort_keys=True),
            source=source,
            artifacts=(self.store.put(raw, "application/json"),),
        )

    def apply(self, command: Command) -> Event:
        self.namespace = uuid5(self.branch, "research:" + command.idempotency_key)
        self.key = f"research:{self.run.id}:{self.branch}:{command.idempotency_key}"
        self.digest = hashlib.sha256(command.model_dump_json().encode()).hexdigest()
        prior = next((e for e in self.events if e.idempotency_key == self.key), None)
        if prior:
            if prior.command_digest != self.digest:
                raise LedgerConflict("Research command idempotency conflict")
            if any(
                isinstance(r, Evidence) and r.source == "research-command-rejected"
                for r in prior.payload
            ):
                raise ValueError("Previously rejected research command")
            return prior
        try:
            event = self.propose(command)
            if isinstance(command, ForkCommand):
                restored = event.model_copy(
                    update={
                        "id": self.identity("restore-event"),
                        "type": EventType.CHECKPOINT_RESTORED,
                        "payload": (),
                        "parent_event_ids": (event.id,),
                        "idempotency_key": self.key + ":restore",
                    }
                )
                return self.ledger.append_batch((event, restored))[0]
            return self.ledger.append(event)
        except (ValueError, KeyError, OSError) as exc:
            # Do not persist submitted secrets or arbitrary exception text. Failed commands
            # are inspectable, but do not claim to have changed environment or commitments.
            failure = Evidence(
                **self.scope(),
                id=self.identity("failure"),
                source="research-command-rejected",
                description=f"{command.operation} rejected: {type(exc).__name__}",
            )
            self.ledger.append(self.event(EventType.DECISION_RECORDED, (failure,)))
            raise

    def state(self) -> CacheEnvironment:
        states = [
            r
            for e in self.visible
            for r in e.payload
            if isinstance(r, Evidence) and r.source == "cache-state-v1"
        ]
        if not states:
            raise ValueError("Initialize the supported environment first")
        return CacheEnvironment.restore(self.store.get(states[-1].artifacts[0]))

    def state_record(self, env: CacheEnvironment) -> Evidence:
        return Evidence(
            **self.scope(Provenance.TOOL_OBSERVATION),
            id=self.identity("state"),
            source="cache-state-v1",
            description="Finite cache environment snapshot",
            artifacts=(self.store.put(env.snapshot(), "application/json"),),
        )

    def tool_guard(self) -> None:
        if (
            sum(
                e.type in {EventType.VERIFICATION_RECORDED, EventType.ACTION_EXECUTED}
                for e in self.events
            )
            >= self.experiment.budget.max_tool_calls
        ):
            raise ValueError("Tool budget exhausted")

    def propose(self, command: Command) -> Event:
        if isinstance(command, LifecycleCommand):
            state = RunState(
                **self.scope(),
                id=self.identity("run-state"),
                status=command.status,
                reason_code=command.reason_code,
            )
            event_type = {
                "running": EventType.RUN_STARTED,
                "completed": EventType.RUN_CLOSED,
                "cancelled": EventType.RUN_CANCELLED,
            }[command.status]
            return self.event(event_type, (state,))
        closed = any(
            isinstance(r, TrajectoryState)
            for e in self.visible
            if e.trajectory_id == self.branch
            for r in e.payload
        )
        if closed and not isinstance(command, (AnnotateCommand, EvaluateCommand)):
            raise ValueError("Branch is completed or abandoned")
        if self.run.status != "running" and not isinstance(
            command, (AnnotateCommand, EvaluateCommand)
        ):
            raise ValueError("Research mutations require a running run")
        replay = any(
            isinstance(r, Evidence)
            and r.source == "verified-cache-restore-v1"
            and json.loads(r.description).get("continuation") == "historical_replay"
            for e in self.visible
            if e.trajectory_id == self.branch
            for r in e.payload
        )
        if replay and not isinstance(command, (AnnotateCommand, EvaluateCommand)):
            raise ValueError("Historical replay is read-only; fork a fresh continuation")
        if isinstance(command, CloseBranchCommand):
            branch_state = TrajectoryState(
                **self.scope(),
                id=self.identity("branch-state"),
                status=command.status,
                reason_code=command.reason_code,
            )
            return self.event(EventType.TRAJECTORY_COMPLETED, (branch_state,))
        if isinstance(command, ClaimCommand):
            return self.claim(command)
        if isinstance(command, EvidenceCommand):
            for artifact in command.artifacts:
                self.store.get(artifact)
            record = Evidence(
                **self.scope(Provenance.IMPORTED_SOURCE),
                id=self.identity("evidence"),
                description=command.description,
                source=command.source,
                artifacts=command.artifacts,
            )
            return self.event(
                EventType.EVIDENCE_ATTACHED, (record,), provenance=Provenance.IMPORTED_SOURCE
            )
        if isinstance(command, DecisionCommand):
            self.get(command.claim_id, Claim)
            for identity in command.dependency_ids:
                self.get(identity, Claim)
            decision = Decision(
                **self.scope(),
                id=self.identity("decision"),
                claim_id=command.claim_id,
                outcome="retain",
                reason=command.reason,
                dependency_ids=command.dependency_ids,
                policy_version="research-v1",
            )
            return self.event(EventType.DECISION_RECORDED, (decision,))
        if isinstance(command, EnvironmentCommand):
            return self.environment(command)
        if isinstance(command, VerifyCommand):
            self.tool_guard()
            claim: Claim = self.get(command.claim_id, Claim)
            candidate = Candidate.model_validate_json(claim.proposition)
            if self.state().state.policy != candidate:
                raise ValueError("Task verification requires the deployed finite policy")
            results = CacheIndependentVerifier.check(candidate)
            evidence = self.evidence(
                "cache-oracle-v2",
                {
                    "checks": results,
                    "candidate": candidate.model_dump(mode="json"),
                    "subject_id": str(claim.id),
                },
            )
            validation = Verification(
                **self.scope(Provenance.DETERMINISTIC_VERIFIER),
                id=self.identity("verification"),
                subject_id=claim.id,
                evaluator_id="cache-oracle",
                evaluator_version="2",
                verdict="valid" if all(results.values()) else "invalid",
                evidence_ids=(evidence.id,),
            )
            return self.event(
                EventType.VERIFICATION_RECORDED,
                (evidence, validation),
                provenance=Provenance.DETERMINISTIC_VERIFIER,
            )
        if isinstance(command, CheckpointCommand):
            return self.checkpoint()
        if isinstance(command, ForkCommand):
            return self.fork(command)
        if isinstance(command, ChallengeCommand):
            self.get(command.claim_id, Claim)
            if command.target_decision_id:
                target_decision: Decision = self.get(command.target_decision_id, Decision)
                if target_decision.claim_id != command.claim_id:
                    raise ValueError("Decision and claim version targets disagree")
            actor = self.participant(command.critic_id)
            if any(case not in CacheFixture().cases for case in command.alleged_cases):
                raise ValueError("Unsupported verification case")
            challenge = Challenge(
                **self.scope(Provenance.IMPORTED_SOURCE),
                id=self.identity("challenge"),
                claim_id=command.claim_id,
                objection=command.objection,
                critic_id=command.critic_id,
                alleged_cases=command.alleged_cases,
                confidence=command.confidence,
                target_decision_id=command.target_decision_id,
                proposed_revision=command.proposed_revision.model_dump_json()
                if command.proposed_revision
                else None,
            )
            return self.event(
                EventType.CHALLENGE_SUBMITTED, (challenge,), actor, Provenance.IMPORTED_SOURCE
            )
        if isinstance(command, AdjudicateCommand):
            return self.adjudicate(command)
        if isinstance(command, RespondCommand):
            return self.respond(command)
        if isinstance(command, ReflectCommand):
            return self.reflect(command)
        if isinstance(command, EvaluateCommand):
            return self.evaluate(command)
        if isinstance(command, AnnotateCommand):
            return self.annotate(command)
        raise ValueError("Unsupported research command")

    def claim(self, command: ClaimCommand) -> Event:
        actor = self.participant(command.author_id)
        previous: Claim | None = None
        if command.revises_id:
            previous = self.get(command.revises_id, Claim)
            if previous.id not in {r.id for r in commitments(self.events, self.branch)}:
                raise ValueError("Revision targets a stale version")
            if previous.author_id and previous.author_id != actor.id:
                raise ValueError("Another agent's position must remain distinct")
        if command.status == "supported":
            # Evidence attachment alone does not certify a proposition. A matching
            # independently verified candidate is required, including for changed text.
            valid = [
                r
                for e in self.visible
                for r in e.payload
                if isinstance(r, Verification)
                and r.verdict == "valid"
                and r.provenance in {Provenance.DETERMINISTIC_VERIFIER, Provenance.TASK_ANSWER_KEY}
            ]
            if not any(
                isinstance(target := self.ledger.get(v.subject_id), Claim)
                and target.proposition == command.proposition
                and set(v.evidence_ids).issubset(command.evidence_ids)
                for v in valid
            ):
                raise ValueError("Supported status requires independent proposition evidence")
        for identity in (
            command.evidence_ids
            + command.contradicting_evidence_ids
            + command.rejected_evidence_ids
        ):
            self.get(identity, Evidence)
        for identity in command.dependency_ids + command.inferred_dependency_ids:
            self.get(identity, Claim)
        affected = impact(self.events, self.branch, previous.id) if previous else ()
        record = Claim(
            **self.scope(Provenance.IMPORTED_SOURCE),
            id=self.identity("claim"),
            commitment_id=(previous.commitment_id or previous.id)
            if previous
            else self.identity("claim"),
            author_id=actor.id,
            proposition=command.proposition,
            status=command.status,
            revises_id=command.revises_id,
            evidence_ids=command.evidence_ids,
            dependency_ids=command.dependency_ids,
            inferred_dependency_ids=command.inferred_dependency_ids,
            contradicting_evidence_ids=command.contradicting_evidence_ids,
            rejected_evidence_ids=command.rejected_evidence_ids,
            reconsider_ids=affected,
        )
        return self.event(
            EventType.CLAIM_REVISED if previous else EventType.CLAIM_PROPOSED,
            (record,),
            actor,
            Provenance.IMPORTED_SOURCE,
        )

    def environment(self, command: EnvironmentCommand) -> Event:
        self.tool_guard()
        if command.action == "initialize":
            if any(
                isinstance(r, Evidence) and r.source == "cache-state-v1"
                for e in self.visible
                for r in e.payload
            ):
                raise ValueError("Environment already initialized; fork to restore")
            if command.candidate is None:
                raise ValueError("Initialization requires a finite policy")
            env = CacheEnvironment(command.candidate)
        else:
            env = self.state()
            if command.action == "read":
                env.read(command.key)
            elif command.action == "update":
                if command.value is None:
                    raise ValueError("Update requires an integer value")
                env.update(command.key, command.value)
            elif command.action == "delete":
                env.delete(command.key)
            elif command.action == "select_policy":
                if command.candidate is None:
                    raise ValueError("Policy selection requires a finite candidate")
                env.state = env.state.model_copy(update={"policy": command.candidate})
        result = self.evidence("cache-action-v1", command.model_dump(mode="json"), "action")
        return self.event(EventType.ACTION_EXECUTED, (self.state_record(env), result))

    def checkpoint(self) -> Event:
        env = self.state()
        state = self.store.put(env.snapshot(), "application/json")
        fixture = self.store.put(CacheFixture().model_dump_json().encode(), "application/json")
        models = tuple(a.model for a in self.experiment.agents if a.model)
        configs = self.store.put(json.dumps([m.model_dump(mode="json") for m in models]).encode())
        policy = self.store.put(self.experiment.budget.model_dump_json().encode())
        from doxa.systems.memory import latest_memories

        memories = tuple(
            m.id for m in latest_memories(self.ledger, self.run.id) if m.trust == "approved"
        )
        observations = tuple(
            a
            for e in self.visible
            for r in e.payload
            if isinstance(r, Evidence)
            for a in r.artifacts
        )
        manifest = CheckpointManifest(
            workspace=state,
            fixture=fixture,
            event_cursor=self.visible[-1].id,
            memory_ids=memories,
            model_config_artifact=configs,
            policy_artifact=policy,
            observations=observations,
        )
        checkpoint = Checkpoint(
            **self.scope(),
            id=self.identity("checkpoint"),
            task_version="1",
            fixture_hash=fixture_hash(CacheFixture()),
            workspace=state,
            environment_config=fixture,
            event_cursor=self.visible[-1].id,
            memory_ids=memories,
            model_configs=models,
            observations=observations,
            manifest=self.store.put(manifest.model_dump_json().encode()),
        )
        return self.event(EventType.CHECKPOINT_CREATED, (checkpoint,))

    def fork(self, command: ForkCommand) -> Event:
        checkpoint: Checkpoint = self.get(command.checkpoint_id, Checkpoint)
        restored = self.restore_checkpoint(checkpoint)
        assert checkpoint.manifest is not None
        manifest = CheckpointManifest.model_validate_json(self.store.get(checkpoint.manifest))
        parent = self.branch
        child = self.identity("child")
        trajectory = Trajectory(
            id=child,
            run_id=self.run.id,
            parent_id=parent,
            checkpoint_id=checkpoint.id,
            intervention=command.intervention,
        )
        self.branch = child
        evidence = self.evidence(
            "verified-cache-restore-v1",
            {
                "checkpoint_id": str(checkpoint.id),
                "expected_sha256": manifest.workspace.sha256,
                "actual_sha256": hashlib.sha256(restored.snapshot()).hexdigest(),
                "equal": True,
                "continuation": command.continuation,
                "external_effects_restored": False,
            },
            "restore",
        )
        event = self.event(
            EventType.BRANCH_CREATED, (trajectory, self.state_record(restored), evidence)
        )
        self.branch = parent
        return event

    def restore_checkpoint(self, checkpoint: Checkpoint) -> CacheEnvironment:
        if checkpoint.trajectory_id != self.branch or checkpoint.manifest is None:
            raise ValueError("Fork requires a manifested checkpoint on its parent")
        manifest = CheckpointManifest.model_validate_json(self.store.get(checkpoint.manifest))
        if (
            manifest.workspace,
            manifest.fixture,
            manifest.event_cursor,
            manifest.memory_ids,
            manifest.observations,
        ) != (
            checkpoint.workspace,
            checkpoint.environment_config,
            checkpoint.event_cursor,
            checkpoint.memory_ids,
            checkpoint.observations,
        ):
            raise ValueError("Manifest differs from pinned checkpoint")
        for artifact in (
            *manifest.observations,
            manifest.model_config_artifact,
            manifest.policy_artifact,
        ):
            self.store.get(artifact)
        models = json.loads(self.store.get(manifest.model_config_artifact))
        if models != [m.model_dump(mode="json") for m in checkpoint.model_configs]:
            raise ValueError("Model configuration mismatch")
        if json.loads(self.store.get(manifest.policy_artifact)) != (
            self.experiment.budget.model_dump(mode="json")
        ):
            raise ValueError("Policy configuration mismatch")
        fixture = CacheFixture.model_validate_json(self.store.get(manifest.fixture))
        if fixture_hash(fixture) != checkpoint.fixture_hash:
            raise ValueError("Fixture hash mismatch")
        raw = self.store.get(manifest.workspace)
        restored = CacheEnvironment.restore(raw)
        if restored.snapshot() != raw:
            raise ValueError("Incomplete restore")
        return restored

    def adjudicate(self, command: AdjudicateCommand) -> Event:
        self.tool_guard()
        challenge: Challenge = self.get(command.challenge_id, Challenge)
        target: Claim = self.get(challenge.claim_id, Claim)
        candidate = Candidate.model_validate_json(target.proposition)
        checks = CacheIndependentVerifier.check(candidate)
        requested = challenge.alleged_cases
        truth = [not checks[c] for c in requested]
        verdict: Literal["valid", "invalid", "partially_valid", "unverified"]
        verdict = (
            "unverified"
            if not truth
            else "valid"
            if all(truth)
            else ("partially_valid" if any(truth) else "invalid")
        )
        alternative = (
            Candidate.model_validate_json(challenge.proposed_revision)
            if (challenge.proposed_revision)
            else None
        )
        evidence = self.evidence(
            "cache-challenge-oracle-v1",
            {
                "target_checks": checks,
                "alleged_cases": requested,
                "alternative_checks": CacheIndependentVerifier.check(alternative)
                if alternative
                else None,
                "alternative_candidate": alternative.model_dump(mode="json")
                if alternative
                else None,
                "target_claim_id": str(target.id),
                "challenge_id": str(challenge.id),
                "objection_verdict": verdict,
            },
        )
        validation = Verification(
            **self.scope(Provenance.DETERMINISTIC_VERIFIER),
            id=self.identity("verification"),
            subject_id=challenge.id,
            evaluator_id="cache-challenge-oracle",
            evaluator_version="1",
            verdict=verdict,
            evidence_ids=(evidence.id,),
        )
        return self.event(
            EventType.VERIFICATION_RECORDED,
            (evidence, validation),
            provenance=Provenance.DETERMINISTIC_VERIFIER,
        )

    def respond(self, command: RespondCommand) -> Event:
        actor = self.participant(command.author_id)
        challenge: Challenge = self.get(command.challenge_id, Challenge)
        target: Claim = self.get(challenge.claim_id, Claim)
        if target.author_id and actor.id != target.author_id:
            raise ValueError("Only target author can change this commitment")
        verdicts = [
            r
            for e in self.visible
            for r in e.payload
            if isinstance(r, Verification)
            and r.subject_id == challenge.id
            and r.evaluator_id == "cache-challenge-oracle"
            and r.provenance == Provenance.DETERMINISTIC_VERIFIER
        ]
        verdict = verdicts[-1] if verdicts else None
        response = challenge.model_copy(
            update={
                "id": self.identity("response"),
                "response": command.response,
                "responds_to_id": challenge.id,
            }
        )
        records: tuple[Record, ...] = (response,)
        if command.response == "accept":
            if not verdict or verdict.verdict != "valid" or not challenge.proposed_revision:
                raise ValueError("Accepting revision requires a valid objection and candidate")
            candidate = Candidate.model_validate_json(challenge.proposed_revision)
            proof: Evidence = self.get(verdict.evidence_ids[0], Evidence)
            result = json.loads(self.store.get(proof.artifacts[0]))
            if (
                proof.source != "cache-challenge-oracle-v1"
                or result.get("alternative_candidate") != candidate.model_dump(mode="json")
                or not result.get("alternative_checks")
                or not all(result["alternative_checks"].values())
            ):
                raise ValueError("Proposed correction lacks passing independent test evidence")
            if target.id not in {c.id for c in commitments(self.events, self.branch)}:
                raise ValueError("Challenge targeted an outdated commitment")
            revision = target.model_copy(
                update={
                    **self.scope(),
                    "id": self.identity("revision"),
                    "commitment_id": target.commitment_id or target.id,
                    "author_id": actor.id,
                    "revises_id": target.id,
                    "proposition": candidate.model_dump_json(),
                    "status": "supported",
                    "evidence_ids": verdict.evidence_ids,
                    "reconsider_ids": impact(self.events, self.branch, target.id),
                }
            )
            records += (revision,)
        elif command.response == "qualify":
            if not verdict or verdict.verdict != "partially_valid":
                raise ValueError("Qualification requires partial independent evidence")
            if target.id not in {c.id for c in commitments(self.events, self.branch)}:
                raise ValueError("Cannot qualify an outdated commitment")
            records += (
                target.model_copy(
                    update={
                        **self.scope(),
                        "id": self.identity("revision"),
                        "revises_id": target.id,
                        "status": "qualified",
                        "commitment_id": target.commitment_id or target.id,
                        "evidence_ids": target.evidence_ids + verdict.evidence_ids,
                    }
                ),
            )
        return self.event(EventType.CHALLENGE_RESPONDED, records, actor)

    def reflect(self, command: ReflectCommand) -> Event:
        trigger = next((e for e in self.visible if e.id == command.trigger_event_id), None)
        if trigger is None:
            raise ValueError("Trigger must be visible on this branch")
        prior = tuple(
            r
            for e in self.visible
            if e.trajectory_id == self.branch
            for r in e.payload
            if isinstance(r, ReflectionDecision) and r.policy_version == "adaptive-v1"
        )
        verifications = [
            r
            for e in self.visible
            for r in e.payload
            if isinstance(r, Verification) and r.evaluator_id == "cache-oracle"
        ]
        selected = [r for r in trigger.payload if isinstance(r, Verification)]
        latest = selected[-1] if selected else None
        with connection(self.ledger.path) as db:
            rows = db.execute(
                "SELECT run_id,COALESCE(billed_microusd,reserved_microusd) FROM reservations"
            ).fetchall()
        run_remaining = float(self.experiment.budget.run_cap_usd) - sum(
            row[1] / 1_000_000 for row in rows if row[0] == str(self.run.id)
        )
        global_remaining = 75 - sum(row[1] / 1_000_000 for row in rows)
        calls = [r for e in self.events for r in e.payload if isinstance(r, ModelCall)]
        tools = sum(
            e.type in {EventType.ACTION_EXECUTED, EventType.VERIFICATION_RECORDED}
            for e in self.events
        )
        elapsed = max(0.0, (datetime.now(UTC) - self.events[0].timestamp).total_seconds())
        budget = {
            "model_calls_remaining": self.experiment.budget.max_model_calls - len(calls),
            "tool_calls_remaining": self.experiment.budget.max_tool_calls - tools,
            "run_usd_remaining": run_remaining,
            "global_usd_remaining": global_remaining,
            "seconds_remaining": self.experiment.budget.timeout_seconds - elapsed,
        }
        is_task = latest is not None and latest.evaluator_id == "cache-oracle"
        is_critic = latest is not None and latest.evaluator_id == "cache-challenge-oracle"
        previous_results = [v.verdict for v in verifications]
        checkpoint_available = False
        for record in (r for e in self.visible for r in e.payload if isinstance(r, Checkpoint)):
            try:
                self.restore_checkpoint(record)
                checkpoint_available = True
            except (ValueError, OSError):
                continue
        signals = Signals(
            signal=str(trigger.id),
            exhausted=any(v <= 0 for v in budget.values()),
            success=is_task and latest is not None and latest.verdict == "valid",
            failed=is_task and latest is not None and latest.verdict == "invalid",
            regression=is_task
            and latest is not None
            and latest.verdict == "invalid"
            and "valid" in previous_results[:-1],
            checkpoint=checkpoint_available,
            validated_criticism=is_critic and latest is not None and latest.verdict == "valid",
            unsupported_criticism=is_critic and latest is not None and latest.verdict != "valid",
            contradiction=any(
                isinstance(r, Claim) and r.contradicting_evidence_ids for r in trigger.payload
            ),
            uncertainty=is_task and latest is not None and latest.verdict == "unverified",
            verified_memory=any(
                isinstance(r, Memory) and r.trust == "approved" for r in trigger.payload
            ),
            repeated_failures=len(previous_results)
            if previous_results and all(v == "invalid" for v in previous_results[-3:])
            else 0,
        )
        action, rule = reflection_rule(
            signals, prior, self.experiment.budget.max_reflections_per_branch
        )
        decision = ReflectionDecision(
            **self.scope(),
            id=self.identity("reflection"),
            action=action,
            trigger_event_id=trigger.id,
            reason_code=rule,
            policy_version="adaptive-v1",
            signal=str(trigger.id),
            budget_before=budget,
            budget_after=budget,
            skipped=action in {"stop", "continue"},
            resulting_state="halted" if action == "stop" else action,
            considered_actions=(
                "continue",
                "verify",
                "retrieve",
                "critique",
                "reflect",
                "rollback",
                "escalate",
                "stop",
            ),
        )
        return self.event(
            EventType.REFLECTION_SKIPPED if decision.skipped else EventType.REFLECTION_TRIGGERED,
            (decision,),
        )

    def evaluate(self, command: EvaluateCommand) -> Event:
        from doxa.core.research_evaluation import evaluate_branch

        evaluation = evaluate_branch(
            self.controller,
            self.run.id,
            self.branch,
            self.identity("evaluation"),
            command.baseline_run_id,
        )
        return self.event(
            EventType.EVALUATION_RECORDED,
            (evaluation,),
            provenance=Provenance.DETERMINISTIC_VERIFIER,
        )

    def annotate(self, command: AnnotateCommand) -> Event:
        dimensions = {
            "overall",
            "evidence",
            "consistency",
            "criticism",
            "revision",
            "memory",
            "recovery",
            "efficiency",
        }
        if not set(command.dimensions).issubset(dimensions) or any(
            type(v) is not int or not 1 <= v <= 5 for v in command.dimensions.values()
        ):
            raise ValueError("Rubric v1 uses named dimensions with ratings 1 through 5")
        if command.preference is not None:
            other = (
                self.ledger.get(command.other_trajectory_id)
                if (command.other_trajectory_id)
                else None
            )
            if not isinstance(other, Trajectory) or other.id == self.branch:
                raise ValueError("Preference requires two actual distinct trajectories")
        elif command.other_trajectory_id:
            raise ValueError("Pairwise target requires a preference")
        annotation = Annotation(
            **self.scope(Provenance.HUMAN_ANNOTATION),
            id=self.identity("annotation"),
            reviewer_id=command.reviewer_id,
            rubric_version=command.rubric_version,
            subject_id=self.branch,
            dimensions=command.dimensions,
            notes=command.notes,
            preferred_over_id=command.other_trajectory_id,
            preference=command.preference,
        )
        return self.event(
            EventType.HUMAN_ANNOTATION_ADDED, (annotation,), provenance=Provenance.HUMAN_ANNOTATION
        )
