import asyncio
import json
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

from doxa.api.app import create_app
from doxa.cli.main import app
from doxa.core.config import Settings
from doxa.core.controller import CapabilityUnavailable, ConfigureRun, Controller
from doxa.core.execution import ExecuteTask, ProviderCallFailed
from doxa.core.models import (
    Agent,
    BudgetPolicy,
    Event,
    EventType,
    Experiment,
    ModelAssignment,
    ModelCall,
    Permissions,
    Role,
)
from doxa.core.profiles import AgentDefinition, CouncilConfig, ModelProfile, PricingMetadata
from doxa.environments.cache_adapter import CacheTaskAdapter
from doxa.environments.cache_policy import CacheFixture, Candidate
from doxa.environments.contracts import Action, TaskEnvironment, TaskSpec
from doxa.environments.sandbox import DisabledSandbox, SandboxLimits, sandbox_status
from doxa.providers.contracts import Capabilities, ModelMessage, ModelRequest
from doxa.providers.registry import ProviderRegistry, readiness, reservation_upper_bound
from doxa.providers.runpod import RunPodProvider, endpoint_url
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.budget import BudgetExceeded, BudgetStore
from doxa.storage.database import connection


def profile(**kwargs):
    return ModelProfile(
        id="test",
        provider="runpod",
        model_id="test/exact-model",
        endpoint_id="test-endpoint",
        enabled=True,
        **kwargs,
    )


def environment():
    return {
        "DOXA_RUNPOD_ENABLED": "true",
        "RUNPOD_API_KEY": "synthetic-http-test-key",
        "DOXA_RUNPOD_ALLOWANCE_USD": "1",
    }


def request(**kwargs):
    return ModelRequest(
        call_id=uuid4(),
        run_id=uuid4(),
        trajectory_id=uuid4(),
        agent_id=uuid4(),
        assignment=ModelAssignment(
            provider="runpod", model_id="test/exact-model", instruction_version="1"
        ),
        messages=(ModelMessage(role="user", content="Finite fixture input"),),
        max_output_tokens=32,
        timeout_seconds=0.05,
        **kwargs,
    )


def live_run(controller, monkeypatch, handler, retries=0, pricing=None, token_cap=10):
    import doxa.core.execution as runtime

    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    p = profile(retries=retries, timeout_seconds=0.1, pricing=pricing)
    agent = Agent(
        role=Role.EXECUTOR,
        instructions="Choose only a finite cache policy",
        permissions=Permissions(remote_inference=True),
    )
    controller.save_configuration(
        CouncilConfig(
            profiles=(p,),
            agents=(
                AgentDefinition(
                    id=agent.id,
                    agent=agent,
                    display_name="Mocked HTTP",
                    model_profile_id=p.id,
                    model_profile_version=1,
                ),
            ),
        )
    )
    real = RunPodProvider
    monkeypatch.setattr(
        runtime, "RunPodProvider", lambda p, e: real(p, e, httpx.MockTransport(handler))
    )
    run = controller.configure_run(
        ConfigureRun(
            idempotency_key=str(uuid4()),
            agent_ids=(agent.id,),
            experiment=Experiment(
                name="Mocked HTTP infrastructure",
                task_id="cache-policy",
                task_version="1",
                environment_version="1",
                policy_version="1",
                evaluator_version="1",
                budget=BudgetPolicy(max_model_calls=token_cap),
            ),
        )
    )
    return run


def test_registry_readiness_is_local_only_and_preserves_unknown_credit_balance():
    registry = ProviderRegistry()
    assert {d.provider for d in registry.descriptors() if d.implemented} == {
        "runpod",
        "openai_compatible",
        "openai",
        "claude",
        "gemini",
        "codex_cli",
    }
    result = readiness(profile(), environment())
    assert result.status == "ready_for_authorized_test" and result.credit_balance_usd is None
    assert not result.remote_verified
    assert "synthetic-http-test-key" not in result.model_dump_json()
    assert readiness(profile(), {}).status == "disabled"
    missing = readiness(profile(), {"DOXA_RUNPOD_ENABLED": "true"})
    assert missing.status == "not_ready" and not missing.credential_present


