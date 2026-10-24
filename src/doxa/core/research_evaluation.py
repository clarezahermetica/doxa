"""Objective branch evaluation; human rubrics and LLM judgments never enter these rates."""

import json
from typing import TYPE_CHECKING
from uuid import UUID

from doxa.core.models import (
    Challenge,
    Claim,
    Evaluation,
    EventType,
    Evidence,
    ModelCall,
    Provenance,
    RetrievalAudit,
    Usage,
    Verification,
)
from doxa.storage.artifacts import ArtifactStore
from doxa.systems.research import branch_events

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def evaluate_branch(
    controller: "Controller",
    run_id: UUID,
    branch: UUID,
    identity: UUID,
    baseline_run_id: UUID | None,
) -> Evaluation:
    events = branch_events(controller.ledger.events(run_id), branch)
    records = [r for e in events for r in e.payload]
    task = [
        r
        for r in records
        if isinstance(r, Verification)
        and r.evaluator_id == "cache-oracle"
        and r.evaluator_version == "2"
        and r.provenance == Provenance.DETERMINISTIC_VERIFIER
    ]
    if not task:
        raise ValueError("Evaluation requires independent task results")
    if baseline_run_id:
        from doxa.core.comparison import compare

        compare(controller, baseline_run_id, run_id)
    initial, final = task[0].verdict == "valid", task[-1].verdict == "valid"
    verdicts = {
        r.subject_id: r
        for r in records
        if isinstance(r, Verification)
        and r.evaluator_id == "cache-challenge-oracle"
        and r.provenance == Provenance.DETERMINISTIC_VERIFIER
    }
    responses = [r for r in records if isinstance(r, Challenge) and r.responds_to_id]
    resolved = [
        r
        for r in responses
        if r.responds_to_id in verdicts
        and verdicts[r.responds_to_id].verdict in {"valid", "invalid", "partially_valid"}
    ]
    appropriate = {
        "valid": {"accept", "investigate"},
        "invalid": {"reject", "investigate"},
        "partially_valid": {"qualify", "investigate"},
    }
    correct = sum(
        r.response in appropriate[verdicts[r.responds_to_id].verdict]
        for r in resolved
        if r.responds_to_id is not None
    )
    revisions = [r for r in records if isinstance(r, Claim) and r.revises_id]
    evidence = {r.id: r for r in records if isinstance(r, Evidence)}
    store = ArtifactStore(controller.settings.data_dir / "artifacts")

    def justified_revision(claim: Claim) -> bool:
        try:
            proposition = json.loads(claim.proposition)
        except ValueError:
            return False
        for identity in claim.evidence_ids:
            source = evidence.get(identity)
            if not source or source.provenance != Provenance.DETERMINISTIC_VERIFIER:
                continue
            payload = json.loads(store.get(source.artifacts[0]))
            if source.source == "cache-oracle-v2" and (
                payload["candidate"] == proposition and all(payload["checks"].values())
            ):
                return True
            if source.source == "cache-challenge-oracle-v1" and (
                payload.get("alternative_candidate") == proposition
                and payload["objection_verdict"] == "valid"
                and all(payload["alternative_checks"].values())
                and payload["target_claim_id"] == str(claim.revises_id)
            ):
                return True
        return False

    justified = sum(justified_revision(claim) for claim in revisions)
    audits = [r for r in records if isinstance(r, RetrievalAudit)]
    eligible_uses = sum(len(r.eligible_ids) for r in audits)
    # Retrieval audits are controller decisions, not index claims. Eligible IDs must
    # reference the version approved at that moment; later revocation is not leakage.
    memory_versions = {
        r.id: r for e in controller.ledger.events(run_id) for r in e.payload if r.kind == "memory"
    }
    contamination = sum(
        i not in memory_versions or memory_versions[i].trust != "approved"
        for r in audits
        for i in r.eligible_ids
    )
    failed = [v.subject_id for v in task if v.verdict == "invalid"]
    propositions = [controller.ledger.get(i).model_dump().get("proposition") for i in failed]
    repeated = len(propositions) - len(set(propositions))
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    logs = [json.loads(store.get(evidence[v.evidence_ids[0]].artifacts[0])) for v in task]
    checks = [value for log in logs for value in log["checks"].values()]
    numerator = {
        "task_success": int(final),
        "test_pass": sum(checks),
        "recovery": int(not initial and final),
        "regression": int(initial and not final),
        "critic_discrimination": correct,
        "unjustified_revision": len(revisions) - justified,
        "memory_contamination": contamination,
        "repeat_error": repeated,
        "trace_integrity": justified,
    }
    denominators = {
        "task_success": 1,
        "test_pass": len(checks),
        "recovery": int(not initial),
        "regression": int(initial),
        "critic_discrimination": len(resolved),
        "unjustified_revision": len(revisions),
        "memory_contamination": eligible_uses,
        "repeat_error": len(propositions),
        "trace_integrity": len(revisions),
    }
    metrics: dict[str, float | None] = {
        k: value / denominators[k] if denominators[k] else None for k, value in numerator.items()
    }
    metrics.update({k + "_numerator": float(v) for k, v in numerator.items()})
    calls = [r for r in records if isinstance(r, ModelCall)]
    metrics["critic_induced_regression"] = (
        float(initial and not final) if (initial and responses) else None
    )
    metrics["critic_induced_regression_numerator"] = float(
        initial and not final and bool(responses)
    )
    denominators["critic_induced_regression"] = int(initial and bool(responses))
    metrics["model_calls"] = float(len(calls))
    metrics["tool_calls"] = float(
        sum(e.type in {EventType.VERIFICATION_RECORDED, EventType.ACTION_EXECUTED} for e in events)
    )
    # No observed provider calls is different from an observed call with missing usage.
    # Offline fixture counts are explicit; billing remains unknown without a bill.
    usage = Usage(
        input_tokens=sum(c.usage.input_tokens for c in calls if c.usage.input_tokens is not None)
        if calls and all(c.usage.input_tokens is not None for c in calls)
        else None,
        output_tokens=sum(c.usage.output_tokens for c in calls if c.usage.output_tokens is not None)
        if calls and all(c.usage.output_tokens is not None for c in calls)
        else None,
        latency_seconds=max(0, (events[-1].timestamp - events[0].timestamp).total_seconds()),
    )
    return Evaluation(
        id=identity,
        experiment_id=events[0].experiment_id,
        run_id=run_id,
        trajectory_id=branch,
        provenance=Provenance.DETERMINISTIC_VERIFIER,
        evaluator_version="research-gym-v1",
        baseline_run_id=baseline_run_id,
        metrics=metrics,
        denominators=denominators,
        usage=usage,
    )
