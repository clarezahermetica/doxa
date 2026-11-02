"""A fully offline, explicitly synthetic workbench acceptance demonstration."""

from uuid import uuid4

from doxa.core.controller import Controller
from doxa.core.models import BudgetPolicy, ContextManifest, CouncilLimits, Role, TaskSpecification
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


async def demonstrate(controller: Controller) -> dict[str, str | int]:
    researcher = add_agent(
        controller,
        NewAgent(
            display_name="Demo Researcher",
            role=Role.RESEARCHER,
            instructions="Compare supplied evidence and cite its identifiers. State uncertainty.",
        ),
    )
    skeptic = add_agent(
        controller,
        NewAgent(
            display_name="Demo Skeptic",
            role=Role.SKEPTIC,
            instructions="Identify unsupported assumptions; distinguish evidence from assertions.",
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Offline evidence & Council demonstration",
            task=TaskSpecification(
                question="When should an agent revise its instructions?",
                council=CouncilLimits(rounds=2, max_calls=10),
            ),
            participants=(
                ParticipantGroup(agent_id=researcher.id),
                ParticipantGroup(agent_id=skeptic.id, count=3),
            ),
            budget=BudgetPolicy(max_model_calls=10),
            idempotency_key=str(uuid4()),
        ),
    )
    import_source(
        controller,
        run.id,
        ImportSource(
            title="Synthetic demonstration source",
            source="DOXA offline fixture v1",
            text="Synthetic fixture: proposed instruction changes "
            "require human review, explicit provenance and reproducible evaluation.",
            idempotency_key="fixture",
        ),
    )
    bundle = await DebateRuntime(controller, run.id).execute_debate(DebateExecution())
    return {
        "run_id": str(run.id),
        "participants": 4,
        "contexts": sum(isinstance(p, ContextManifest) for e in bundle.events for p in e.payload),
    }