def test_generic_compatible_adapter_requires_explicit_opt_in_and_preserves_usage():
    p = ModelProfile(
        id="compatible",
        provider="openai_compatible",
        model_id="exact/served-name",
        base_url="https://compatible.example/v1",
        credential_env="CUSTOM_PROVIDER_KEY",
        enabled=True,
    )
    command = request().model_copy(
        update={
            "assignment": ModelAssignment(
                provider=p.provider, model_id=p.model_id, instruction_version="fixture-v1"
            )
        }
    )
    env = {
        "CUSTOM_PROVIDER_KEY": "synthetic-compatible-credential",
        "DOXA_OPENAI_COMPATIBLE_ENABLED": "true",
        "DOXA_OPENAI_COMPATIBLE_ALLOWANCE_USD": "1",
    }

    def handler(req):
        assert str(req.url) == "https://compatible.example/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer " + env["CUSTOM_PROVIDER_KEY"]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "fixture response"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    registry = ProviderRegistry()
    adapter = registry.create(
        p,
        env,
        factory=lambda profile, values: RunPodProvider(
            profile, values, httpx.MockTransport(handler)
        ),
    )
    response = asyncio.run(adapter.generate(command))
    assert response.usage.input_tokens == 4 and response.usage.output_tokens == 2
    assert (
        response.usage.billed_usd is None
        and readiness(p, env).status == "ready_for_authorized_test"
    )
    with pytest.raises(ValueError, match="explicit HTTPS"):
        endpoint_url(p.model_copy(update={"base_url": None}), {})


def test_configured_complete_price_is_used_by_live_controller_without_manual_override(
    controller, monkeypatch
):
    pricing = PricingMetadata(
        version="fixture-price-v1",
        source="Synthetic complete-cost fixture",
        kind="complete_operation",
        complete_operation_upper_bound_usd=Decimal(".05"),
    )
    run = live_run(
        controller,
        monkeypatch,
        lambda req: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"policy":"invalidate_all"}'}}],
                "id": "synthetic-configured-price-response",
            },
        ),
        pricing=pricing,
    )
    bundle = asyncio.run(controller.execute_task(run.id, ExecuteTask(authorize_paid=True)))
    assert bundle.run.status == "completed" and bundle.accounting[0]["reserved_microusd"] == 50000
    call = next(r for e in bundle.events for r in e.payload if isinstance(r, ModelCall))
    assert call.usage.pricing_version == "fixture-price-v1"
    assert call.usage.billed_usd is None and call.assignment.pricing_version == "fixture-price-v1"


@pytest.mark.parametrize(
    "capabilities",
    [
        Capabilities(structured_output="native"),
        Capabilities(streaming=True),
        Capabilities(tool_calling="native"),
        Capabilities(seed_control=True),
        Capabilities(context_limit=100),
    ],
)
def test_unimplemented_capabilities_fail_before_transport(capabilities):
    def handler(req):
        pytest.fail("Transport must not be called")

    result = asyncio.run(
        RunPodProvider(
            profile(capabilities=capabilities), environment(), httpx.MockTransport(handler)
        ).generate(request())
    )
    assert result.error.category in {"configuration", "unsupported"}
    assert not result.error.billing_uncertain


def test_schema_constrained_requests_fail_closed_without_http():
    result = asyncio.run(
        RunPodProvider(
            profile(),
            environment(),
            httpx.MockTransport(lambda req: pytest.fail("Unexpected HTTP")),
        ).generate(request(response_schema={"type": "object"}))
    )
    assert result.error.category == "unsupported" and not result.error.billing_uncertain


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"choices": []},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": -1}},
        {"choices": [{"message": {"content": "ok"}}], "usage": {"completion_tokens": "12"}},
        {"choices": [{"message": {"content": "ok"}}], "id": 42},
    ],
)
def test_invalid_responses_preserve_uncertainty(payload):
    result = asyncio.run(
        RunPodProvider(
            profile(),
            environment(),
            httpx.MockTransport(lambda req: httpx.Response(200, json=payload)),
        ).generate(request())
    )
    assert result.error.category == "invalid_response"
    assert result.error.billing_uncertain and result.usage.billed_usd is None


