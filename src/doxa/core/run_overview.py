"""Read-only operator summary from committed research observations."""

from collections import Counter
from typing import TYPE_CHECKING
from uuid import UUID

from doxa.core.investigation import claim_threads_from_events
from doxa.core.models import (
    Challenge,
    Checkpoint,
    Claim,
    ClaimAssessment,
    Decision,
    Evaluation,
    EventType,
    Experiment,
    Memory,
    ModelCall,
    ProcedureManifest,
    ProviderActivity,
    ReflectionDecision,
    ResearchOutcome,
    ResponseNormalization,
    RetrievalAudit,
    RunState,
    Trajectory,
    Verification,
)

if TYPE_CHECKING:
    from doxa.core.controller import Controller, RunBundle


def failure_disposition(bundle: "RunBundle") -> str:
    """Recorded facts and supported operations; never infer a safe replay or final bill."""
    if bundle.run.status != "failed":
        return ""
    records = [r for e in bundle.events for r in e.payload]
    states = [r for r in records if isinstance(r, RunState)]
    reason = states[-1].reason_code if states else "not recorded"
    calls = {r.call_id: r for r in records if isinstance(r, ModelCall)}
    stages = [r.stage for r in records if isinstance(r, ProviderActivity)]
    committed = next(
        (
            e
            for e in reversed(bundle.events)
            if e.type
            not in {
                EventType.RUN_FAILED,
                EventType.RUN_CLOSED,
                EventType.RUN_CANCELLED,
            }
        ),
        None,
    )
    last = next(
        (
            e
            for e in reversed(bundle.events)
            if any(isinstance(r, (Claim, Challenge, ClaimAssessment, Decision)) for r in e.payload)
        ),
        None,
    )
    lines = [
        f"Recorded failure reason: {reason}",
        "The precise exception was never recorded for this historical failure."
        if reason == "debate_failed_inspect_operations"
        else "Failure classification only; exception messages are not saved here.",
        f"Last committed provider stage: {stages[-1] if stages else 'not recorded'}",
        f"Last committed stage: #{committed.sequence} ({committed.type.value})."
        if committed
        else "No earlier committed stage recorded.",
        f"Completed work: {sum(r.status == 'completed' for r in calls.values())} calls; "
        f"{sum(isinstance(r, Claim) for r in records)} claim versions; "
        f"{len(bundle.events)} committed events retained.",
        f"Last committed research contribution: #{last.sequence} ({last.type.value})."
        if last
        else "No research contribution committed.",
        "Accounting states: " + str(dict(Counter(str(r["state"]) for r in bundle.accounting))),
        "Supported next actions: inspect contributions and saved inputs; export history; "
        "prepare a separate attempt with doxa run new-attempt.",
        "A new attempt is configuration only and needs its own evidence/preflight and "
        "execution authorization. This failed attempt cannot resume in place. "
        "No uncertain request is replayed or reservation released automatically.",
    ]
    return "\n".join(lines)


