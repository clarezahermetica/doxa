"""Narrow finite-policy experiment runtime; never executes generated source code."""

import asyncio
import hashlib
import time
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from pydantic import Field

from doxa.core.models import (
    Agent,
    Challenge,
    Checkpoint,
    Claim,
    Contract,
    CouncilMessage,
    Decision,
    Evaluation,
    Event,
    EventType,
    Evidence,
    Experiment,
    ModelCall,
    ProtocolMode,
    Provenance,
    Record,
    ReflectionDecision,
    Role,
    RunState,
    Trajectory,
    Usage,
    Verification,
)
from doxa.core.profiles import ModelProfile
from doxa.core.secrets import local_env, safe_text
from doxa.environments.cache_policy import (
    CacheEnvironment,
    CacheFixture,
    Candidate,
    fixture_hash,
    verify,
)
from doxa.providers.contracts import ModelMessage, ModelRequest, ModelResponse
from doxa.providers.runpod import RunPodProvider
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.budget import BudgetStore
from doxa.storage.configurations import ConfigurationStore
from doxa.storage.ledger import LedgerConflict

if TYPE_CHECKING:
    from doxa.core.controller import Controller, RunBundle


class ExecuteTask(Contract):
    fixture: CacheFixture = Field(default_factory=CacheFixture)
    synthetic_answers: dict[str, Candidate] = Field(default_factory=dict)
    authorize_paid: bool = False
    upper_bound_usd_per_attempt: Decimal | None = Field(default=None, gt=0, le=25)