def test_adapter_redacts_text_ids_and_honors_exact_url_model_and_request_id():
    env = environment()
    command = request()

    def handler(req):
        assert req.headers["X-Request-ID"] == str(command.call_id)
        assert req.headers["authorization"] == "Bearer " + env["RUNPOD_API_KEY"]
        assert str(req.url) == "https://api.runpod.ai/v2/test-endpoint/openai/v1/chat/completions"
        assert json.loads(req.content)["model"] == "test/exact-model"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": env["RUNPOD_API_KEY"]}}],
                "id": env["RUNPOD_API_KEY"],
                "model": env["RUNPOD_API_KEY"],
            },
        )

    response = asyncio.run(
        RunPodProvider(profile(), env, httpx.MockTransport(handler)).generate(command)
    )
    assert env["RUNPOD_API_KEY"] not in response.model_dump_json()
    assert response.call_id == command.call_id and response.usage.input_tokens is None


def test_enforced_wall_timeout_and_explicit_local_cancel():
    async def handler(req):
        await asyncio.sleep(10)
        return httpx.Response(200)

    provider = RunPodProvider(profile(), environment(), httpx.MockTransport(handler))
    response = asyncio.run(provider.generate(request()))
    assert response.error.category == "timeout" and response.error.billing_uncertain

    async def scenario():
        command = request().model_copy(update={"timeout_seconds": 10})
        task = asyncio.create_task(provider.generate(command))
        await asyncio.sleep(0.01)
        assert await provider.cancel(command.call_id)
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not await provider.cancel(command.call_id)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status,category",
    [
        (400, "invalid_request"),
        (404, "invalid_request"),
        (401, "authentication"),
        (403, "authentication"),
        (429, "quota"),
        (503, "transport"),
    ],
)
def test_provider_status_errors_never_echo_bodies(status, category):
    response = asyncio.run(
        RunPodProvider(
            profile(),
            environment(),
            httpx.MockTransport(
                lambda req: httpx.Response(status, text="sensitive synthetic diagnostic")
            ),
        ).generate(request())
    )
    assert response.error.category == category
    assert "sensitive synthetic diagnostic" not in response.model_dump_json()


def test_ambiguous_timeout_never_retries_and_reservation_survives_restart(controller, monkeypatch):
    calls = []

    async def handler(req):
        calls.append(req)
        await asyncio.sleep(10)
        return httpx.Response(200)

    run = live_run(controller, monkeypatch, handler, retries=3)
    with pytest.raises(ProviderCallFailed, match="timeout"):
        asyncio.run(
            controller.execute_task(
                run.id, ExecuteTask(authorize_paid=True, upper_bound_usd_per_attempt=Decimal(".1"))
            )
        )
    reloaded = Controller(controller.settings).inspect(run.id)
    assert len(calls) == 1 and len(reloaded.accounting) == 1
    assert reloaded.accounting[0]["state"] == "uncertain"
    assert reloaded.accounting[0]["billed_microusd"] is None
    record = next(r for e in reloaded.events for r in e.payload if isinstance(r, ModelCall))
    assert record.status == "uncertain" and record.billing_uncertain and record.request_hash
    assert reloaded.events[-1].payload[0].reason_code == "provider:timeout"


def test_safe_connection_retries_are_bounded_and_each_reserved(controller, monkeypatch):
    calls = []

    def handler(req):
        calls.append(req)
        raise httpx.ConnectError("synthetic pre-send failure", request=req)

    run = live_run(controller, monkeypatch, handler, retries=1)
    with pytest.raises(ProviderCallFailed):
        asyncio.run(
            controller.execute_task(
                run.id, ExecuteTask(authorize_paid=True, upper_bound_usd_per_attempt=Decimal(".1"))
            )
        )
    assert len(calls) == 2
    assert all(
        o["state"] == "failed" and o["billed_microusd"] is None
        for o in controller.inspect(run.id).accounting
    )


