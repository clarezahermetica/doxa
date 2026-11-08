"""Ledger-derived claim threads and bounded research-state scheduling.

This calls the existing runtime/controller. It owns no private history or model transport.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from doxa.core.models import (
    Agent,
    Challenge,
    Claim,
    ClaimAssessment,
    Decision,
    Evaluation,
    EventType,
    ResearchOutcome,
    Role,
)
from doxa.systems.research import branch_events

if TYPE_CHECKING:
    from doxa.core.controller import Controller, RunBundle
    from doxa.core.workbench import DebateExecution, DebateRuntime


def validate_stage_action(action: object, phase: str) -> None:
    """Reject off-stage proposals before their semantic records enter history."""
    fields = phase.split(":")
    stage = fields[fields.index("stage") + 1]
    allowed = {
        "initial_investigation": {"claim"},
        "cross_criticism": {"challenge", "assess"},
        "response_revision": {"respond"},
        "reassessment": {"assess"},
        "adjudication": {"adjudicate"},
    }[stage]
    if (
        not isinstance(action, dict)
        or not isinstance(action.get("operation"), str)
        or action["operation"] not in allowed
    ):
        raise ValueError("Research action does not match the selected stage: " + stage)
    target = fields[fields.index("target") + 1]
    challenge = fields[fields.index("challenge") + 1]
    if stage in {"cross_criticism", "reassessment", "adjudication"}:
        if str(action.get("claim_id")).lower() != target:
            raise ValueError("Research action does not address the selected stage target")
    if stage == "response_revision" and str(action.get("challenge_id")).lower() != challenge:
        raise ValueError("Research action does not address the selected stage criticism")


@dataclass
class ClaimThread:
    current: Claim
    versions: list[Claim]
    criticisms: list[Challenge]
    responses: list[Challenge]
    assessments: list[ClaimAssessment]
    decisions: list[Decision]

    @property
    def position(self) -> str:
        current_decisions = [d for d in self.decisions if d.claim_id == self.current.id]
        if current_decisions:
            latest = {d.adjudicator_id: d for d in current_decisions}
            outcomes = {d.outcome for d in latest.values()}
            if "reject" in outcomes and outcomes & {"retain", "qualify"}:
                return "disputed judgments (unverified)"
            return {
                "retain": "supported (unverified judgment)",
                "reject": "rejected (unverified judgment)",
                "qualify": "qualified (unverified judgment)",
            }.get(current_decisions[-1].outcome, "unresolved (unverified judgment)")
        if self.criticisms:
            return "contested" if not self.responses else "responded; judgment pending"
        return "proposed"


def claim_threads(controller: "Controller", run_id: UUID, branch: UUID) -> list[ClaimThread]:
    records = [
        p for e in branch_events(controller.ledger.events(run_id), branch) for p in e.payload
    ]
    claims = [p for p in records if isinstance(p, Claim)]
    groups: dict[UUID, list[Claim]] = {}
    for claim in claims:
        root = claim.commitment_id or claim.revises_id or claim.id
        # Historical revisions may omit a commitment_id; follow actual ancestry.
        root = next(
            (
                k
                for k, versions in groups.items()
                if any(v.id == claim.revises_id for v in versions)
            ),
            root,
        )
        groups.setdefault(root, []).append(claim)
    result = []
    for versions in groups.values():
        ids = {v.id for v in versions}
        criticisms = [
            p
            for p in records
            if isinstance(p, Challenge) and p.claim_id in ids and not p.responds_to_id
        ]
        result.append(
            ClaimThread(
                current=versions[-1],
                versions=versions,
                criticisms=criticisms,
                responses=[
                    p
                    for p in records
                    if isinstance(p, Challenge) and p.claim_id in ids and p.responds_to_id
                ],
                assessments=[
                    p for p in records if isinstance(p, ClaimAssessment) and p.claim_id in ids
                ],
                decisions=[p for p in records if isinstance(p, Decision) and p.claim_id in ids],
            )
        )
    return result


async def execute_investigation(
    runtime: "DebateRuntime", command: "DebateExecution"
) -> "RunBundle":
    from doxa.core.research_criteria import REVIEW_DISPUTES, assess_cycle
    from doxa.core.text_research import ReviewCheckpoint, ReviewEvaluate
    from doxa.core.workbench import ContextAssembler

    task = runtime.experiment.task
    assert task is not None
    participants = sorted(runtime.experiment.agents, key=lambda a: str(a.id))
    authors = [a for a in participants if a.role in {Role.RESEARCHER, Role.EXECUTOR}]
    skeptics = [a for a in participants if a.role == Role.SKEPTIC]
    archivists = [a for a in participants if a.role == Role.ARCHIVIST]
    if not (authors and skeptics and archivists):
        runtime.finish("failed", "investigation_requires_author_skeptic_archivist")
        raise ValueError("Investigation protocol requires author, Skeptic and Archivist")
    calls = 0
    call_admission = 0
    cycle = 0
    used = {a.id: 0 for a in participants}
    per_turns = {a.id: 0 for a in participants}
    total = 0

    class Exhausted(Exception):
        pass

    async def turn(
        actor: Agent, stage: str, target: UUID | None = None, challenge: UUID | None = None
    ) -> None:
        nonlocal calls, total, call_admission
        runtime.ensure_running()
        attempts = 1
        if actor.model_profile_id and runtime.run.execution_kind == "live":
            from doxa.core.profiles import ModelProfile
            from doxa.storage.configurations import ConfigurationStore

            pinned = ConfigurationStore(runtime.controller.settings.database_path).get(
                "profile", actor.model_profile_id, actor.model_profile_version
            )
            assert isinstance(pinned, ModelProfile)
            attempts += min(pinned.retries, runtime.experiment.budget.max_retries)
        attempts *= 1 + task.max_tool_rounds
        if call_admission + attempts > min(
            task.council.max_calls, runtime.experiment.budget.max_model_calls
        ):
            raise Exhausted("model_call_limit")
        if per_turns[actor.id] >= task.council.max_agent_turns:
            raise Exhausted("per_agent_turn_limit")
        phase = (
            f"investigation:{calls}:target:{target or 'none'}:"
            f"challenge:{challenge or 'none'}:stage:{stage}"
        )
        manifest = ContextAssembler(runtime.controller, runtime.run.id).assemble(
            actor,
            phase,
            agent_remaining=(task.council.per_agent_tokens - used[actor.id]) // attempts,
            total_remaining=(task.council.total_tokens - total) // attempts,
        )
        charge = manifest.input_token_upper_bound + runtime.experiment.budget.max_output_tokens
        charge *= attempts
        call_admission += attempts
        used[actor.id] += charge
        total += charge
        calls += 1
        per_turns[actor.id] += 1
        before = len(runtime.ledger.events(runtime.run.id))
        await runtime.turn(actor, phase, manifest, command)
        produced = [p for e in runtime.ledger.events(runtime.run.id)[before:] for p in e.payload]
        expected = {
            "initial_investigation": (Claim,),
            "cross_criticism": (Challenge, ClaimAssessment),
            "response_revision": (Challenge,),
            "reassessment": (ClaimAssessment,),
            "adjudication": (Decision,),
        }[stage]
        if not any(isinstance(p, expected) for p in produced):
            raise ValueError("Research turn did not produce its required stage operation: " + stage)
        if target and stage in {"cross_criticism", "reassessment", "adjudication"}:
            if not any(
                isinstance(p, expected) and getattr(p, "claim_id", None) == target for p in produced
            ):
                raise ValueError("Research operation did not address the selected current claim")

    def conclude(status: str, outcome: str, reason: str) -> None:
        record = ResearchOutcome.model_validate(
            dict(
                **runtime.scope(),
                id=runtime.identity("investigation:outcome"),
                execution_status=status,
                epistemic_outcome=outcome,
                reason=reason,
                turns=calls,
                cycles=cycle,
                decision_ids=tuple(
                    d.id
                    for t in claim_threads(runtime.controller, runtime.run.id, runtime.branch)
                    for d in t.decisions
                ),
            )
        )
        if runtime.controller.inspect(runtime.run.id).run.status != "running":
            runtime.emit("investigation:outcome", EventType.OBSERVATION_RECEIVED, (record,))
            return
        runtime.finish(
            "failed"
            if status == "failed"
            else "cancelled"
            if status == "interrupted"
            else "completed",
            reason,
            records=(record,),
        )

    try:
        async with asyncio.timeout(task.council.timeout_seconds):
            for author in authors:
                await turn(author, "initial_investigation")
            previous = None
            stagnant = 0
            for cycle_index in range(1, task.council.rounds + 1):
                cycle = cycle_index
                threads = claim_threads(runtime.controller, runtime.run.id, runtime.branch)
                targets = [t for t in threads if t.current.author_id in {a.id for a in authors}]
                if not targets:
                    raise ValueError("Author did not produce a research claim")
                for thread in targets:
                    for skeptic in skeptics:
                        await turn(skeptic, "cross_criticism", thread.current.id)
                    refreshed = next(
                        t
                        for t in claim_threads(runtime.controller, runtime.run.id, runtime.branch)
                        if any(v.id == thread.current.id for v in t.versions)
                    )
                    answered = {r.responds_to_id for r in refreshed.responses}
                    new_response = False
                    for criticism in refreshed.criticisms:
                        if criticism.id not in answered:
                            author = next(a for a in authors if a.id == thread.current.author_id)
                            current_thread = next(
                                t
                                for t in claim_threads(
                                    runtime.controller, runtime.run.id, runtime.branch
                                )
                                if any(v.id == thread.current.id for v in t.versions)
                            )
                            await turn(
                                author, "response_revision", current_thread.current.id, criticism.id
                            )
                            new_response = True
                            state = next(
                                t
                                for t in claim_threads(
                                    runtime.controller, runtime.run.id, runtime.branch
                                )
                                if any(v.id == thread.current.id for v in t.versions)
                            )
                            if criticism.id not in {r.responds_to_id for r in state.responses}:
                                raise ValueError("Author turn did not address its active criticism")
                    state = next(
                        t
                        for t in claim_threads(runtime.controller, runtime.run.id, runtime.branch)
                        if any(v.id == thread.current.id for v in t.versions)
                    )
                    if new_response:
                        for skeptic in skeptics:
                            await turn(skeptic, "reassessment", state.current.id)
                    for archivist in archivists:
                        await turn(archivist, "adjudication", state.current.id)
                threads = claim_threads(runtime.controller, runtime.run.id, runtime.branch)
                criteria = assess_cycle(
                    threads,
                    [
                        p
                        for e in branch_events(
                            runtime.ledger.events(runtime.run.id), runtime.branch
                        )
                        for p in e.payload
                    ],
                    {a.id for a in skeptics},
                    {a.id for a in archivists},
                    REVIEW_DISPUTES in task.evaluation_criteria,
                )
                evaluation = Evaluation.model_validate(
                    dict(
                        **runtime.scope(),
                        id=runtime.identity(f"cycle:{cycle}:criteria"),
                        evaluator_version="investigation-criteria-v1",
                        parameters={
                            "reason": criteria.reason,
                            "policy": "review_disputes"
                            if REVIEW_DISPUTES in task.evaluation_criteria
                            else "archivist_judgment",
                            "pending_challenges": [str(i) for i in criteria.pending_challenges],
                            "pending_reviewers": [str(i) for i in criteria.pending_reviewers],
                            "correctness": "not established by these controller checks",
                        },
                        metrics={
                            "open_challenges": len(criteria.pending_challenges),
                            "pending_reviewers": len(criteria.pending_reviewers),
                            "missing_current_judgments": criteria.missing_judgments,
                            "objective_correctness": None,
                        },
                        denominators={
                            "current_claims": len(threads),
                            "assigned_skeptics": len(skeptics),
                            "assigned_archivists": len(archivists),
                        },
                    )
                )
                runtime.emit(
                    f"cycle:{cycle}:criteria", EventType.EVALUATION_RECORDED, (evaluation,)
                )
                if criteria.missing_judgments:
                    raise ValueError("Archivist did not record a judgment for every active claim")
                if criteria.conclusion:
                    conclusion = criteria.conclusion
                    break
                # IDs alone are not progress. Text/evidence changes are a structural proxy;
                # paraphrases can still look new here, so the explicit cycle cap remains essential.
                fingerprint = hashlib.sha256(
                    json.dumps(
                        [
                            (
                                t.current.proposition,
                                sorted(
                                    (
                                        artifact.sha256,
                                        str(getattr(evidence, "source_location", None)),
                                    )
                                    for evidence in (
                                        runtime.controller.ledger.get(i)
                                        for i in t.current.evidence_ids
                                    )
                                    for artifact in getattr(evidence, "artifacts", ())
                                ),
                            )
                            for t in threads
                        ],
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                stagnant = stagnant + 1 if fingerprint == previous else 0
                previous = fingerprint
                if stagnant >= task.plateau_cycles:
                    conclusion = (
                        "stopped",
                        "unresolved",
                        "structural_plateau_no_new_claim_or_evidence",
                    )
                    break
            else:
                conclusion = ("stopped", "unresolved", "maximum_research_cycles")
        runtime.controller.review_command(
            runtime.run.id,
            runtime.branch,
            ReviewEvaluate(idempotency_key="investigation-final-evaluation"),
        )
        runtime.controller.review_command(
            runtime.run.id,
            runtime.branch,
            ReviewCheckpoint(idempotency_key="investigation-final-checkpoint"),
        )
        runtime.ensure_running()
        conclude(*conclusion)
    except Exhausted as exc:
        conclude("stopped", "unresolved", str(exc))
    except ValueError as exc:
        if str(exc).startswith("Context budget"):
            conclude("stopped", "unresolved", str(exc))
        else:
            conclude(
                "failed", "unresolved", "invalid_research_operation; inspect persisted diagnostics"
            )
            raise
    except TimeoutError:
        conclude("stopped", "unresolved", "wall_time_limit_remote_completion_may_be_unknown")
    except asyncio.CancelledError:
        conclude("interrupted", "unresolved", "cancelled_no_automatic_replay")
        raise
    except Exception as exc:
        if runtime.controller.inspect(runtime.run.id).run.status == "running":
            conclude("failed", "unresolved", type(exc).__name__ + ": inspect persisted diagnostics")
        raise
    return runtime.controller.inspect(runtime.run.id)
