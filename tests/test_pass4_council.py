"""Five distinct model-backed participants through mock HTTP; never live inference."""

import asyncio
import json
from uuid import UUID

import httpx
import pytest

from doxa.core.execution import ProviderCallFailed
from doxa.core.models import (
    BudgetPolicy,
    CouncilLimits,
    Decision,
    Experiment,
    ModelCall,
    Provenance,
    Role,
    TaskSpecification,
    Trajectory,
)
from doxa.core.profiles import CouncilConfig, ModelProfile
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
from doxa.providers.contracts import Capabilities
from doxa.providers.runpod import RunPodProvider
from scripts.canonical_research import RANK, FixtureSource, fixture_answers


@pytest.mark.parametrize("failed_participant", [False, True])
def test_same_role_different_profiles_archivist_and_one_participant_failure(
    controller, monkeypatch, failed_participant
):
    profiles = tuple(
        ModelProfile(
            id=f"pass4-profile-{index}",
            provider="openai_compatible",
            model_id=f"previously-unknown-pass4-model-{index}",
            base_url="http://127.0.0.1:12345/v1",
            local=True,
            authentication="none",
            enabled=True,
            retries=0,
            max_context_tokens=65536,
            max_output_tokens=1024,
            concurrency=3,
            capabilities=Capabilities(text_generation="available", structured_output="prompted"),
        )
        for index in range(2)
    )
    controller.save_configuration(CouncilConfig(profiles=profiles))
    agents = [
        add_agent(
            controller,
            NewAgent(
                display_name=f"Independent participant {index}",
                role=role,
                instructions="Fixed mock fixture, not a live model result.",
                profile_id=profiles[index % 2].id,
                profile_version=1,
                remote_inference=True,
            ),
        )
        for index, role in enumerate(
            (Role.RESEARCHER, Role.RESEARCHER, Role.SKEPTIC, Role.SKEPTIC, Role.ARCHIVIST)
        )
    ]
    run = create_experiment(
        controller,
        NewExperiment(
            name="Pass 4 MOCK HTTP council, no live provider",
            task=TaskSpecification(
                question="Controlled mock research; distinguish linkage from correctness.",
                structured_actions=True,
                staged_research=True,
                council=CouncilLimits(
                    rounds=3,
                    scheduling="round_parallel",
                    concurrency=3,
                    per_agent_tokens=131072,
                    total_tokens=1048576,
                ),
            ),
            execution_kind="live",
            participants=tuple(ParticipantGroup(agent_id=a.id) for a in agents),
            budget=BudgetPolicy(max_model_calls=20, max_context_tokens=32768, timeout_seconds=300),
            idempotency_key="mock-five",
        ),
    )
    docs = {}
    for name in ("S1", "S2", "S3", "S4"):
        text = "Explicit mock source " + name
        doc = import_source(
            controller, run.id, ImportSource(title=name, text=text, idempotency_key=name)
        )
        docs[name] = FixtureSource(doc.id, text)
    experiment = controller.ledger.get(run.experiment_id)
    assert isinstance(experiment, Experiment)
    branch = next(
        p.id
        for e in controller.inspect(run.id).events
        for p in e.payload
        if isinstance(p, Trajectory)
    )
    answers = fixture_answers(experiment, branch, docs)
    ordered = sorted(experiment.agents, key=lambda a: (RANK[a.role], str(a.id)))
    requests = []

    async def respond(request):
        body = json.loads(request.content)
        phase = json.loads(body["messages"][1]["content"].split("\n")[0])["phase"]
        actor = UUID(phase.split(":")[3])
        requests.append((actor, phase, body["model"]))
        await asyncio.sleep(0.03 if actor == ordered[0].id else 0.001)
        if failed_participant and actor == ordered[1].id:
            return httpx.Response(500, json={"error": "mock participant failure"})
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"message": {"content": answers[phase]}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 17, "completion_tokens": 11},
            },
        )

    monkeypatch.setattr(
        controller.providers,
        "create",
        lambda p, env, **kw: RunPodProvider(p, env, httpx.MockTransport(respond)),
    )
    if failed_participant:
        with pytest.raises(ProviderCallFailed):
            asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
        assert controller.inspect(run.id).run.status == "failed"
        assert len(requests) == 5  # No next round, substitution or implicit retry.
    else:
        bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
        assert bundle.run.status == "completed" and len(requests) == 15
        scientific = [e for e in bundle.events if e.idempotency_key.startswith("generated:")]
        assert [e.actor_id for e in scientific] == [a.id for a in ordered] * 3
        assert len({actor for actor, _, _ in requests}) == 5
        assert len({model for _, _, model in requests}) == 2
        decisions = [p for e in bundle.events for p in e.payload if isinstance(p, Decision)]
        assert decisions and all(p.provenance == Provenance.LLM_EVALUATOR for p in decisions)
        calls = [
            p
            for e in bundle.events
            for p in e.payload
            if isinstance(p, ModelCall) and p.status == "completed"
        ]
        assert len(calls) == 15 and all(p.usage.input_tokens == 17 for p in calls)