def test_complete_operation_price_can_reserve_but_token_rates_cannot_estimate_runpod_compute():
    pricing = PricingMetadata(
        version="fixture-v1",
        source="Synthetic operator fixture; not a tariff",
        kind="complete_operation",
        complete_operation_upper_bound_usd=Decimal(".1234561"),
    )
    p = profile(pricing=pricing)
    assert reservation_upper_bound(p, request(), None) == Decimal(".123457")
    assert reservation_upper_bound(p, request(), Decimal(".2")) == Decimal(".200000")
    token = PricingMetadata(
        version="fixture-v1",
        source="Synthetic test rates",
        kind="token",
        input_usd_per_million=Decimal("1"),
        output_usd_per_million=Decimal("2"),
    )
    with pytest.raises(ValueError, match="complete"):
        reservation_upper_bound(profile(pricing=token), request(), None)
    with pytest.raises(ValidationError):
        PricingMetadata(version="bad", source="test", kind="token", input_usd_per_million="NaN")


def test_budget_exhaustion_prevents_transport_and_uncertainty_overrides_concurrency(
    controller, monkeypatch, command
):
    run = live_run(
        controller, monkeypatch, lambda req: pytest.fail("No paid transport allowed"), token_cap=0
    )
    with pytest.raises(BudgetExceeded):
        asyncio.run(
            controller.execute_task(
                run.id, ExecuteTask(authorize_paid=True, upper_bound_usd_per_attempt=Decimal(".1"))
            )
        )
    budget = BudgetStore(controller.settings.database_path)
    # Admission on a terminal run is now forbidden; test service uncertainty on
    # a separate configured run, independently from the failed budget attempt.
    run = controller.configure_run(command)
    a, b = uuid4(), uuid4()
    for identity in (a, b):
        budget.reserve(
            run.id,
            identity,
            Decimal(".1"),
            service="runpod",
            service_cap_usd=Decimal("1"),
            request_hash=str(identity),
        )
    budget.dispatch_once(a)
    budget.finish(a, "uncertain")
    with pytest.raises(BudgetExceeded, match="uncertain"):
        budget.dispatch_once(b, concurrency=8)


def test_atomic_recovery_and_operator_reconciliation(controller, command):
    run = controller.configure_run(command)
    budget = BudgetStore(controller.settings.database_path)
    identity = uuid4()
    budget.reserve(
        run.id,
        identity,
        Decimal(".2"),
        service="runpod",
        service_cap_usd=Decimal("1"),
        request_hash="test",
    )
    budget.dispatch_once(identity)
    with pytest.raises(ValueError, match="Cancel"):
        controller.recover_run(run.id)
    controller.cancel(run.id)
    recovered = controller.recover_run(run.id)
    assert recovered.accounting[0]["state"] == "uncertain"
    assert controller.recover_run(run.id) == recovered
    assert recovered.events[-1].payload[0].source == "durable-operation-recovery-v1"
    controller.reconcile_charge(identity, Decimal(".1"))
    state = Controller(controller.settings).inspect(run.id)
    assert state.accounting[0]["billed_microusd"] == 100000
    assert state.events[-1].payload[0].source == "operator-reported-billing"
    controller.reconcile_charge(identity, Decimal(".100000"))
    assert controller.inspect(run.id) == state
    with pytest.raises(ValueError, match="immutable"):
        controller.reconcile_charge(identity, Decimal(".2"))


def test_profile_version_upgrade_and_two_agents_share_credential_reference(controller):
    p = profile()
    agents = tuple(
        Agent(role=r, instructions="Version 1 instructions") for r in (Role.EXECUTOR, Role.SKEPTIC)
    )
    definitions = tuple(
        AgentDefinition(
            id=a.id, agent=a, display_name=a.role, model_profile_id=p.id, model_profile_version=1
        )
        for a in agents
    )
    legacy = p.model_dump_json(exclude={"pricing", "max_input_bytes"})
    with connection(controller.settings.database_path) as db, db:
        db.execute("INSERT INTO configurations VALUES (?,?,?,?)", ("profile", p.id, 1, legacy))
    controller.save_configuration(CouncilConfig(profiles=(p,), agents=definitions))
    # Semantic equality is idempotent without rewriting the old serialized body.
    with connection(controller.settings.database_path) as db:
        body = db.execute("SELECT body FROM configurations WHERE kind='profile'").fetchone()[0]
        assert "credential_env" in body
        assert body == legacy
    v2 = p.model_copy(update={"version": 2, "model_id": "different-model", "enabled": False})
    controller.save_configuration(CouncilConfig(profiles=(v2,)))
    report = Controller(controller.settings).validate_configuration()
    assert report.valid and {p.version for p in report.profiles} == {1, 2}
    assert all(p.credential_env == "RUNPOD_API_KEY" for p in report.profiles)


