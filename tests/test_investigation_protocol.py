"""Deterministic offline protocol checks, never empirical research findings."""

import asyncio
import json
from uuid import uuid4

from doxa.core.investigation import claim_threads
from doxa.core.models import (
    BudgetPolicy,
    Challenge,
    Claim,
    ClaimAssessment,
    CouncilLimits,
    Decision,
    ResearchOutcome,
    Role,
    TaskSpecification,
)
from doxa.core.workbench import (
    DebateExecution,
    DebateRuntime,
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)


def prepare(controller, calls=12, rounds=2, text=None):
    groups = []
    for role in (Role.RESEARCHER, Role.SKEPTIC, Role.ARCHIVIST):
        actor = add_agent(
            controller,
            NewAgent(
                display_name=role.value,
                role=role,
                instructions="Explicit offline protocol fixture.",
            ),
        )
        groups.append(ParticipantGroup(agent_id=actor.id))
    run = create_experiment(
        controller,
        NewExperiment(
            name="Synthetic investigation fixture",
            task=TaskSpecification(
                question="What can this fixture establish?",
                structured_actions=True,
                research_protocol="investigation",
                council=CouncilLimits(
                    rounds=rounds, max_calls=calls, per_agent_tokens=131072, total_tokens=393216
                ),
            ),
            participants=tuple(groups),
            budget=BudgetPolicy(max_model_calls=calls, max_context_tokens=16384),
            idempotency_key=str(uuid4()),
        ),
    )
    import_source(
        controller,
        run.id,
        ImportSource(
            title="Fixture evidence",
            text=text or "This is synthetic infrastructure evidence, not a scientific finding.",
            idempotency_key="fixture-source",
        ),
    )
    return run


def test_full_cycle_can_end_unresolved_without_consensus(controller):
    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    assert bundle.run.status == "completed"
    assert any(isinstance(p, Challenge) and p.responds_to_id for p in records)
    assert any(isinstance(p, Claim) and p.revises_id for p in records)
    assert any(isinstance(p, ClaimAssessment) for p in records)
    assert any(isinstance(p, Decision) and p.evidence_ids for p in records)
    outcome = next(p for p in records if isinstance(p, ResearchOutcome))
    assert outcome.execution_status == "concluded" and outcome.epistemic_outcome == "unresolved"
    assert outcome.turns == 5
    thread = claim_threads(controller, run.id, runtime.branch)[0]
    assert len(thread.versions) == 2 and thread.responses and thread.assessments
    assert "unresolved" in thread.position


def test_justified_maintenance_does_not_require_a_revision(controller):
    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def maintain(actor, phase, manifest):
        body = json.loads(default(actor, phase, manifest))
        if body["research_action"]["operation"] == "respond":
            body["research_action"].update(
                response="reject",
                revised_proposition=None,
                reason="Offline fixture: objection does not refute the bounded claim.",
            )
        return json.dumps(body)

    runtime.synthetic_answer = maintain
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    assert any(isinstance(p, Challenge) and p.response == "reject" for p in records)
    assert not any(isinstance(p, Claim) and p.revises_id for p in records)
    assert any(
        isinstance(p, ResearchOutcome) and p.execution_status == "concluded" for p in records
    )


def test_budget_stop_is_not_a_supported_research_conclusion(controller):
    run = prepare(controller, calls=3, rounds=1)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    outcome = next(p for p in records if isinstance(p, ResearchOutcome))
    assert outcome.execution_status == "stopped" and outcome.epistemic_outcome == "unresolved"
    assert outcome.reason == "model_call_limit" and outcome.turns == 3
    assert not any(isinstance(p, Decision) for p in records)


def test_multiple_skeptics_receive_responses_after_prior_revision(controller):
    run = prepare(controller)
    original = controller.ledger.get(run.experiment_id)
    skeptic = add_agent(
        controller,
        NewAgent(
            display_name="Second Skeptic",
            role=Role.SKEPTIC,
            instructions="Explicit offline second critic.",
        ),
    )
    groups = [ParticipantGroup(agent_id=a.template_id) for a in original.agents]
    groups.append(ParticipantGroup(agent_id=skeptic.id))
    expanded = create_experiment(
        controller,
        NewExperiment(
            name="Offline multiple critics",
            task=original.task,
            participants=tuple(groups),
            budget=original.budget,
            idempotency_key=str(uuid4()),
        ),
    )
    import_source(
        controller,
        expanded.id,
        ImportSource(
            title="Fixture source",
            text="Offline fixture evidence supports infrastructure checks only.",
            idempotency_key="multi",
        ),
    )
    runtime = DebateRuntime(controller, expanded.id)
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    criticisms = [p for p in records if isinstance(p, Challenge) and not p.responds_to_id]
    responded = {p.responds_to_id for p in records if isinstance(p, Challenge) and p.responds_to_id}
    assert len(criticisms) == 2 and all(c.id in responded for c in criticisms)
    assert any(
        isinstance(p, ResearchOutcome) and p.execution_status == "concluded" for p in records
    )


def test_archivist_can_reject_claim_without_forcing_consensus(controller):
    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def reject(actor, phase, manifest):
        body = json.loads(default(actor, phase, manifest))
        if body["research_action"]["operation"] == "adjudicate":
            body["research_action"]["outcome"] = "reject"
        return json.dumps(body)

    runtime.synthetic_answer = reject
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    outcome = next(p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome))
    assert outcome.epistemic_outcome == "rejected" and outcome.decision_ids
    assert outcome.judgment_basis == "unverified_model_judgments"


def test_declared_full_cycle_preflight_exercises_complete_investigation(controller):
    from doxa.core.cycle_preflight import cycle_preflight

    run = prepare(controller)
    before = controller.inspect(run.id).model_dump_json()
    report = cycle_preflight(controller, run.id)
    assert report["passed"], report
    assert [t["operation"] for t in report["turns"]] == [
        "claim",
        "challenge",
        "respond",
        "assess",
        "adjudicate",
    ]
    assert report["model_calls"] == 0
    assert controller.inspect(run.id).model_dump_json() == before


def test_skeptic_can_accept_without_inventing_an_objection(controller):
    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def accept(actor, phase, manifest):
        body = json.loads(default(actor, phase, manifest))
        action = body["research_action"]
        if action["operation"] == "challenge":
            body["research_action"] = {
                "operation": "assess",
                "claim_id": action["claim_id"],
                "stance": "accept",
                "reason": "Explicit fixture accepts the scoped claim without a challenge.",
                "source_ids": action["source_ids"],
            }
        return json.dumps(body)

    runtime.synthetic_answer = accept
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    assert not any(isinstance(p, Challenge) for p in records)
    assert any(isinstance(p, ClaimAssessment) and p.stance == "accept" for p in records)
    assert any(isinstance(p, Decision) and p.challenge_id is None for p in records)
    outcome = next(p for p in records if isinstance(p, ResearchOutcome))
    assert outcome.execution_status == "concluded" and outcome.epistemic_outcome == "unresolved"