class Runtime:
    def __init__(self, controller: "Controller", run_id: UUID):
        self.controller = controller
        self.ledger = controller.ledger
        self.bundle = controller.inspect(run_id)
        self.run = self.bundle.run
        experiment = self.ledger.get(self.run.experiment_id)
        assert isinstance(experiment, Experiment)
        self.experiment: Experiment = experiment
        self.branch = self.bundle.events[-1].trajectory_id
        self.store = ArtifactStore(controller.settings.data_dir / "artifacts")
        self.calls = BudgetStore(controller.settings.database_path)
        self.started = time.monotonic()
        self.command: ExecuteTask

    def identity(self, name: str) -> UUID:
        return uuid5(self.run.id, name)

    def scope(self, provenance: Provenance = Provenance.SYSTEM_INFERENCE) -> dict[str, object]:
        return dict(
            experiment_id=self.experiment.id,
            run_id=self.run.id,
            trajectory_id=self.branch,
            provenance=provenance,
        )

    def emit(
        self,
        key: str,
        event_type: EventType,
        records: tuple[Record, ...] = (),
        actor: Agent | None = None,
        provenance: Provenance = Provenance.SYSTEM_INFERENCE,
    ) -> Event:
        previous = self.ledger.events(self.run.id)[-1]
        return self.ledger.append(
            Event(
                experiment_id=self.experiment.id,
                run_id=self.run.id,
                trajectory_id=self.branch,
                sequence=1,
                type=event_type,
                payload=records,
                idempotency_key=f"{self.run.id}:{key}",
                parent_event_ids=(previous.id,),
                actor_id=actor.id if actor else None,
                actor_role=actor.role if actor else Role.ORCHESTRATOR,
                provenance=provenance,
                model=actor.model if actor else None,
            )
        )

    def ensure_running(self) -> None:
        if self.controller.inspect(self.run.id).run.status != "running":
            raise asyncio.CancelledError

    def agent(self, role: Role) -> Agent:
        found = next((a for a in self.experiment.agents if a.role == role and a.enabled), None)
        if found is None:
            raise ValueError(f"Enabled {role.value} agent is required")
        return found

    async def propose(self, agent: Agent, phase: str, context: str) -> Candidate:
        self.ensure_running()
        if self.run.execution_kind == "synthetic":
            if phase not in self.command.synthetic_answers:
                raise ValueError(f"Synthetic fixture missing {phase} answer")
            answer = self.command.synthetic_answers[phase]
            message = CouncilMessage.model_validate(
                dict(
                    **self.scope(Provenance.IMPORTED_SOURCE),
                    id=self.identity(phase + ":message"),
                    message_type="CLAIM",
                    sender_id=agent.id,
                    visibility="private",
                    content=answer.model_dump_json(),
                )
            )
            self.emit(
                phase + ":message",
                EventType.OBSERVATION_RECEIVED,
                (message,),
                agent,
                Provenance.IMPORTED_SOURCE,
            )
            return answer
        if self.run.execution_kind != "live" or self.command.synthetic_answers:
            raise ValueError("Replay cannot be executed as live inference")
        if not self.command.authorize_paid or not agent.permissions.remote_inference:
            raise PermissionError("Explicit paid-call authorization and agent permission required")
        if not agent.model_profile_id or not agent.model:
            raise ValueError("Live agent requires a pinned model profile")
        profile = ConfigurationStore(self.controller.settings.database_path).get(
            "profile", agent.model_profile_id, agent.model_profile_version
        )
        assert isinstance(profile, ModelProfile)
        if profile.provider != "runpod":
            raise ValueError("Only RunPod adapter is registered for live runtime calls")
        env = local_env()
        allowance = Decimal(env.get("DOXA_RUNPOD_ALLOWANCE_USD", "0"))
        upper = self.command.upper_bound_usd_per_attempt
        if upper is None:
            raise ValueError("A complete per-attempt compute cost upper bound is required")
        if not profile.enabled or env.get("DOXA_RUNPOD_ENABLED", "false").lower() != "true":
            raise PermissionError("RunPod is disabled")
        # Validate URL and credential presence before reserving a possible charge.
        from doxa.providers.runpod import endpoint_url

        endpoint_url(profile, env)
        if not env.get(profile.credential_env) or env.get(profile.credential_env) == "replace_me":
            raise ValueError("RunPod backend credential is missing")
        budget = self.experiment.budget
        for attempt in range(min(profile.retries, budget.max_retries) + 1):
            self.ensure_running()
            call_id = self.identity(f"{phase}:call:{attempt}")
            request = ModelRequest(
                call_id=call_id,
                run_id=self.run.id,
                trajectory_id=self.branch,
                agent_id=agent.id,
                assignment=agent.model,
                messages=(
                    ModelMessage(role="system", content=agent.instructions),
                    ModelMessage(
                        role="user",
                        content=context + "\nReturn only JSON: "
                        '{"policy":"invalidate_all|stale_on_update|stale_on_delete"}',
                    ),
                ),
                max_output_tokens=min(profile.max_output_tokens, budget.max_output_tokens),
                timeout_seconds=min(profile.timeout_seconds, budget.timeout_seconds),
            )
            size = sum(len(m.content.encode()) + 32 for m in request.messages)
            if size + request.max_output_tokens > min(
                profile.max_context_tokens, budget.max_context_tokens
            ):
                raise ValueError("Context/output budget exceeded")
            self.calls.reserve(
                self.run.id,
                call_id,
                upper,
                service="runpod",
                service_cap_usd=allowance,
                request_hash=hashlib.sha256(request.model_dump_json().encode()).hexdigest(),
                max_calls=budget.max_model_calls,
            )
            self.calls.dispatch_once(call_id, profile.concurrency)
            provider = RunPodProvider(profile, env)
            try:
                response = await provider.generate(request)
            except BaseException:
                self.calls.finish(call_id, "uncertain")
                record = ModelCall.model_validate(
                    dict(
                        **self.scope(),
                        id=self.identity(str(call_id)),
                        call_id=call_id,
                        agent_id=agent.id,
                        assignment=agent.model,
                        status="uncertain",
                        error_category="local_cancel_or_crash",
                    )
                )
                self.emit(f"{phase}:uncertain:{attempt}", EventType.MODEL_CALL_RECORDED, (record,))
                raise
            self.calls.finish(call_id, "completed" if response.error is None else "failed")
            self.record_response(response, agent, phase, attempt, upper)
            self.ensure_running()
            if response.error is None:
                return Candidate.model_validate_json(response.text or "")
            if not response.error.retryable or attempt >= min(profile.retries, budget.max_retries):
                raise RuntimeError("Provider " + response.error.category)
        raise RuntimeError("Provider attempts exhausted")

    def record_response(
        self, response: ModelResponse, agent: Agent, phase: str, attempt: int, upper: Decimal
    ) -> None:
        assert agent.model is not None
        record = ModelCall.model_validate(
            dict(
                **self.scope(),
                id=self.identity(str(response.call_id)),
                call_id=response.call_id,
                agent_id=agent.id,
                assignment=agent.model,
                response_id=safe_text(response.response_id) if response.response_id else None,
                reported_model_id=safe_text(response.reported_model_id)
                if response.reported_model_id
                else None,
                usage=response.usage.model_copy(update={"estimated_usd": upper}),
                error_category=response.error.category if response.error else None,
                status="failed" if response.error else "completed",
            )
        )
        records: tuple[Record, ...] = (record,)
        if response.text is not None:
            records += (
                CouncilMessage.model_validate(
                    dict(
                        **self.scope(Provenance.MODEL_OUTPUT),
                        id=self.identity(phase + ":message"),
                        message_type="CLAIM",
                        sender_id=agent.id,
                        visibility="private",
                        content=safe_text(response.text),
                    )
                ),
            )
        self.emit(
            f"{phase}:response:{attempt}",
            EventType.PROVIDER_FAILED if response.error else EventType.MODEL_CALL_RECORDED,
            records,
            agent,
            Provenance.MODEL_OUTPUT,
        )

    def check(self, candidate: Candidate, key: str) -> tuple[Claim, Verification, bool]:
        checks = sum(
            e.type == EventType.VERIFICATION_RECORDED for e in self.ledger.events(self.run.id)
        )
        if checks >= self.experiment.budget.max_tool_calls:
            raise ValueError("Deterministic verifier tool-call limit reached")
        claim = Claim.model_validate(
            dict(
                **self.scope(
                    Provenance.IMPORTED_SOURCE
                    if self.run.execution_kind == "synthetic"
                    else Provenance.MODEL_OUTPUT
                ),
                id=self.identity(key + ":claim"),
                proposition=candidate.model_dump_json(),
            )
        )
        self.emit(key + ":claim", EventType.CLAIM_PROPOSED, (claim,))
        results = verify(self.command.fixture, candidate)
        artifact = self.store.put(str(results).encode(), "text/plain")
        evidence = Evidence.model_validate(
            dict(
                **self.scope(Provenance.DETERMINISTIC_VERIFIER),
                id=self.identity(key + ":evidence"),
                description=str(results),
                source="cache-oracle-v1",
                artifacts=(artifact,),
            )
        )
        passed = all(results.values())
        verification = Verification.model_validate(
            dict(
                **self.scope(Provenance.DETERMINISTIC_VERIFIER),
                id=self.identity(key + ":verification"),
                subject_id=claim.id,
                evaluator_id="cache-policy-oracle",
                evaluator_version="1",
                verdict="valid" if passed else "invalid",
                evidence_ids=(evidence.id,),
            )
        )
        self.emit(
            key + ":checked",
            EventType.VERIFICATION_RECORDED,
            (evidence, verification),
            provenance=Provenance.DETERMINISTIC_VERIFIER,
        )
        return claim, verification, passed

    def checkpoint(self, candidate: Candidate) -> Checkpoint:
        env = CacheEnvironment(candidate)
        env.read("x")
        state = self.store.put(env.snapshot(), "application/json")
        config = self.store.put(self.command.fixture.model_dump_json().encode(), "application/json")
        checkpoint = Checkpoint.model_validate(
            dict(
                **self.scope(),
                id=self.identity("checkpoint"),
                task_version="1",
                fixture_hash=fixture_hash(self.command.fixture),
                workspace=state,
                environment_config=config,
                event_cursor=self.ledger.events(self.run.id)[-1].id,
            )
        )
        self.emit("checkpoint", EventType.CHECKPOINT_CREATED, (checkpoint,))
        return checkpoint

    def fork(self, checkpoint: Checkpoint, intervention: str) -> None:
        raw = self.store.get(checkpoint.workspace)
        CacheEnvironment.restore(raw)
        fixture = CacheFixture.model_validate_json(self.store.get(checkpoint.environment_config))
        if fixture_hash(fixture) != checkpoint.fixture_hash:
            raise ValueError("Checkpoint fixture hash mismatch")
        trajectory = Trajectory(
            id=self.identity("alternative"),
            run_id=self.run.id,
            parent_id=self.branch,
            checkpoint_id=checkpoint.id,
            intervention=intervention,
        )
        self.branch = trajectory.id
        self.emit("fork", EventType.BRANCH_CREATED, (trajectory,))
        self.emit("restored", EventType.CHECKPOINT_RESTORED)

    async def execute(self, command: ExecuteTask) -> "RunBundle":
        self.command = command
        if self.experiment.task_id != "cache-policy" or self.experiment.task_version != "1":
            raise ValueError("This execution path supports only cache-policy v1")
        digest = hashlib.sha256(command.model_dump_json().encode()).hexdigest()
        prior = [r for e in self.bundle.events for r in e.payload if isinstance(r, RunState)]
        if prior:
            if prior[0].reason_code != "execution:" + digest:
                raise LedgerConflict("Run already has a different execution command")
            if self.run.status in {"completed", "failed", "cancelled"}:
                return self.controller.inspect(self.run.id)
            raise LedgerConflict(
                "Run active or interrupted; cancel/reconcile before another attempt"
            )
        executor = self.agent(Role.EXECUTOR)
        if self.run.mode == ProtocolMode.COLLABORATIVE:
            peer = self.agent(Role.RESEARCHER)
        elif self.run.mode in {ProtocolMode.SOLO_DELIBERATIVE, ProtocolMode.ADVERSARIAL}:
            peer = self.agent(Role.SKEPTIC)
        else:
            peer = None
        if peer and peer.id == executor.id:
            raise ValueError("Council participants require distinct stable identities")
        if (
            self.run.mode == ProtocolMode.SOLO_DELIBERATIVE
            and peer
            and peer.model != executor.model
        ):
            # Instructions can differ; require provider/model identity, not whole assignment.
            if (
                peer.model
                and executor.model
                and (peer.model.provider, peer.model.model_id)
                != (executor.model.provider, executor.model.model_id)
            ):
                raise ValueError("Solo Deliberative requires the same physical model")
        state = RunState.model_validate(
            dict(
                **self.scope(),
                status="running",
                reason_code="execution:" + digest,
                id=self.identity("started"),
            )
        )
        start = Event(
            experiment_id=self.experiment.id,
            run_id=self.run.id,
            trajectory_id=self.branch,
            sequence=1,
            type=EventType.RUN_STARTED,
            payload=(state,),
            idempotency_key=f"{self.run.id}:start",
        )
        saved = self.ledger.append(start)
        if saved.id != start.id:
            raise LedgerConflict("Run has already been admitted by another executor")
        try:
            self.emit("environment", EventType.ENVIRONMENT_INITIALIZED)
            candidate = await self.propose(executor, "executor", command.fixture.model_dump_json())
            claim, verification, passed = self.check(candidate, "initial")
            baseline_passed = passed
            checkpoint = self.checkpoint(candidate)
            if peer:
                phase = "researcher" if self.run.mode == ProtocolMode.COLLABORATIVE else "skeptic"
                # Cooperative peer investigates independently; critics receive the candidate only.
                context = command.fixture.model_dump_json()
                if phase == "skeptic":
                    context += (
                        "\nChallenge this candidate with a testable alternative: "
                        + candidate.model_dump_json()
                    )
                alternative = await self.propose(peer, phase, context)
                alt_claim, alt_verification, alt_passed = self.check(alternative, "alternative")
                if phase == "skeptic":
                    challenge = Challenge.model_validate(
                        dict(
                            **self.scope(
                                Provenance.IMPORTED_SOURCE
                                if self.run.execution_kind == "synthetic"
                                else Provenance.MODEL_OUTPUT
                            ),
                            id=self.identity("challenge"),
                            claim_id=claim.id,
                            objection="Proposed alternate cache policy",
                            proposed_revision=alternative.model_dump_json(),
                        )
                    )
                    self.emit("challenge", EventType.CHALLENGE_SUBMITTED, (challenge,), peer)
                    criticism_verdict = (
                        "valid"
                        if not passed and alt_passed
                        else "invalid"
                        if passed
                        else "unverified"
                    )
                    adjudication = Verification.model_validate(
                        dict(
                            **self.scope(Provenance.DETERMINISTIC_VERIFIER),
                            id=self.identity("criticism-verdict"),
                            subject_id=challenge.id,
                            evaluator_id="cache-policy-challenge-oracle",
                            evaluator_version="1",
                            verdict=criticism_verdict,
                            evidence_ids=verification.evidence_ids + alt_verification.evidence_ids,
                        )
                    )
                    self.emit(
                        "criticism-verdict",
                        EventType.VERIFICATION_RECORDED,
                        (adjudication,),
                        provenance=Provenance.DETERMINISTIC_VERIFIER,
                    )
                if self.run.mode == ProtocolMode.SOLO_DELIBERATIVE:
                    # Third, separate context for the same model's defender phase.
                    alternative = await self.propose(
                        executor,
                        "defender",
                        command.fixture.model_dump_json()
                        + "\nDefend or repair the original policy "
                        "using these oracle outcomes only: "
                        + str(
                            {
                                "original_passed": passed,
                                "critic_alternative_passed": alt_passed,
                            }
                        ),
                    )
                    alt_claim, alt_verification, alt_passed = self.check(alternative, "defender")
                    if (
                        self.run.execution_kind == "live"
                        or "adjudicator" in command.synthetic_answers
                    ):
                        # Separate fourth context; a model recommendation still cannot
                        # establish validity. Keep legacy three-answer fixtures readable.
                        alternative = await self.propose(
                            executor,
                            "adjudicator",
                            command.fixture.model_dump_json()
                            + "\nSelect a final candidate using only the external test outcomes: "
                            + str({"initial_passed": passed, "defended_passed": alt_passed}),
                        )
                        alt_claim, alt_verification, alt_passed = self.check(
                            alternative, "adjudicator"
                        )
                accepted = not passed and alt_passed
                decision = Decision.model_validate(
                    dict(
                        **self.scope(),
                        id=self.identity("decision"),
                        claim_id=claim.id,
                        outcome="revise" if accepted else "retain",
                        reason="independent_oracle_accept"
                        if accepted
                        else "unsupported_or_unneeded_change",
                        verification_ids=(
                            verification.id,
                            alt_verification.id,
                        ),
                        policy_version="evidence-gate-v1",
                    )
                )
                self.emit("adjudication", EventType.ADJUDICATION_RECORDED, (decision,))
                if accepted:
                    self.fork(checkpoint, "adopt independently passing policy")
                    revised = Claim.model_validate(
                        dict(
                            **self.scope(),
                            id=self.identity("revised"),
                            proposition=alternative.model_dump_json(),
                            status="supported",
                            revises_id=claim.id,
                            evidence_ids=alt_verification.evidence_ids,
                        )
                    )
                    self.emit("revision", EventType.CLAIM_REVISED, (revised,))
                    candidate = alternative
                    passed = True
                # Transparent rule-based intervention/skip, with a hard branch limit.
                may_reflect = accepted and self.experiment.budget.max_reflections_per_branch > 0
                reflection = ReflectionDecision.model_validate(
                    dict(
                        **self.scope(),
                        id=self.identity("reflection"),
                        action="verify" if may_reflect else "stop",
                        trigger_event_id=self.ledger.events(self.run.id)[-1].id,
                        reason_code="validated_correction"
                        if may_reflect
                        else "reflection_limit_or_no_new_evidence",
                        policy_version="bounded-v1",
                        skipped=not may_reflect,
                    )
                )
                self.emit(
                    "reflection",
                    EventType.REFLECTION_TRIGGERED if may_reflect else EventType.REFLECTION_SKIPPED,
                    (reflection,),
                )
                if may_reflect:
                    _, _, passed = self.check(candidate, "post-intervention")
            else:
                reflection = ReflectionDecision.model_validate(
                    dict(
                        **self.scope(),
                        id=self.identity("reflection"),
                        action="stop",
                        trigger_event_id=self.ledger.events(self.run.id)[-1].id,
                        reason_code="solo_direct_baseline_no_critique",
                        policy_version="bounded-v1",
                        skipped=True,
                    )
                )
                self.emit("reflection", EventType.REFLECTION_SKIPPED, (reflection,))
            self.ensure_running()
            evaluation = Evaluation.model_validate(
                dict(
                    **self.scope(Provenance.DETERMINISTIC_VERIFIER),
                    id=self.identity("evaluation"),
                    evaluator_version="cache-oracle-v1",
                    metrics={
                        "task_success": float(passed),
                        "recovery": float(not baseline_passed and passed),
                        "regression": float(baseline_passed and not passed),
                    },
                    denominators={
                        "task_success": 1,
                        "recovery": int(not baseline_passed),
                        "regression": int(baseline_passed),
                    },
                    usage=Usage(latency_seconds=time.monotonic() - self.started),
                )
            )
            self.emit("evaluation", EventType.EVALUATION_RECORDED, (evaluation,))
            from doxa.core.memory_commands import ProposeMemory, TransitionMemory

            lesson = self.controller.propose_memory(
                self.run.id,
                ProposeMemory(
                    text="Invalidate cache entries after update and delete."
                    if passed
                    else "Cache entries never require invalidation.",
                    owner_agent_id=executor.id,
                    idempotency_key="outcome-lesson",
                    eligibility=("cache-policy-v1",),
                ),
            )
            if passed:
                validation = self.controller.validate_memory(self.run.id, lesson.id)
                if validation.verdict == "valid":
                    self.controller.transition_memory(
                        self.run.id,
                        lesson.id,
                        TransitionMemory(
                            trust="approved",
                            validation_ids=(validation.id,),
                            idempotency_key="outcome-promotion",
                        ),
                    )
            await self.controller.retrieve_memory(
                self.run.id, executor.id, "cache", conditions=("cache-policy-v1",)
            )
            final = RunState.model_validate(
                dict(
                    **self.scope(),
                    id=self.identity("closed"),
                    status="completed",
                    reason_code="task_passed" if passed else "task_failed",
                )
            )
            self.emit("closed", EventType.RUN_CLOSED, (final,))
        except BaseException as exc:
            if self.controller.inspect(self.run.id).run.status == "running":
                cancelled = isinstance(exc, asyncio.CancelledError)
                final = RunState.model_validate(
                    dict(
                        **self.scope(),
                        id=self.identity("stopped"),
                        status="cancelled" if cancelled else "failed",
                        reason_code="local_cancellation" if cancelled else type(exc).__name__,
                    )
                )
                self.emit(
                    "stopped",
                    EventType.RUN_CANCELLED if cancelled else EventType.RUN_FAILED,
                    (final,),
                )
            raise
        return self.controller.inspect(self.run.id)