def test_response_commit_rolls_back_financial_state_if_event_is_invalid(controller, command):
    run = controller.configure_run(command)
    previous = controller.inspect(run.id).events[-1]
    budget = BudgetStore(controller.settings.database_path)
    operation = uuid4()
    budget.reserve(
        run.id,
        operation,
        Decimal(".1"),
        service="runpod",
        service_cap_usd=Decimal("1"),
        request_hash="synthetic",
    )
    budget.dispatch_once(operation)
    invalid = Event(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=previous.trajectory_id,
        sequence=1,
        type=EventType.MODEL_CALL_RECORDED,
        parent_event_ids=(uuid4(),),
        idempotency_key="invalid-financial-observation",
    )
    with pytest.raises(ValueError):
        budget.complete_call(operation, "completed", Decimal(".01"), invalid, controller.ledger)
    assert budget.operations()[0]["state"] == "in_flight"
    assert budget.operations()[0]["billed_microusd"] is None


def test_fresh_cli_api_start_without_credentials_or_container(controller, tmp_path):
    runner = CliRunner()
    folder = tmp_path / "fresh"
    assert runner.invoke(app, ["init", "--data-dir", str(folder)]).exit_code == 0
    for name in ("doctor", "validate-config", "agents", "profiles", "providers"):
        result = runner.invoke(
            app,
            [name, "--data-dir", str(folder)]
            + (["--json"] if name in {"doctor", "agents", "profiles"} else []),
        )
        assert result.exit_code == 0, result.output
        json.loads(result.output)
    with TestClient(create_app(Settings(data_dir=folder))) as client:
        status = client.get("/api/readiness")
        assert status.status_code == 200 and status.json()["external_probe_performed"] is False
        assert client.post("/api/configuration/validate", json={}).json()["valid"]
        assert client.get("/api/providers").status_code == 200
        assert client.get("/api/runs", headers={"host": "untrusted.example"}).status_code == 400
    with pytest.raises(ValidationError):
        Settings(api_host="0.0.0.0")


def test_environment_port_complete_lifecycle_and_disabled_sandbox(controller):
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    task = TaskSpec(
        id="cache-policy",
        version="1",
        environment="1",
        fixture=store.put(CacheFixture().model_dump_json().encode()),
    )
    concrete = CacheTaskAdapter(
        store, uuid4(), uuid4(), uuid4(), Candidate(policy="invalidate_all")
    )
    adapter: TaskEnvironment = concrete

    async def scenario():
        initial = await adapter.initialize(task, uuid4())
        snapshot = await adapter.snapshot()
        action = Action(id=uuid4(), tool="update", arguments_artifact=store.put(b'{"value":9}'))
        changed = await adapter.act(action)
        assert initial.evidence[0].artifacts != changed.evidence[0].artifacts
        restored = await adapter.restore(snapshot, uuid4())
        assert restored.evidence[0].artifacts[0].sha256 == initial.evidence[0].artifacts[0].sha256
        with pytest.raises(ValueError, match="allowlist"):
            await adapter.act(action.model_copy(update={"tool": "exec"}))
        await adapter.terminate()
        await adapter.terminate()
        with pytest.raises(ValueError):
            await adapter.observe()
        with pytest.raises(CapabilityUnavailable):
            await DisabledSandbox().execute(snapshot.workspace, SandboxLimits())

    asyncio.run(scenario())
    assert sandbox_status().execution_enabled is False
