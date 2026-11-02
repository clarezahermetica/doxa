"""Full model-backed path via fake HTTP. These are not live-inference results."""

import asyncio
import json
from uuid import UUID, uuid4

import httpx

from doxa.core.models import (
    BudgetPolicy,
    Challenge,
    Claim,
    ContextManifest,
    CouncilLimits,
    Experiment,
    ModelCall,
    ProtocolMode,
    Provenance,
    Role,
    TaskSpecification,
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
from doxa.storage.artifacts import ArtifactStore


def configured(controller, *, parallel=False):
    profiles = tuple(
        ModelProfile(
            id=f"mock-{i}",
            provider="openai_compatible",
            model_id=f"unknown-served-model-{i}",
            base_url="http://127.0.0.1:12345/v1",
            local=True,
            authentication="none",
            enabled=True,
            max_context_tokens=32768,
            max_output_tokens=4096,
            max_input_bytes=524288,
            concurrency=3,
            capabilities=Capabilities(text_generation="available", structured_output="prompted"),
        )
        for i in range(2)
    )
    controller.save_configuration(CouncilConfig(profiles=profiles))
    templates = [
        add_agent(
            controller,
            NewAgent(
                display_name=f"Participant {i}",
                role=role,
                instructions="Use supplied evidence.",
                profile_id=profiles[i % 2].id,
                profile_version=1,
                remote_inference=True,
            ),
        )
        for i, role in enumerate((Role.RESEARCHER, Role.SKEPTIC))
    ]
    run = create_experiment(
        controller,
        NewExperiment(
            name="Mock-provider complete research",
            task=TaskSpecification(
                question="When should an agent change its instructions?",
                structured_actions=True,
                staged_research=True,
                council=CouncilLimits(
                    rounds=3,
                    concurrency=3,
                    scheduling="round_parallel" if parallel else "sequential",
                    max_calls=20,
                    timeout_seconds=3600,
                    per_agent_tokens=131072,
                    total_tokens=1048576,
                ),
            ),
            execution_kind="live",
            mode=ProtocolMode.COLLABORATIVE,
            participants=(
                ParticipantGroup(agent_id=templates[0].id, count=2),
                ParticipantGroup(agent_id=templates[1].id),
            ),
            budget=BudgetPolicy(
                max_model_calls=20,
                max_context_tokens=32768,
                max_output_tokens=4096,
                timeout_seconds=300,
            ),
            idempotency_key=str(uuid4()),
        ),
    )
    for i, text in enumerate(
        ("Changes require external review.", "Reversible changes need recorded tests.")
    ):
        import_source(
            controller,
            run.id,
            ImportSource(title=f"Source {i}", text=text, idempotency_key=f"source-{i}"),
        )
    return run


def attach_mock(controller, monkeypatch, run):
    observed = []

    async def handler(req):
        body = json.loads(req.content)
        user = body["messages"][1]["content"]
        first = json.loads(user.split("\n")[0])
        phase = first["phase"]
        index = int(phase.split(":")[1])
        agent_id = UUID(phase.split(":")[3])
        experiment = controller.ledger.get(run.experiment_id)
        assert isinstance(experiment, Experiment)
        actor = next(a for a in experiment.agents if a.id == agent_id)
        records = [p for e in controller.inspect(run.id).events for p in e.payload]
        sources = [p.id for p in records if p.kind == "source_document"]
        own = [p for p in records if isinstance(p, Claim) and p.author_id == actor.id]
        if index and actor.role == Role.SKEPTIC:
            target = next(p for p in records if isinstance(p, Claim) and p.author_id != actor.id)
            action = dict(
                operation="challenge",
                claim_id=str(target.id),
                objection="The claim needs a reversible-change qualification.",
                objection_type="scope",
                requested_correction="Qualify the claim using the reversible-change evidence.",
                source_ids=[str(sources[1])],
            )
        elif index == 2:
            challenges = [
                p
                for p in records
                if isinstance(p, Challenge)
                and not p.responds_to_id
                and any(c.id == p.claim_id for c in own)
            ]
            if challenges:
                action = dict(
                    operation="respond",
                    challenge_id=str(challenges[0].id),
                    response="qualify",
                    reason="The second source limits this conclusion.",
                    revised_proposition="Changes require review and reversible tests.",
                )
            else:
                action = dict(
                    operation="claim",
                    proposition="Qualified conclusion; uncertainty remains.",
                    revises_id=str(own[-1].id),
                    source_ids=[str(sources[1])],
                )
        else:
            action = dict(
                operation="claim",
                proposition="Changes require review, subject to evidence.",
                source_ids=[str(sources[0])],
            )
        observed.append((actor.id, phase, body["model"]))
        # Deliberately finish requests out of order in the parallel test.
        await asyncio.sleep(0.015 if str(actor.id) < str(experiment.agents[0].id) else 0.001)
        return httpx.Response(
            200,
            json={
                "id": "mock-" + req.headers["x-request-id"],
                "model": body["model"],
                "choices": [
                    {
                        "message": {"content": json.dumps({"research_action": action})},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 40},
            },
        )

    monkeypatch.setattr(
        controller.providers,
        "create",
        lambda p, env, **kw: RunPodProvider(p, env, httpx.MockTransport(handler)),
    )
    return observed


def test_complete_mock_provider_path(controller, monkeypatch):
    run = configured(controller)
    observed = attach_mock(controller, monkeypatch, run)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    assert bundle.run.status == "completed" and len(observed) == 9
    assert len({a for a, _, _ in observed}) == 3
    assert len({m for _, _, m in observed}) == 2
    records = [p for e in bundle.events for p in e.payload]
    claims = [p for p in records if isinstance(p, Claim)]
    assert any(c.revises_id for c in claims) and any(c.evidence_ids for c in claims)
    assert all(c.provenance == Provenance.MODEL_OUTPUT for c in claims)
    assert any(isinstance(p, Challenge) and p.responds_to_id for p in records)
    calls = [p for p in records if isinstance(p, ModelCall) and p.status == "completed"]
    assert len(calls) == 9 and all(p.usage.input_tokens == 100 for p in calls)
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    for call in calls:
        request = json.loads(store.get(call.request_artifact))
        assert request["profile_id"] and request["context_id"] and request["turn_id"]
        assert json.loads(store.get(call.response_artifact))["raw_response"]
    contexts = [p for p in records if isinstance(p, ContextManifest)]
    assert all("Scheduled stage:" in store.get(p.messages).decode() for p in contexts)
    from doxa.core.comparison import compare_branches
    from doxa.core.exports import export_run
    from doxa.core.models import Checkpoint, Evaluation, ReflectionDecision, Trajectory
    from doxa.core.text_research import ReviewFork

    checkpoint = next(p for p in records if isinstance(p, Checkpoint))
    root = next(p for p in records if isinstance(p, Trajectory))
    fork = controller.review_command(
        run.id,
        root.id,
        ReviewFork(
            checkpoint_id=checkpoint.id,
            intervention="Analysis of source conflicts; no model replay",
            idempotency_key="analysis-fork",
        ),
    )
    child = next(p for p in fork.payload if isinstance(p, Trajectory))
    comparison = compare_branches(controller, run.id, root.id, child.id)
    assert comparison.starting_state_equivalent
    assert any(isinstance(p, Evaluation) for p in records)
    assert sum(isinstance(p, ReflectionDecision) for p in records) == 3
    destination = controller.settings.data_dir / "mock-provider-export.json"
    export_run(controller, run.id, destination)
    assert json.loads(destination.read_text()) == controller.inspect(run.id).model_dump(mode="json")
    assert len(observed) == 9  # fork, comparison and export never generate model calls
    import hashlib
    import zipfile

    archive_path = controller.settings.data_dir / "mock-provider-export.zip"
    export_run(controller, run.id, archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert "configuration.json" in manifest["files"]
        assert any(name.startswith("artifacts/") for name in manifest["files"])
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected["sha256"]
        assert json.loads(archive.read("history.json")) == controller.inspect(run.id).model_dump(
            mode="json"
        )


def test_paired_attempt_and_condition_diff_are_explicit(controller, monkeypatch):
    from doxa.core.attempts import new_attempt
    from doxa.core.comparison import compare

    run = configured(controller)
    attach_mock(controller, monkeypatch, run)
    asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    paired = new_attempt(controller, run.id, idempotency_key="paired")
    assert paired.experiment_id == run.experiment_id and paired.id != run.id
    assert compare(controller, run.id, paired.id).comparison_kind == "descriptive"  # no sources yet
    treatment = new_attempt(
        controller, run.id, criticism_strategy="source_conflicts", idempotency_key="condition"
    )
    config = controller.ledger.get(treatment.experiment_id)
    assert config.comparison_parent_id == run.experiment_id
    assert config.condition_changes["criticism_strategy"]["after"] == "source_conflicts"
    for i, text in enumerate(
        ("Changes require external review.", "Reversible changes need recorded tests.")
    ):
        import_source(
            controller,
            treatment.id,
            ImportSource(title=f"Source {i}", text=text, idempotency_key=f"source-{i}"),
        )
    comparison = compare(controller, run.id, treatment.id)
    assert comparison.configuration_differences == ("task.criticism_strategy",)
    assert comparison.evidence_equal
    assert comparison.comparison_kind == "declared_criticism_strategy_condition"


def test_parallel_scientific_commits_follow_pinned_order(controller, monkeypatch):
    run = configured(controller, parallel=True)
    attach_mock(controller, monkeypatch, run)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    experiment = controller.ledger.get(run.experiment_id)
    assert isinstance(experiment, Experiment)
    rank = {Role.RESEARCHER: 0, Role.EXECUTOR: 1, Role.SKEPTIC: 2, Role.ARCHIVIST: 3}
    expected = [a.id for a in sorted(experiment.agents, key=lambda a: (rank[a.role], str(a.id)))]
    scientific = [e.actor_id for e in bundle.events if e.idempotency_key.startswith("generated:")]
    assert scientific == expected * 3
