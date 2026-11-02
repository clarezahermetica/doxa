"""Pass 4 regressions for exposed offline research, with no provider/network calls."""

import asyncio

import pytest

from doxa.core.models import (
    BudgetPolicy,
    Challenge,
    Claim,
    CouncilLimits,
    Decision,
    ModelCall,
    Provenance,
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


@pytest.mark.parametrize("scheduling", ["sequential", "round_parallel"])
def test_exposed_structured_offline_mode_needs_no_hidden_answers(controller, scheduling):
    templates = [
        add_agent(
            controller,
            NewAgent(
                display_name=role.value,
                role=role,
                instructions="Synthetic fixture: preserve uncertainty and supplied evidence.",
            ),
        )
        for role in (Role.RESEARCHER, Role.SKEPTIC, Role.ARCHIVIST)
    ]
    run = create_experiment(
        controller,
        NewExperiment(
            name="Exposed structured offline mode",
            task=TaskSpecification(
                question="What does the supplied finite-cache evidence establish?",
                structured_actions=True,
                staged_research=True,
                council=CouncilLimits(
                    rounds=3,
                    scheduling=scheduling,
                    per_agent_tokens=131072,
                    total_tokens=1048576,
                ),
            ),
            participants=tuple(
                ParticipantGroup(agent_id=a.id, count=2 if i < 2 else 1)
                for i, a in enumerate(templates)
            ),
            idempotency_key="structured-offline",
            budget=BudgetPolicy(max_model_calls=20, max_context_tokens=32768),
        ),
    )
    import_source(
        controller,
        run.id,
        ImportSource(
            title="Explicit synthetic source",
            text="A finite oracle cannot establish timing claims.",
            idempotency_key="source",
        ),
    )
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    assert bundle.run.status == "completed"
    records = [p for e in bundle.events for p in e.payload]
    assert not any(isinstance(p, ModelCall) for p in records)
    assert any(isinstance(p, Challenge) and not p.responds_to_id for p in records)
    assert any(isinstance(p, Challenge) and p.responds_to_id for p in records)
    assert any(isinstance(p, Claim) and p.revises_id for p in records)
    assert any(isinstance(p, Decision) for p in records)
    generated = [e for e in bundle.events if e.idempotency_key.startswith("generated:")]
    assert len(generated) == 15 and len({e.actor_id for e in generated}) == 5
    assert all(e.provenance == Provenance.IMPORTED_SOURCE for e in generated)
    assert all("Synthetic" in p.proposition for p in records if isinstance(p, Claim))