def run_overview(controller: "Controller", run_id: UUID, branch: UUID | None = None) -> str:
    from doxa.core.quality_labels import correction_metrics
    from doxa.systems.research import branch_events

    bundle = controller.inspect(run_id)
    exp = controller.ledger.get(bundle.run.experiment_id)
    assert isinstance(exp, Experiment)
    all_events = list(bundle.events)
    branch = branch or all_events[0].trajectory_id
    events = branch_events(all_events, branch)
    rows = [r for e in events for r in e.payload]
    states = [r for e in all_events for r in e.payload if isinstance(r, RunState)]
    reason = states[-1].reason_code if states else "Not started"
    outcome = next((r for r in reversed(rows) if isinstance(r, ResearchOutcome)), None)
    milestones = [r for r in rows if isinstance(r, ProviderActivity)]
    last_stage = next((r.stage for r in reversed(milestones) if r.stage != "provider_error"), None)
    calls = {r.call_id: r for r in rows if isinstance(r, ModelCall)}
    task = exp.task
    procedure = next((r for r in rows if isinstance(r, ProcedureManifest)), None)
    coverage = Counter(r.kind for r in rows)
    quality = correction_metrics(rows)
    started = next((e.timestamp for e in all_events if e.type == EventType.RUN_STARTED), None)
    ended = next(
        (
            e.timestamp
            for e in reversed(all_events)
            if e.type
            in {
                EventType.RUN_FAILED,
                EventType.RUN_CLOSED,
                EventType.RUN_CANCELLED,
            }
        ),
        None,
    )
    elapsed = f"{(ended - started).total_seconds():.1f}s" if started and ended else "not final"
    protocol = task.research_protocol if task else "built-in task"
    outcome_name = outcome.epistemic_outcome if outcome else "not separately recorded"
    lines = [
        exp.name,
        f"Attempt: {run_id} · Created: {all_events[0].timestamp:%Y-%m-%d %H:%M:%S} UTC",
        f"Execution: {bundle.run.status} ({bundle.run.execution_kind}); elapsed: {elapsed}",
        f"Recorded stop reason: {reason}",
        f"Last recorded provider stage: {last_stage or 'none'}",
        f"Research outcome: {outcome_name}",
        "Model judgments are unverified. A successful call does not verify serving settings.",
        f"Protocol: {bundle.run.mode.value} / {protocol}",
        "Objective correctness: unknown from Council judgments alone",
    ]
    if bundle.run.status == "failed":
        lines += ["", failure_disposition(bundle), ""]
    if outcome:
        lines.append(f"Research stopping condition: {outcome.reason}")
    rejected = next(
        (
            r
            for r in reversed(rows)
            if isinstance(r, ResponseNormalization) and r.disposition != "accepted"
        ),
        None,
    )
    if rejected:
        lines.append(f"Last rejected response: {rejected.reason_code}")
    if task:
        limits = task.council
        lines.append(
            f"{limits.scheduling} · rounds/cycles {limits.rounds} · calls "
            f"{min(limits.max_calls, exp.budget.max_model_calls)} · "
            f"concurrency {limits.concurrency} · overall {limits.timeout_seconds:g}s"
        )
        lines.append(
            f"Council token bounds: {limits.per_agent_tokens} per agent; "
            f"{limits.total_tokens} total. Run context: {exp.budget.max_context_tokens}."
        )
    if procedure:
        lines.append(f"Procedure manifest: {procedure.id}")

    def usage(values: list[ModelCall], which: str) -> str:
        numbers = [getattr(p.usage, which) for p in values]
        return str(sum(numbers)) if numbers and all(n is not None for n in numbers) else "unknown"

    lines += ["", "Council assignments and recorded usage"]
    for agent in exp.agents:
        assigned = agent.model
        reasoning = assigned.settings.get("reasoning", {}) if assigned else {}
        effort = (
            reasoning.get("effort", "unverified default")
            if isinstance(reasoning, dict)
            else "unknown"
        )
        own = [r for r in calls.values() if r.agent_id == agent.id]
        observed = (
            ", ".join(sorted({p.reported_model_id for p in own if p.reported_model_id}))
            or "not reported"
        )
        billing = ", ".join(sorted({p.accounting_basis for p in own})) or "none"
        requested = f"{assigned.provider} / {assigned.model_id}" if assigned else "unassigned"
        profile = agent.model_profile_id or "none"
        version = agent.model_profile_version or "-"
        statuses = dict(Counter(p.status for p in own))
        adapters = {
            p.request_settings.get("adapter")
            for p in own
            if isinstance(p.request_settings.get("adapter"), str)
        }
        adapter_text = ", ".join(sorted(str(value) for value in adapters)) or "not recorded"
        tokens_in, tokens_out = usage(own, "input_tokens"), usage(own, "output_tokens")
        lines += [
            f"{agent.display_name} ({agent.role.value}) · memory {agent.memory_scope} · "
            f"tools {', '.join(agent.permissions.allowed_tools) or 'none'}",
            f"  Requested: {requested}; effort {effort}; profile {profile} v{version}",
            f"  Reported model: {observed}; recorded adapters: {adapter_text}",
            f"  Calls: {statuses}; accounting: {billing}; "
            f"tokens: {tokens_in} in / {tokens_out} out",
        ]
    accounting = Counter(str(row["state"]) for row in bundle.accounting)
    costs = [p.usage.billed_usd for p in calls.values()]
    usd = (
        str(sum(c for c in costs if c is not None))
        if costs and all(c is not None for c in costs)
        else "unknown"
    )
    lines += [
        f"Accounting operations: {dict(accounting)} · billed USD: {usd}",
        "",
        "Claim versions",
    ]
    threads = claim_threads_from_events(all_events, branch)
    for t in threads:
        lines.append(
            f"v{len(t.versions)} · {t.position} · {str(t.current.id)[:8]} · "
            f"{len(t.criticisms)} criticism(s), {len(t.responses)} response(s); "
            f"{sum(d.claim_id == t.current.id for d in t.decisions)} current judgment(s)"
        )
    net_correction = quality["net_justified_correction"]
    correction_label = net_correction if net_correction is not None else "unknown"
    lines += [
        f"Unlabeled or partially labeled revisions: {quality['unlabeled_revisions']}; "
        f"human-labeled net correction: {correction_label}",
        "",
        "Research-system coverage (this trajectory only)",
    ]
    revisions = sum(bool(r.revises_id) for r in rows if isinstance(r, Claim))
    forks = sum(r.parent_id is not None for r in rows if isinstance(r, Trajectory))
    measures = [
        (
            "Epistemic Git",
            f"{coverage['claim']} claim records, {revisions} revisions",
            any(isinstance(r, Claim) for r in rows),
        ),
        (
            "Counterfactual Engine",
            f"{coverage['checkpoint']} checkpoints, {forks} forks on this lineage",
            any(isinstance(r, Checkpoint) for r in rows),
        ),
        (
            "False Critic",
            f"{sum(not r.responds_to_id for r in rows if isinstance(r, Challenge))} criticisms",
            any(isinstance(r, Challenge) for r in rows),
        ),
        (
            "Memory Tribunal",
            f"{coverage['memory']} memory records, {coverage['retrieval_audit']} retrieval audits",
            any(isinstance(r, (Memory, RetrievalAudit)) for r in rows),
        ),
        (
            "Self-Correction Gym",
            f"{coverage['evaluation']} evaluation records",
            any(isinstance(r, Evaluation) for r in rows),
        ),
        (
            "Adaptive Reflection",
            f"{coverage['reflection_decision']} recorded decisions/skips",
            any(isinstance(r, ReflectionDecision) for r in rows),
        ),
    ]
    for name, facts, exercised in measures:
        state = (
            "exercised in synthetic fixture"
            if exercised and bundle.run.execution_kind == "synthetic"
            else "exercised"
            if exercised
            else "not exercised here"
        )
        lines.append(f"{name}: {state} · {facts}")
    independent = sum(
        isinstance(r, Verification) and r.provenance.value == "deterministic_verifier" for r in rows
    )
    lines.append(
        f"Independent verification records: {independent}. "
        "Coverage documents records, not correctness or mock/provider certification."
    )
    return "\n".join(lines)
