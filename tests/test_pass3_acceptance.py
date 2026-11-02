"""No-network preflight, terminal control and conservative model-call failure checks."""

import asyncio
import json
from decimal import Decimal

import httpx
import pytest
from test_pass3_execution import attach_mock, configured
from typer.testing import CliRunner

from doxa.cli.console import ResearchConsole
from doxa.cli.main import app
from doxa.core.models import ModelCall, RunState
from doxa.core.preflight import authorize, preflight
from doxa.core.workbench import DebateExecution, DebateRuntime
from doxa.providers.runpod import RunPodProvider
from doxa.storage.artifacts import ArtifactStore


def test_preflight_has_no_side_effects_and_launch_records_authorization(controller, monkeypatch):
    run = configured(controller)
    before = controller.inspect(run.id).model_dump_json()
    monkeypatch.setattr(
        httpx.AsyncClient, "send", lambda *a, **k: pytest.fail("Network prohibited")
    )
    report = preflight(controller, run.id)
    assert report.eligible and report.planned_requests_upper_bound == 9
    assert report.planned_rounds == 3 and not report.inference_verified
    assert report.endpoint_reachable is None and report.authorization_required == ()
    assert controller.inspect(run.id).model_dump_json() == before
    assert (
        authorize(controller, run.id, paid=False, external=False, upper_bound=None).report == report
    )
    result = CliRunner().invoke(
        app,
        [
            "run",
            "preflight",
            str(run.id),
            "--json",
            "--data-dir",
            str(controller.settings.data_dir),
        ],
    )
    assert result.exit_code == 0 and json.loads(result.stdout)["eligible"]
    monkeypatch.undo()
    attach_mock(controller, monkeypatch, run)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    state = next(
        p
        for e in bundle.events
        for p in e.payload
        if isinstance(p, RunState) and p.status == "running"
    )
    envelope = json.loads(
        ArtifactStore(controller.settings.data_dir / "artifacts").get(state.authorization)
    )
    assert envelope["report"]["run_id"] == str(run.id)
    assert envelope["report"]["limits"]["run_cap_usd"] == "1"
    assert not envelope["authorize_paid"] and not envelope["authorize_external"]
    assert envelope["uncertain_outcome_policy"] == "retain_reservation_no_replay"


def test_timeout_is_not_replayed_or_called_success(controller, monkeypatch):
    run = configured(controller)
    calls = []

    def timeout(req):
        calls.append(req)
        raise httpx.ReadTimeout("mock timeout", request=req)

    monkeypatch.setattr(
        controller.providers,
        "create",
        lambda p, env, **kw: RunPodProvider(p, env, httpx.MockTransport(timeout)),
    )
    with pytest.raises(Exception, match="timeout"):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    bundle = controller.inspect(run.id)
    assert bundle.run.status == "failed" and len(calls) == 1
    record = next(
        p
        for e in bundle.events
        for p in e.payload
        if isinstance(p, ModelCall) and p.status == "uncertain"
    )
    assert record.usage.billed_usd is None and record.billing_uncertain
    with pytest.raises(ValueError, match="already started"):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    assert len(calls) == 1


def test_terminal_preflight_and_new_attempt_at_laptop_size(controller, monkeypatch):
    run = configured(controller)
    attach_mock(controller, monkeypatch, run)
    asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))

    async def interaction():
        from textual.widgets import Select, TextArea

        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.select_experiment(run.id)
            await pilot.pause(0.3)
            app.action_preflight()
            await pilot.pause()
            await pilot.click("#tool-run")
            await pilot.pause(0.3)
            assert "Launch blocked" in app.screen.query_one("#tool-result", TextArea).text
            await pilot.press("escape")
            app.action_new_attempt()
            await pilot.pause()
            app.screen.query_one("#attempt-condition", Select).value = "same"
            await pilot.click("#attempt-save")
            await pilot.pause(0.3)
            assert app.selected != run.id
            assert controller.inspect(app.selected).run.experiment_id == run.experiment_id
            assert controller.inspect(app.selected).run.status == "configured"

    asyncio.run(interaction())


def test_remote_authorization_is_explicit_and_budget_bounded(controller, monkeypatch):
    from doxa.core.models import Experiment
    from doxa.core.profiles import CouncilConfig
    from doxa.storage.configurations import ConfigurationStore

    run = configured(controller)
    experiment = controller.ledger.get(run.experiment_id)
    assert isinstance(experiment, Experiment)
    # Separate configured remote profiles/experiment, never modify existing pinned rows.
    profiles = [
        ConfigurationStore(controller.settings.database_path).get("profile", f"mock-{i}", 1)
        for i in range(2)
    ]
    remote = tuple(
        p.model_copy(
            update={
                "id": p.id + "-remote",
                "local": False,
                "base_url": "https://mock.example/v1",
                "authentication": "none",
            }
        )
        for p in profiles
    )
    controller.save_configuration(CouncilConfig(profiles=remote))
    monkeypatch.setenv("DOXA_OPENAI_COMPATIBLE_ENABLED", "true")
    monkeypatch.setenv("DOXA_OPENAI_COMPATIBLE_ALLOWANCE_USD", "1")
    from uuid import uuid4

    from doxa.core.controller import ConfigureRun

    agents = tuple(
        a.model_copy(update={"model_profile_id": a.model_profile_id + "-remote"})
        for i, a in enumerate(experiment.agents)
    )
    configured_remote = controller.configure_run(
        ConfigureRun(
            experiment=experiment.model_copy(update={"id": uuid4(), "agents": agents}),
            mode=run.mode,
            execution_kind="live",
            idempotency_key="remote-auth",
        )
    )
    with pytest.raises(PermissionError):
        authorize(
            controller, configured_remote.id, paid=True, external=False, upper_bound=Decimal("0.1")
        )
    assert not controller.inspect(configured_remote.id).accounting
    calls = []

    def timeout(req):
        calls.append(req)
        raise httpx.ReadTimeout("mock uncertain paid call", request=req)

    monkeypatch.setattr(
        controller.providers,
        "create",
        lambda p, env, **kw: RunPodProvider(p, env, httpx.MockTransport(timeout)),
    )
    with pytest.raises(Exception, match="timeout"):
        asyncio.run(
            DebateRuntime(controller, configured_remote.id).execute_debate(
                DebateExecution(
                    authorize_paid=True,
                    authorize_external=True,
                    upper_bound_usd_per_attempt=Decimal("0.1"),
                )
            )
        )
    bundle = controller.inspect(configured_remote.id)
    assert bundle.run.status == "failed" and len(calls) == 1
    assert len(bundle.accounting) == 1
    assert bundle.accounting[0]["state"] == "uncertain"
    assert bundle.accounting[0]["reserved_microusd"] == 100000
    assert bundle.accounting[0]["billed_microusd"] is None
