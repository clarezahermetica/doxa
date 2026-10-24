import asyncio
import json
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from doxa.core.controller import ConfigureRun
from doxa.core.execution import ExecuteTask
from doxa.core.models import Agent, Experiment, ModelAssignment, ModelCall, Permissions, Role
from doxa.core.profiles import AgentDefinition, CouncilConfig, ModelProfile
from doxa.providers.contracts import ModelMessage, ModelRequest
from doxa.providers.runpod import RunPodProvider, endpoint_url
from doxa.storage.budget import BudgetExceeded, BudgetStore


def profile(**changes):
    return ModelProfile(
        id="runpod",
        provider="runpod",
        model_id="exact-test-model",
        endpoint_id="test-endpoint",
        enabled=True,
        **changes,
    )


def request():
    return ModelRequest(
        call_id=uuid4(),
        run_id=uuid4(),
        trajectory_id=uuid4(),
        agent_id=uuid4(),
        assignment=ModelAssignment(
            provider="runpod", model_id="exact-test-model", instruction_version="1"
        ),
        messages=(ModelMessage(role="user", content="cache test"),),
        max_output_tokens=100,
        timeout_seconds=1,
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://api.runpod.ai/v2/test/openai/v1",
        "https://evil.test/v2/test/openai/v1",
        "https://api.runpod.ai/v2/test/openai/v1?key=secret",
        "https://user:password@api.runpod.ai/v2/test/openai/v1",
    ],
)
def test_runpod_url_validation(url):
    with pytest.raises(ValueError):
        endpoint_url(profile().model_copy(update={"base_url": url}), {})


