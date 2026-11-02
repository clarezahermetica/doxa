"""Agent-issued tools are bounded and fully offline in acceptance tests."""

import asyncio
import json

import pytest

from doxa.core.models import (
    Claim,
    ContextManifest,
    CouncilLimits,
    Experiment,
    Role,
    SourceDocument,
    TaskSpecification,
    ToolAudit,
)
from doxa.core.workbench import (
    DebateExecution,
    DebateRuntime,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
)
from doxa.storage.artifacts import ArtifactStore


def setup(controller, *, network="approved_fetch", permitted=True, rounds=1):
    agent = add_agent(
        controller,
        NewAgent(
            display_name="Researcher",
            role=Role.RESEARCHER,
            instructions="Cite permitted evidence.",
            allowed_tools=("web_fetch",) if permitted else (),
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Tool loop fixture",
            task=TaskSpecification(
                question="What does the source say?",
                network_mode=network,
                allowed_domains=("example.org",),
                max_fetches=1,
                max_tool_rounds=rounds,
                council=CouncilLimits(rounds=1),
            ),
            participants=(ParticipantGroup(agent_id=agent.id),),
            idempotency_key="loop",
        ),
    )
    experiment = controller.ledger.get(run.experiment_id)
    assert isinstance(experiment, Experiment)
    participant = experiment.agents[0]
    phase = f"round:0:agent:{participant.id}"
    return run, participant, phase


def command(agent, phase, *, authorize=True, repeat=False):
    intent = json.dumps(
        {"tool_request": {"tool": "web_fetch", "query_or_url": "https://example.org/evidence"}}
    )
    return DebateExecution(
        authorize_external=authorize,
        synthetic_answers={
            str(agent.id): intent,
            phase + ":tool-followup:1": intent if repeat else "The source remains unverified.",
        },
    )


def test_tool_loop_records_private_source_and_followup_manifest(controller):
    run, agent, phase = setup(controller)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(command(agent, phase)))
    records = [p for e in bundle.events for p in e.payload]
    assert bundle.run.status == "completed"
    audits = [p for p in records if isinstance(p, ToolAudit)]
    assert [a.status for a in audits] == ["started", "completed"]
    source = next(p for p in records if isinstance(p, SourceDocument))
    contexts = [p for p in records if isinstance(p, ContextManifest)]
    assert len(contexts) == 2 and source.id in contexts[1].source_ids
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    assert "Synthetic tool fixture" in store.get(contexts[1].messages).decode()
    assert source.visibility == "private" and source.owner_agent_id == agent.id
    assert (
        next(p for p in records if isinstance(p, Claim)).proposition
        == "The source remains unverified."
    )


@pytest.mark.parametrize(
    "network,permitted,authorize",
    [
        ("offline", True, True),
        ("approved_fetch", False, True),
        ("approved_fetch", True, False),
    ],
)
def test_tool_loop_does_not_bypass_permission_layers(controller, network, permitted, authorize):
    run, agent, phase = setup(controller, network=network, permitted=permitted)
    with pytest.raises(PermissionError):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(
                command(agent, phase, authorize=authorize)
            )
        )
    assert not any(
        isinstance(p, ToolAudit) for e in controller.inspect(run.id).events for p in e.payload
    )


def test_repeated_tool_intents_hit_turn_bound_without_extra_dispatch(controller):
    run, agent, phase = setup(controller)
    with pytest.raises(ValueError, match="turn bound"):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(command(agent, phase, repeat=True))
        )
    assert (
        sum(
            isinstance(p, ToolAudit) and p.status == "started"
            for e in controller.inspect(run.id).events
            for p in e.payload
        )
        == 1
    )
