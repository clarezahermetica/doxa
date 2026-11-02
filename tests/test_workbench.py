"""Workbench acceptance checks use only temporary ledgers and mocked providers."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from doxa.api.app import create_app
from doxa.cli.main import app
from doxa.core.config import Settings
from doxa.core.models import (
    BudgetPolicy,
    Claim,
    ContextManifest,
    CouncilLimits,
    EventType,
    Experiment,
    ModelAssignment,
    ProtocolMode,
    Provenance,
    Role,
    SourceDocument,
    TaskSpecification,
)
from doxa.core.profiles import ModelProfile
from doxa.core.workbench import (
    ContextAssembler,
    DebateExecution,
    DebateRuntime,
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    ReviseClaim,
    add_agent,
    create_experiment,
    import_source,
    revise_claim,
)
from doxa.providers.contracts import ModelMessage, ModelRequest
from doxa.providers.runpod import RunPodProvider, endpoint_url
from doxa.retrieval.lexical import lexical_rank
from doxa.storage.artifacts import ArtifactStore


def council(controller, *, count=3, limits=None, mode=ProtocolMode.ADVERSARIAL, live=False):
    template = add_agent(
        controller,
        NewAgent(display_name="Skeptic", role=Role.SKEPTIC, instructions="Inspect evidence."),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Test debate",
            task=TaskSpecification(
                question="Should agents revise instructions?",
                council=limits or CouncilLimits(rounds=2),
            ),
            mode=mode,
            execution_kind="live" if live else "synthetic",
            participants=(ParticipantGroup(agent_id=template.id, count=count),),
            budget=BudgetPolicy(max_model_calls=20),
            idempotency_key=str(uuid4()),
        ),
    )
    exp = controller.ledger.get(run.experiment_id)
    assert isinstance(exp, Experiment)
    return run, exp


@pytest.mark.parametrize("scheduling", ["sequential", "round_parallel"])
def test_each_instance_participates_and_context_reconstructs(controller, scheduling):
    run, exp = council(
        controller, limits=CouncilLimits(rounds=2, scheduling=scheduling, concurrency=2)
    )
    assert len({a.id for a in exp.agents}) == 3
    assert len({a.template_id for a in exp.agents}) == 1
    source = import_source(
        controller,
        run.id,
        ImportSource(title="Paper", text="Instructions need review.", idempotency_key="source"),
    )
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    assert bundle.run.status == "completed"
    claims = [p for e in bundle.events for p in e.payload if isinstance(p, Claim)]
    assert len(claims) == 6
    assert {c.author_id for c in claims} == {a.id for a in exp.agents}
    contexts = [p for e in bundle.events for p in e.payload if isinstance(p, ContextManifest)]
    assert len(contexts) == 6
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    for context in contexts:
        messages = json.loads(store.get(context.messages))
        assert "Instructions need review." in messages[1]["content"]
        assert context.source_ids == (source.id,)
        assert context.input_token_upper_bound >= sum(len(m["content"].encode()) for m in messages)
    if scheduling == "round_parallel":
        assert all(not c.history_ids for c in contexts[:3])
    assert all(c.provenance == Provenance.IMPORTED_SOURCE for c in claims)
    with pytest.raises(ValueError, match="already started"):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))


def test_private_sources_and_private_messages_are_not_disclosed(controller):
    run, exp = council(controller, count=2)
    private = import_source(
        controller,
        run.id,
        ImportSource(
            title="Private",
            text="TOP PRIVATE",
            visibility="private",
            owner_agent_id=exp.agents[0].id,
            idempotency_key="private",
        ),
    )
    assembler = ContextAssembler(controller, run.id)
    owner = assembler.assemble(exp.agents[0], "owner")
    other = assembler.assemble(exp.agents[1], "other")
    assert private.id in owner.source_ids and private.id not in other.source_ids
    assert b"TOP PRIVATE" not in ArtifactStore(controller.settings.data_dir / "artifacts").get(
        other.messages
    )
    with pytest.raises(PermissionError):
        assembler.assemble(exp.agents[0].model_copy(update={"id": uuid4()}), "intruder")


@pytest.mark.parametrize("kwargs", [{"max_agents": 2}, {"max_calls": 2}])
def test_council_admission_caps(controller, kwargs):
    with pytest.raises(ValueError):
        council(controller, limits=CouncilLimits(**kwargs))


def test_token_cap_stops_without_paid_calls(controller):
    run, _ = council(controller, count=1, limits=CouncilLimits(rounds=2, total_tokens=1500))
    with pytest.raises(ValueError, match="limit"):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    assert controller.inspect(run.id).run.status == "failed"
    assert not controller.inspect(run.id).accounting


def test_live_debate_is_opt_in_before_start(controller):
    run, _ = council(controller, count=1, live=True)
    with pytest.raises(PermissionError):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    assert controller.inspect(run.id).run.status == "configured"


def test_revision_preserves_initial_claim_and_provenance(controller):
    run, _ = council(controller, count=1)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    original = next(p for e in bundle.events for p in e.payload if isinstance(p, Claim))
    revision = revise_claim(
        controller,
        run.id,
        ReviseClaim(claim_id=original.id, proposition="Human proposal", idempotency_key="revise"),
    )
    assert controller.ledger.get(original.id) == original
    assert revision.revises_id == original.id and revision.provenance == Provenance.HUMAN_ANNOTATION
    with pytest.raises(ValueError, match="already revised"):
        revise_claim(
            controller,
            run.id,
            ReviseClaim(
                claim_id=original.id,
                proposition="Second competing revision",
                idempotency_key="another",
            ),
        )


def test_sse_resume_and_foreign_cursor_and_origin(controller):
    run, _ = council(controller, count=1)
    asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    events = controller.inspect(run.id).events
    with TestClient(create_app(controller.settings)) as client:
        response = client.get(
            f"/api/runs/{run.id}/events?follow=false", headers={"Last-Event-ID": str(events[2].id)}
        )
        assert response.status_code == 200
        assert response.text.count("event: ledger") == len(events) - 3
        assert f"id: {events[2].id}\n" not in response.text
        assert client.get(f"/api/runs/{run.id}/events?after={uuid4()}").status_code == 409
        assert (
            client.get("/api/configuration", headers={"Origin": "https://evil.example"}).status_code
            == 403
        )
    assert controller.inspect(run.id).run.status == "completed"


def test_workbench_http_creates_distinct_instances_and_rejects_live_start(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        template = client.post(
            "/api/workbench/agents",
            json={"display_name": "A", "role": "researcher", "instructions": "Read sources"},
        ).json()
        response = client.post(
            "/api/workbench/experiments",
            json={
                "name": "API debate",
                "task": {"question": "What follows from this source?"},
                "participants": [{"agent_id": template["id"], "count": 2}],
                "execution_kind": "live",
                "idempotency_key": "api",
            },
        )
        assert response.status_code == 201, response.text
        run = response.json()
        assert client.post(f"/api/workbench/runs/{run['id']}/start", json={}).status_code == 403


def test_lexical_search_handles_quotes_and_precise_terms():
    a, b = uuid4(), uuid4()
    assert lexical_rank([(a, "cache invalidation"), (b, "sleep memory")], '"invalidation"') == (a,)
    assert lexical_rank([(a, "test")], '" OR * --') == ()


@pytest.mark.parametrize("provider", ["openai", "claude"])
def test_native_provider_http_wire_without_network(provider):
    profile = ModelProfile(
        id="native",
        provider=provider,
        model_id="exact-model",
        credential_env="TEST_API_KEY",
        enabled=True,
    )

    def respond(request):
        body = json.loads(request.content)
        assert body["model"] == "exact-model"
        if provider == "openai":
            assert request.url.host == "api.openai.com"
            assert body["max_completion_tokens"] == 100 and body["store"] is False
            payload = {
                "id": "response",
                "model": "exact-model",
                "choices": [{"message": {"content": "Argument"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
            }
        else:
            assert request.url.host == "api.anthropic.com"
            assert request.headers["x-api-key"] == "private-test-key"
            assert body["system"] == "Instructions" and body["max_tokens"] == 100
            payload = {
                "id": "response",
                "model": "exact-model",
                "content": [{"type": "text", "text": "Argument"}],
                "usage": {"input_tokens": 12, "output_tokens": 5},
            }
        return httpx.Response(200, json=payload)

    adapter = RunPodProvider(
        profile,
        {"TEST_API_KEY": "private-test-key", f"DOXA_{provider.upper()}_ENABLED": "true"},
        httpx.MockTransport(respond),
    )
    request = ModelRequest(
        call_id=uuid4(),
        run_id=uuid4(),
        trajectory_id=uuid4(),
        agent_id=uuid4(),
        assignment=ModelAssignment(
            provider=provider, model_id="exact-model", instruction_version="1"
        ),
        messages=(
            ModelMessage(role="system", content="Instructions"),
            ModelMessage(role="user", content="Question"),
        ),
        max_output_tokens=100,
        timeout_seconds=10,
    )
    result = asyncio.run(adapter.generate(request))
    assert result.error is None and result.text == "Argument"
    assert result.usage.input_tokens == 12 and result.usage.output_tokens == 5
    assert result.usage.billed_usd is None
    with pytest.raises(ValueError):
        endpoint_url(profile.model_copy(update={"base_url": "https://evil.example"}), {})


def test_cli_readable_demo_and_json_compatibility(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["demo", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Synthetic fixtures; no paid calls" in result.output
    result = runner.invoke(app, ["config-list", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0 and json.loads(result.output)["agents"]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/a",
        "https://127.0.0.1/a",
        "https://user:pass@example.org/a",
        "https://example.org:444/a",
        "https://other.org/a",
        "https://example.org/a#fragment",
    ],
)
def test_web_url_policy_refuses_unsafe_targets(url):
    from doxa.core.web_tools import checked_url

    with pytest.raises(PermissionError):
        checked_url(url, ("example.org",))


def test_web_dns_refuses_private_and_mixed_answers(monkeypatch):
    from doxa.core.web_tools import public_addresses

    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(PermissionError):
        public_addresses("example.org")


def tool_council(controller):
    agent = add_agent(
        controller,
        NewAgent(
            display_name="Web researcher",
            role=Role.RESEARCHER,
            instructions="Inspect bounded sources.",
            allowed_tools=("web_fetch", "web_search"),
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Tool policy fixture",
            task=TaskSpecification(
                question="Inspect evidence",
                network_mode="approved_fetch",
                allowed_domains=("example.org",),
                max_fetches=1,
            ),
            participants=(ParticipantGroup(agent_id=agent.id),),
            idempotency_key=str(uuid4()),
        ),
    )
    experiment = controller.ledger.get(run.experiment_id)
    assert isinstance(experiment, Experiment)
    return run, experiment.agents[0]


def test_mock_tools_durable_quota_idempotence_and_private_sources(controller):
    from doxa.core.web_tools import MockWeb, ToolRequest, use_tool

    run, agent = tool_council(controller)
    request = ToolRequest(
        agent_id=agent.id,
        tool="web_fetch",
        query_or_url="https://example.org/a",
        authorize_external=True,
        idempotency_key="fetch",
    )
    result = asyncio.run(use_tool(controller, run.id, request, MockWeb()))
    assert result.status == "completed" and result.cost_usd is None
    again = asyncio.run(use_tool(controller, run.id, request, MockWeb()))
    assert again.id == result.id
    with pytest.raises(ValueError, match="quota"):
        asyncio.run(
            use_tool(
                controller,
                run.id,
                request.model_copy(update={"idempotency_key": "again"}),
                MockWeb(),
            )
        )
    docs = [
        p
        for e in controller.inspect(run.id).events
        for p in e.payload
        if isinstance(p, SourceDocument)
    ]
    assert docs[0].visibility == "private" and docs[0].owner_agent_id == agent.id
    assert docs[0].provenance == Provenance.IMPORTED_SOURCE


def test_tools_require_both_permissions_and_live_switch(controller, monkeypatch):
    from doxa.core.web_tools import MockWeb, ToolRequest, use_tool

    run, agent = tool_council(controller)
    request = ToolRequest(
        agent_id=agent.id,
        tool="web_fetch",
        query_or_url="https://example.org/a",
        idempotency_key="blocked",
    )
    with pytest.raises(PermissionError):
        asyncio.run(use_tool(controller, run.id, request, MockWeb()))
    monkeypatch.setenv("DOXA_WEB_ENABLED", "false")
    with pytest.raises(PermissionError, match="disabled"):
        asyncio.run(
            use_tool(controller, run.id, request.model_copy(update={"authorize_external": True}))
        )
    assert all(e.type != EventType.ACTION_REQUESTED for e in controller.inspect(run.id).events)


def test_tool_failure_consumes_quota_and_is_not_replayed(controller):
    from doxa.core.web_tools import MockWeb, ToolRequest, use_tool

    class Broken(MockWeb):
        async def invoke(self, *args):
            raise TimeoutError("fixture timeout")

    run, agent = tool_council(controller)
    request = ToolRequest(
        agent_id=agent.id,
        tool="web_fetch",
        query_or_url="https://example.org/a",
        authorize_external=True,
        idempotency_key="timeout",
    )
    with pytest.raises(TimeoutError):
        asyncio.run(use_tool(controller, run.id, request, Broken()))
    assert asyncio.run(use_tool(controller, run.id, request, Broken())).status == "failed"


def test_source_and_revision_commands_are_idempotent(controller):
    run, _ = council(controller, count=1)
    command = ImportSource(title="Document", text="Stable source", idempotency_key="same")
    first = import_source(controller, run.id, command)
    assert import_source(controller, run.id, command) == first
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    claim = next(p for e in bundle.events for p in e.payload if isinstance(p, Claim))
    revision = ReviseClaim(claim_id=claim.id, proposition="New proposal", idempotency_key="same")
    first_revision = revise_claim(controller, run.id, revision)
    assert revise_claim(controller, run.id, revision) == first_revision


def test_console_mount_and_quit_preserves_run(controller):
    from doxa.cli.console import ResearchConsole

    run, _ = council(controller, count=1)

    async def view():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.cursor > 0
            await pilot.press("q")

    asyncio.run(view())
    assert controller.inspect(run.id).run.status == "configured"


def test_live_workbench_shared_model_uses_guarded_mock_calls(controller, monkeypatch):
    from doxa.core.models import ModelCall
    from doxa.core.profiles import CouncilConfig

    monkeypatch.setenv("DOXA_OPENAI_ENABLED", "true")
    monkeypatch.setenv("DOXA_OPENAI_ALLOWANCE_USD", "1")
    monkeypatch.setenv("WORKBENCH_TEST_KEY", "fixture-key-12345678")
    profile = ModelProfile(
        id="shared",
        provider="openai",
        model_id="test-model",
        enabled=True,
        credential_env="WORKBENCH_TEST_KEY",
        max_context_tokens=8192,
        max_input_bytes=8192,
    )
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    template = add_agent(
        controller,
        NewAgent(
            display_name="Shared model",
            role=Role.SKEPTIC,
            instructions="Inspect sources.",
            profile_id=profile.id,
            profile_version=1,
            remote_inference=True,
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Mocked live wire",
            execution_kind="live",
            task=TaskSpecification(
                question="What does the evidence establish?",
                council=CouncilLimits(rounds=1, scheduling="round_parallel", concurrency=3),
            ),
            participants=(ParticipantGroup(agent_id=template.id, count=3),),
            idempotency_key=str(uuid4()),
        ),
    )

    def respond(request):
        return httpx.Response(
            200,
            json={
                "id": "mock-response",
                "model": "test-model",
                "choices": [{"message": {"content": "An unverified model assertion."}}],
            },
        )

    monkeypatch.setattr(
        "doxa.core.execution.RunPodProvider",
        lambda p, e: RunPodProvider(p, e, httpx.MockTransport(respond)),
    )
    from decimal import Decimal

    bundle = asyncio.run(
        DebateRuntime(controller, run.id).execute_debate(
            DebateExecution(
                authorize_paid=True,
                authorize_external=True,
                upper_bound_usd_per_attempt=Decimal(".01"),
            )
        )
    )
    calls = [p for e in bundle.events for p in e.payload if isinstance(p, ModelCall)]
    assert len(calls) == 3 and len({c.agent_id for c in calls}) == 3
    assert {c.assignment.model_id for c in calls} == {"test-model"}
    assert len(bundle.accounting) == 3 and all(c.usage.billed_usd is None for c in calls)
    assert bundle.run.status == "completed"


def test_independent_verifier_cannot_be_instantiated_as_council_agent(controller):
    from doxa.core.models import Agent
    from doxa.core.profiles import AgentDefinition, CouncilConfig

    identity = uuid4()
    controller.save_configuration(
        CouncilConfig(
            agents=(
                AgentDefinition(
                    id=identity,
                    display_name="Oracle",
                    agent=Agent(id=identity, role=Role.INDEPENDENT_VERIFIER, instructions="Oracle"),
                ),
            )
        )
    )
    with pytest.raises(ValueError, match="cannot be LLM Council"):
        create_experiment(
            controller,
            NewExperiment(
                name="Forbidden Council",
                task=TaskSpecification(question="Question"),
                participants=(ParticipantGroup(agent_id=identity),),
                idempotency_key="verifier",
            ),
        )


def test_host_web_tools_do_not_require_native_model_tool_calling(controller):
    from doxa.core.profiles import CouncilConfig

    profile = ModelProfile(
        id="text-only",
        provider="openai",
        model_id="exact-text-model",
        credential_env="OPENAI_API_KEY",
    )
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    agent = add_agent(
        controller,
        NewAgent(
            display_name="Researcher",
            role=Role.RESEARCHER,
            instructions="Inspect sources.",
            profile_id=profile.id,
            profile_version=1,
            allowed_tools=("web_fetch",),
        ),
    )
    assert agent.agent.permissions.allowed_tools == ("web_fetch",)