def test_runpod_mocked_http_preserves_metadata_and_unknown_billing(monkeypatch):
    key = "synthetic-secret-for-test-only"
    monkeypatch.setenv("RUNPOD_API_KEY", key)

    def handler(req):
        assert str(req.url) == "https://api.runpod.ai/v2/test-endpoint/openai/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer " + key
        assert json.loads(req.content)["model"] == "exact-test-model"
        return httpx.Response(
            200,
            json={
                "id": "test-response",
                "model": "exact-served-model",
                "choices": [{"message": {"content": "Echo " + key}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            },
        )

    provider = RunPodProvider(
        profile(),
        {"DOXA_RUNPOD_ENABLED": "true", "RUNPOD_API_KEY": key},
        httpx.MockTransport(handler),
    )
    response = asyncio.run(provider.generate(request()))
    assert key not in response.model_dump_json()
    assert response.response_id == "test-response"
    assert response.reported_model_id == "exact-served-model"
    assert response.usage.input_tokens == 11
    assert response.usage.billed_usd is None
    assert response.usage.latency_seconds is not None


@pytest.mark.parametrize(
    "status,category", [(401, "authentication"), (429, "quota"), (500, "transport")]
)
def test_runpod_errors_do_not_echo_headers_or_provider_bodies(status, category):
    provider = RunPodProvider(
        profile(),
        {"DOXA_RUNPOD_ENABLED": "true", "RUNPOD_API_KEY": "test"},
        httpx.MockTransport(lambda req: httpx.Response(status, text="SECRET provider diagnostics")),
    )
    response = asyncio.run(provider.generate(request()))
    assert response.error.category == category
    assert "SECRET" not in response.model_dump_json()
    assert response.usage.billed_usd is None


def test_disabled_runpod_cannot_send_http():
    def handler(req):
        raise AssertionError("Unexpected network call")

    response = asyncio.run(
        RunPodProvider(profile(), {}, httpx.MockTransport(handler)).generate(request())
    )
    assert response.error is not None


def test_configuration_is_versioned_secret_free_and_survives_reload(controller, monkeypatch):
    agent = Agent(role=Role.EXECUTOR, instructions="Test instructions")
    definition = AgentDefinition(
        id=agent.id,
        agent=agent,
        display_name="Executor A",
        model_profile_id="runpod",
        model_profile_version=1,
    )
    config = CouncilConfig(profiles=(profile(),), agents=(definition,))
    controller.save_configuration(config)
    controller.save_configuration(config)
    controller.initialize()
    assert controller.configuration() == config
    with pytest.raises(ValueError, match="immutable"):
        controller.save_configuration(
            CouncilConfig(profiles=(profile().model_copy(update={"model_id": "different-model"}),))
        )
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-value-to-reject-from-records")
    with pytest.raises(ValueError, match="Secret"):
        controller.save_configuration(
            CouncilConfig(
                agents=(
                    definition.model_copy(
                        update={"version": 2, "display_name": "secret-value-to-reject-from-records"}
                    ),
                )
            )
        )


def test_durable_dispatch_credit_cap_and_crash_reconciliation(controller, command):
    run = controller.configure_run(command)
    budgets = BudgetStore(controller.settings.database_path)
    operation = uuid4()
    budgets.reserve(
        run.id,
        operation,
        Decimal(".2"),
        service="runpod",
        service_cap_usd=Decimal("1"),
        request_hash="test-hash",
    )
    budgets.dispatch_once(operation)
    with pytest.raises(BudgetExceeded):
        BudgetStore(controller.settings.database_path).dispatch_once(operation)
    second = uuid4()
    budgets.reserve(
        run.id,
        second,
        Decimal(".2"),
        service="runpod",
        service_cap_usd=Decimal("1"),
        request_hash="second-hash",
    )
    with pytest.raises(BudgetExceeded, match="concurrency"):
        budgets.dispatch_once(second)
    budgets.reconcile(operation, Decimal(".1"))
    budgets.dispatch_once(second)
    budgets.finish(second, "uncertain")
    assert budgets.operations()[1]["billed_microusd"] is None
    with pytest.raises(BudgetExceeded, match="25"):
        budgets.reserve(
            run.id,
            uuid4(),
            Decimal(".1"),
            service="runpod",
            service_cap_usd=Decimal("26"),
            request_hash="excess-credit-cap",
        )


def test_runtime_runpod_is_guarded_and_retries_are_reserved(controller, monkeypatch):
    import doxa.core.execution as execution_module

    monkeypatch.setenv("DOXA_RUNPOD_ENABLED", "true")
    monkeypatch.setenv("RUNPOD_API_KEY", "synthetic-runpod-test-secret")
    monkeypatch.setenv("DOXA_RUNPOD_ALLOWANCE_USD", "1")
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx.Response(503, text="synthetic transient failure")
        return httpx.Response(
            200,
            json={
                "id": "mock-http",
                "model": "exact-test-model",
                "choices": [{"message": {"content": '{"policy":"invalidate_all"}'}}],
            },
        )

    real = RunPodProvider
    monkeypatch.setattr(
        execution_module, "RunPodProvider", lambda p, e: real(p, e, httpx.MockTransport(handler))
    )
    p = profile(retries=1)
    agent = Agent(
        role=Role.EXECUTOR,
        instructions="Choose a cache policy.",
        permissions=Permissions(remote_inference=True),
    )
    controller.save_configuration(
        CouncilConfig(
            profiles=(p,),
            agents=(
                AgentDefinition(
                    id=agent.id,
                    agent=agent,
                    display_name="Live HTTP boundary test",
                    model_profile_id=p.id,
                    model_profile_version=p.version,
                ),
            ),
        )
    )
    run = controller.configure_run(
        ConfigureRun(
            idempotency_key="live-http-test",
            agent_ids=(agent.id,),
            experiment=Experiment(
                name="Mocked HTTP integration; no real model",
                task_id="cache-policy",
                task_version="1",
                environment_version="1",
                policy_version="1",
                evaluator_version="1",
            ),
        )
    )
    bundle = asyncio.run(
        controller.execute_task(
            run.id, ExecuteTask(authorize_paid=True, upper_bound_usd_per_attempt=Decimal(".1"))
        )
    )
    assert bundle.run.status == "completed"
    assert len(calls) == 2
    assert len(bundle.accounting) == 2
    assert all(op["billed_microusd"] is None for op in bundle.accounting)
    assert any(
        isinstance(r, ModelCall) and r.error_category == "transport"
        for e in bundle.events
        for r in e.payload
    )
    assert "synthetic-runpod-test-secret" not in bundle.model_dump_json()


def test_live_run_without_per_call_authorization_sends_nothing(controller, monkeypatch):
    from test_runtime_stage import setup_run

    run, _ = setup_run(controller, execution_kind="live")
    with pytest.raises(PermissionError):
        asyncio.run(controller.execute_task(run.id, ExecuteTask()))
    assert controller.inspect(run.id).run.status == "failed"


def test_in_flight_provider_cancel_keeps_uncertain_charge(controller, monkeypatch):
    import doxa.core.execution as execution_module

    monkeypatch.setenv("DOXA_RUNPOD_ENABLED", "true")
    monkeypatch.setenv("RUNPOD_API_KEY", "synthetic-cancellation-secret")
    monkeypatch.setenv("DOXA_RUNPOD_ALLOWANCE_USD", "1")
    p = profile()
    agent = Agent(
        role=Role.EXECUTOR, instructions="test", permissions=Permissions(remote_inference=True)
    )
    controller.save_configuration(
        CouncilConfig(
            profiles=(p,),
            agents=(
                AgentDefinition(
                    id=agent.id,
                    agent=agent,
                    display_name="Cancel test",
                    model_profile_id=p.id,
                    model_profile_version=1,
                ),
            ),
        )
    )
    run = controller.configure_run(
        ConfigureRun(
            idempotency_key="cancel-http-test",
            agent_ids=(agent.id,),
            experiment=Experiment(
                name="Mocked cancellation",
                task_id="cache-policy",
                task_version="1",
                environment_version="1",
                policy_version="1",
                evaluator_version="1",
            ),
        )
    )

    async def scenario():
        started = asyncio.Event()

        async def handler(req):
            started.set()
            await asyncio.sleep(100)
            return httpx.Response(200)

        monkeypatch.setattr(
            execution_module,
            "RunPodProvider",
            lambda profile, env: RunPodProvider(profile, env, httpx.MockTransport(handler)),
        )
        task = asyncio.create_task(
            controller.execute_task(
                run.id, ExecuteTask(authorize_paid=True, upper_bound_usd_per_attempt=Decimal(".1"))
            )
        )
        await asyncio.wait_for(started.wait(), timeout=5)
        controller.cancel(run.id)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    bundle = controller.inspect(run.id)
    assert bundle.run.status == "cancelled"
    assert bundle.accounting[0]["state"] == "uncertain"
    assert bundle.accounting[0]["billed_microusd"] is None
    assert any(
        isinstance(r, ModelCall) and r.status == "uncertain"
        for e in bundle.events
        for r in e.payload
    )
