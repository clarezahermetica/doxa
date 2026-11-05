"""Account CLI regression tests. Real model executables/authentication are never invoked."""

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from doxa.core.models import (
    BudgetPolicy,
    Claim,
    ContextManifest,
    CouncilLimits,
    ModelAssignment,
    ModelCall,
    ProtocolMode,
    Role,
    TaskSpecification,
)
from doxa.core.preflight import authorize, preflight
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
from doxa.providers import cli_session as cli
from doxa.providers.contracts import Capabilities, ModelMessage, ModelRequest
from doxa.storage.budget import BudgetStore
from doxa.storage.database import connection

REAL_RUN = cli.run_process
REAL_RESOLVE = cli.executable


def profile(**changes):
    return ModelProfile(
        **{
            "id": "codex-account",
            "provider": "codex_cli",
            "transport": "cli_session",
            "authentication": "cli_session",
            "credential_env": None,
            "model_id": "cli-default",
            "enabled": True,
            "max_input_bytes": 65536,
            "max_context_tokens": 65536,
            "max_output_tokens": 2048,
            "capabilities": Capabilities(text_generation="available", structured_output="native"),
            **changes,
        }
    )


@pytest.fixture(autouse=True)
def fake_cli(monkeypatch, tmp_path):
    # This intercepts every CLI provider probe and model subprocess in the module.
    # Boundary tests explicitly call REAL_RUN with Python fixture scripts only.
    cli._CHECKS.clear()
    path = str(tmp_path / "codex.exe")
    monkeypatch.setattr(cli, "executable", lambda adapter: path if adapter == "codex_cli" else None)
    state = SimpleNamespace(
        calls=[],
        flags=" ".join(cli.REQUIRED_FLAGS) + " --output-schema --output-last-message",
        auth=cli.ProcessResult(0, b"", b"Logged in using ChatGPT\n"),
        text="fixture response",
        code=0,
        stderr=b"",
        usage={"input_tokens": 12, "output_tokens": 4},
        events=None,
    )

    async def runner(argv, cwd, prompt=b"", **kwargs):
        state.calls.append((argv, Path(cwd), prompt, kwargs))
        if "--version" in argv:
            return cli.ProcessResult(0, b"codex-cli 1.2.3\n", b"")
        if "--help" in argv:
            return cli.ProcessResult(0, state.flags.encode(), b"")
        if argv[1:3] == ["features", "list"]:
            return cli.ProcessResult(
                0,
                "\n".join(
                    f"{f} stable true"
                    for f in (*cli.DISABLED_FEATURES, "skip_host_skill_discovery")
                ).encode(),
                b"",
            )
        if argv[1:3] == ["login", "status"]:
            return state.auth
        assert argv[1] == "exec" and argv[-1] == "-"
        assert not list(Path(cwd).iterdir()), "Model cwd must be empty"
        if "--output-last-message" in argv and state.code == 0:
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                state.text, encoding="utf-8"
            )
        events = (
            state.events
            if state.events is not None
            else [
                {"type": "thread.started", "model": "reported-fixture-model"},
                {"type": "item.completed", "item": {"type": "agent_message", "text": state.text}},
                {"type": "turn.completed", "usage": state.usage},
            ]
        )
        return cli.ProcessResult(
            state.code, "\n".join(map(json.dumps, events)).encode(), state.stderr
        )

    monkeypatch.setattr(cli, "run_process", runner)
    yield state
    cli._CHECKS.clear()


def request(p=None, **changes):
    p = p or profile()
    return ModelRequest(
        **{
            "call_id": uuid4(),
            "run_id": uuid4(),
            "trajectory_id": uuid4(),
            "agent_id": uuid4(),
            "assignment": ModelAssignment(
                provider=p.provider, model_id=p.model_id, instruction_version="1"
            ),
            "messages": (ModelMessage(role="user", content="PRIVATE FIXTURE PROMPT"),),
            "max_output_tokens": 512,
            "timeout_seconds": 2,
            **changes,
        }
    )


def test_version_auth_and_diagnostics_are_safe_and_never_infer(fake_cli):
    from doxa.cli.main import app

    output = CliRunner().invoke(app, ["model-clis", "--json"])
    assert output.exit_code == 0, output.output
    checks = json.loads(output.stdout)
    assert len(checks) == 4 and checks[0]["ready"]
    assert checks[0]["authentication"] == "authenticated"
    assert all(not c[2] for c in fake_cli.calls)
    assert "PRIVATE" not in output.stdout and "AppData" not in output.stdout
    assert not any(c[0][-1] == "-" for c in fake_cli.calls)


@pytest.mark.parametrize(
    "auth,expected",
    [
        (cli.ProcessResult(1, b"", b"Not logged in"), "missing"),
        (cli.ProcessResult(2, b"", b"opaque fixture failure"), "unknown"),
        (cli.ProcessResult(0, b"Logged in using an API key", b""), "unknown"),
    ],
)
def test_authentication_missing_unknown_and_api_key_are_not_session_ready(fake_cli, auth, expected):
    fake_cli.auth = auth
    checked = asyncio.run(cli.check_cli("codex_cli"))
    assert checked.authentication == expected and not checked.ready
    assert checked.login_command == "codex login"


def test_old_version_and_absent_executables_do_not_infer(fake_cli, monkeypatch):
    fake_cli.flags = "--json --sandbox"
    assert not asyncio.run(cli.check_cli("codex_cli")).supported
    monkeypatch.setattr(cli, "executable", lambda _: None)
    checks = asyncio.run(cli.check_installed_clis())
    assert all(not c.detected and not c.ready for c in checks)


def test_detected_unreviewed_adapter_is_honestly_unsupported(monkeypatch):
    monkeypatch.setattr(cli, "executable", lambda _: "fixture-gemini.exe")
    checked = asyncio.run(cli.check_cli("gemini_cli"))
    assert checked.detected and not checked.supported and not checked.ready


def test_windows_resolution_uses_native_allowlisted_exe_without_shell_shims(monkeypatch):
    seen = []
    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", "win32")
        patch.setenv("PATH", os.pathsep.join([".", str(Path(sys.executable).parent)]))
        patch.setattr(cli.shutil, "which", lambda name, **kw: seen.append((name, kw)) or None)
        assert REAL_RESOLVE("codex_cli") is None
    assert Path(seen[0][0]).name == "codex.exe" and "." not in seen[0][1]["path"].split(os.pathsep)


def test_stdin_isolation_schema_arguments_model_and_unknown_usd(fake_cli):
    p = profile(model_id="exact-fixture-model")
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    fake_cli.text = '{"answer":"fixture"}'
    response = asyncio.run(cli.CodexCliProvider(p).generate(request(p, response_schema=schema)))
    assert response.error is None and response.completion_state == "completed"
    assert response.reported_model_id == "reported-fixture-model"
    assert response.usage.input_tokens == 12 and response.usage.output_tokens == 4
    assert response.usage.billed_usd is None and response.usage.estimated_usd is None
    argv, cwd, prompt, _ = fake_cli.calls[-1]
    assert b"PRIVATE FIXTURE PROMPT" in prompt and not any("PRIVATE" in a for a in argv)
    assert not cwd.exists() and "--model" in argv and "exact-fixture-model" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in argv and "--ignore-rules" in argv
    assert "--output-schema" in argv and "--output-last-message" in argv
    assert "shell_tool" in argv and "computer_use" in argv and "multi_agent" in argv
    assert not any("model_providers.openai." in argument for argument in argv)
    assert "unbounded_connection_retries" in argv


def test_plain_final_fallback_default_model_and_unknown_usage(fake_cli):
    fake_cli.flags = " ".join(cli.REQUIRED_FLAGS)
    fake_cli.usage = None
    response = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert response.text == fake_cli.text and response.usage.input_tokens is None
    argv = fake_cli.calls[-1][0]
    assert "--model" not in argv and "--output-last-message" not in argv
    assert response.usage.billed_usd is None


@pytest.mark.parametrize(
    "events,state,error",
    [
        (
            [{"type": "item.completed", "item": {"type": "agent_message", "text": "partial"}}],
            "incomplete",
            None,
        ),
        (
            [
                {"type": "item.completed", "item": {"type": "refusal", "text": "refused"}},
                {"type": "turn.completed"},
            ],
            "refused",
            None,
        ),
        ([{"type": "turn.failed", "error": {"message": "quota exceeded"}}], None, "quota"),
        ([{"type": "error", "message": "authentication failed"}], None, "authentication"),
        (
            [{"type": "item.completed", "item": {"type": "command_execution"}}],
            None,
            "invalid_response",
        ),
    ],
)
def test_incomplete_refusal_failure_and_unexpected_native_tools(fake_cli, events, state, error):
    fake_cli.events = events
    fake_cli.flags = " ".join(cli.REQUIRED_FLAGS)
    result = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert result.error.category == error if error else result.completion_state == state


@pytest.mark.parametrize(
    "message,category",
    [
        (b"quota limit exceeded", "quota"),
        (b"authentication expired", "authentication"),
        (b"unexpected argument fixture", "configuration"),
        (b"connection reset", "transport"),
    ],
)
def test_nonzero_errors_are_sanitized_and_not_retried(fake_cli, message, category):
    fake_cli.code = 1
    fake_cli.stderr = message + b" SECRET-THAT-MUST-NOT-BE-LOGGED"
    result = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert result.error.category == category and not result.error.retryable
    assert "SECRET" not in result.model_dump_json()
    assert len([c for c in fake_cli.calls if c[0][-1] == "-"]) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"credential_env": "SOME_KEY"},
        {"base_url": "https://example.org"},
        {"retries": 1},
        {"concurrency": 2},
        {"authentication": "none"},
        {"local": True},
    ],
)
def test_cli_profiles_reject_api_semantics_and_unsafe_retry_concurrency(changes):
    with pytest.raises(ValueError):
        profile(**changes)


def test_old_http_profile_defaults_and_all_registered_transports_remain_available():
    from doxa.providers.registry import ProviderRegistry

    old = ModelProfile.model_validate({"id": "old", "provider": "openai", "model_id": "exact"})
    assert old.transport == "http" and old.authentication == "bearer"
    assert old.credential_env == "RUNPOD_API_KEY"
    supported = {d.provider for d in ProviderRegistry().descriptors() if d.implemented}
    assert {"openai", "claude", "gemini", "openai_compatible", "runpod", "codex_cli"} <= supported


def configured(controller, fake_cli, *, profile_id="codex-account", timeout=30):
    p = profile(id=profile_id, timeout_seconds=timeout)
    controller.save_configuration(CouncilConfig(profiles=(p,)))
    actor = add_agent(
        controller,
        NewAgent(
            display_name="Reader",
            role=Role.RESEARCHER,
            instructions="Use only supplied evidence.",
            profile_id=p.id,
            profile_version=1,
            remote_inference=True,
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Offline fake CLI acceptance",
            execution_kind="live",
            mode=ProtocolMode.SOLO_DIRECT,
            task=TaskSpecification(
                question="What does the fixture say?",
                structured_actions=True,
                council=CouncilLimits(rounds=1, max_calls=1),
            ),
            participants=(ParticipantGroup(agent_id=actor.id),),
            budget=BudgetPolicy(max_model_calls=1),
            idempotency_key=str(uuid4()),
        ),
    )
    source = import_source(
        controller,
        run.id,
        ImportSource(
            title="Local fixture",
            text="The fixture marker is amber.",
            idempotency_key="source",
        ),
    )
    fake_cli.text = json.dumps(
        {
            "research_action": {
                "operation": "claim",
                "proposition": "The fixture marker is amber.",
                "source_ids": [str(source.id)],
                "revises_id": None,
            }
        }
    )
    return run, source


def test_real_controller_cli_path_persists_quota_not_usd_claim_and_context(controller, fake_cli):
    from doxa.cli.main import app

    run, source = configured(controller, fake_cli)
    cli._CHECKS.clear()  # A fresh CLI process must be able to explicitly refresh readiness.
    output = CliRunner().invoke(
        app,
        [
            "run",
            "preflight",
            str(run.id),
            "--data-dir",
            str(controller.settings.data_dir),
            "--check-clis",
            "--json",
        ],
    )
    assert output.exit_code == 0, output.output
    assert json.loads(output.stdout)["eligible"]
    assert not any(call[0][-1] == "-" for call in fake_cli.calls)
    report = preflight(controller, run.id)
    assert report.eligible and report.authorization_required == (
        "authorize_external",
        "authorize_quota",
    )
    assert report.participants[0]["endpoint"] is None
    with pytest.raises(PermissionError):
        authorize(controller, run.id, paid=True, external=True, upper_bound=None)
    authorize(controller, run.id, paid=False, external=True, upper_bound=None, quota=True)
    bundle = asyncio.run(
        DebateRuntime(controller, run.id).execute_debate(
            DebateExecution(authorize_external=True, authorize_quota=True)
        )
    )
    assert bundle.run.status == "completed"
    calls = [p for e in bundle.events for p in e.payload if isinstance(p, ModelCall)]
    assert [c.status for c in calls] == ["started", "completed"]
    assert all(
        c.accounting_basis == "subscription_quota"
        and c.usage.billed_usd is None
        and c.usage.estimated_usd is None
        for c in calls
    )
    assert any(
        isinstance(p, Claim) and p.proposition == "The fixture marker is amber."
        for e in bundle.events
        for p in e.payload
    )
    assert any(
        isinstance(p, ContextManifest) and source.id in p.source_ids
        for e in bundle.events
        for p in e.payload
    )
    operations = BudgetStore(controller.settings.database_path).operations()
    assert len(operations) == 1 and operations[0]["state"] == "completed"
    assert operations[0]["billed_microusd"] is None and operations[0]["reserved_microusd"] is None
    with connection(controller.settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 0
    with pytest.raises(ValueError):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(
                DebateExecution(authorize_external=True, authorize_quota=True)
            )
        )


@pytest.mark.parametrize("external,quota", [(False, False), (True, False), (False, True)])
def test_external_disclosure_and_quota_acknowledgment_are_both_mandatory(
    controller, fake_cli, external, quota
):
    run, _ = configured(controller, fake_cli)
    with pytest.raises(PermissionError):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(
                DebateExecution(authorize_external=external, authorize_quota=quota)
            )
        )
    assert controller.inspect(run.id).run.status == "configured"
    assert not BudgetStore(controller.settings.database_path).operations()


def test_uncertain_quota_call_is_durable_and_blocks_other_profile_attempts(controller, fake_cli):
    from doxa.core.execution import ProviderCallFailed

    run, _ = configured(controller, fake_cli)
    fake_cli.code = 1
    fake_cli.stderr = b"connection reset"
    with pytest.raises(ProviderCallFailed):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(
                DebateExecution(authorize_external=True, authorize_quota=True)
            )
        )
    operations = BudgetStore(controller.settings.database_path).operations()
    assert operations[0]["state"] == "uncertain" and operations[0]["reserved_calls"] == 1
    assert operations[0]["quota_consumed"] is None
    controller.recover_run(run.id)
    assert BudgetStore(controller.settings.database_path).operations()[0] == operations[0]
    second, _ = configured(controller, fake_cli, profile_id="other-codex-account-profile")
    with pytest.raises(ValueError, match="uncertain-operation"):
        asyncio.run(
            DebateRuntime(controller, second.id).execute_debate(
                DebateExecution(authorize_external=True, authorize_quota=True)
            )
        )


@pytest.mark.parametrize("channel", ["stdout", "stderr", "events"])
def test_actual_subprocess_stream_limits(channel, tmp_path):
    code = {
        "stdout": "import sys; sys.stdout.write('x'*9000)",
        "stderr": "import sys; sys.stderr.write('x'*9000)",
        "events": "print('x\\n'*20)",
    }[channel]
    with pytest.raises(cli.StreamLimit):
        asyncio.run(
            REAL_RUN(
                [sys.executable, "-c", code],
                tmp_path,
                timeout=5,
                stdout_limit=128,
                stderr_limit=128,
                events=4,
            )
        )


def test_actual_subprocess_stdin_cwd_and_minimal_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-fixture-key")
    monkeypatch.setenv("MOSS_PROJECT_KEY", "private-fixture-key")
    monkeypatch.setenv("NODE_OPTIONS", "private-fixture-key")
    code = (
        "import os,sys,json; print(json.dumps({'cwd':os.getcwd(), 'files':os.listdir('.'),"
        "'secret':any(k in os.environ for k in ['OPENAI_API_KEY','MOSS_PROJECT_KEY',"
        "'NODE_OPTIONS']), 'input':sys.stdin.read()}))"
    )
    result = asyncio.run(
        REAL_RUN([sys.executable, "-c", code], tmp_path, b"fixture stdin", timeout=5)
    )
    body = json.loads(result.stdout)
    assert Path(body["cwd"]) == tmp_path and body["files"] == [] and not body["secret"]
    assert body["input"] == "fixture stdin"


def test_actual_subprocess_timeout_and_cancellation_leave_no_child(tmp_path):
    async def test():
        active = {}
        identity = uuid4()
        with pytest.raises(TimeoutError):
            await REAL_RUN(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                tmp_path,
                timeout=0.1,
                active=active,
                call_id=identity,
            )
        assert not active
        task = asyncio.create_task(
            REAL_RUN(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                tmp_path,
                timeout=20,
                active=active,
                call_id=identity,
            )
        )
        for _ in range(100):
            if active:
                break
            await asyncio.sleep(0.01)
        child = active[identity]
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert child.returncode is not None and not active

    asyncio.run(test())


@pytest.mark.parametrize("stubborn", [False, True])
def test_force_kill_only_after_termination_grace_expires(stubborn):
    class Child:
        returncode = None

        def __init__(self):
            self.steps = []

        def terminate(self):
            self.steps.append("terminate")

        def kill(self):
            self.steps.append("kill")
            self.returncode = -9

        async def wait(self):
            self.steps.append("wait")
            if stubborn and self.returncode is None:
                raise TimeoutError
            self.returncode = 0
            return 0

    child = Child()
    asyncio.run(cli.stop_process(child))
    assert child.steps == (
        ["terminate", "wait", "kill", "wait"] if stubborn else ["terminate", "wait"]
    )


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"type": "item.completed", "item": None},
        {"type": "turn.completed", "usage": {"input_tokens": True}},
    ],
)
def test_malformed_events_fail_closed_without_raw_output(fake_cli, body):
    fake_cli.events = [body]
    result = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert result.error.category == "invalid_response"


def test_quota_admission_and_started_record_are_atomic(controller, fake_cli, monkeypatch):
    run, _ = configured(controller, fake_cli)
    original = controller.ledger._append

    def fail_start(event, db):
        if any(isinstance(p, ModelCall) and p.status == "started" for p in event.payload):
            raise OSError("injected quota admission interruption")
        return original(event, db)

    monkeypatch.setattr(controller.ledger, "_append", fail_start)
    with pytest.raises(OSError, match="injected"):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(
                DebateExecution(authorize_external=True, authorize_quota=True)
            )
        )
    assert not BudgetStore(controller.settings.database_path).operations()
    assert not any(c[0][-1] == "-" for c in fake_cli.calls)


def test_quota_operations_survive_verified_workspace_restore(
    controller, fake_cli, tmp_path_factory
):
    from doxa.storage.backup import backup_workspace, restore_workspace

    run, _ = configured(controller, fake_cli)
    asyncio.run(
        DebateRuntime(controller, run.id).execute_debate(
            DebateExecution(authorize_external=True, authorize_quota=True)
        )
    )
    before = BudgetStore(controller.settings.database_path).operations()
    tmp_path = tmp_path_factory.mktemp("quota-recovery")
    backup_workspace(controller.settings.data_dir, tmp_path / "backup")
    restore_workspace(tmp_path / "backup", tmp_path / "restored")
    assert BudgetStore(tmp_path / "restored/ledger.sqlite3").operations() == before


def test_model_form_saves_session_without_credentials_allowance_or_inference(
    controller, fake_cli, monkeypatch, tmp_path
):
    from textual.widgets import Checkbox, Input, Select

    from doxa.cli.console import ResearchConsole
    from doxa.cli.model_setup import ModelScreen

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))

    async def test():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            screen = ModelScreen(app.controller)
            app.push_screen(screen)
            await pilot.pause()
            screen.query_one("#model-connection", Select).value = "codex_cli"
            await pilot.pause()
            assert screen.query_one("#model-id", Input).value == "cli-default"
            assert not screen.query_one("#auth-fields").display
            assert not screen.query_one("#credential-fields").display
            assert not screen.query_one("#url-fields").display
            assert not screen.query_one("#model-allowance").display
            assert screen.query_one("#model-concurrency", Input).value == "1"
            screen.query_one("#model-name", Input).value = "saved-cli"
            screen.query_one("#model-reasoning", Select).value = "low"
            screen.query_one("#model-enabled", Checkbox).value = True
            await pilot.pause()
            await screen.save()
            await pilot.pause()
        saved = app.controller.configuration().profiles[0]
        assert saved.transport == "cli_session" and saved.credential_env is None
        assert saved.pricing is None and saved.retries == 0 and saved.concurrency == 1
        assert saved.base_url is None
        assert saved.reasoning == {"effort": "low"}
        assert not (controller.settings.data_dir / "runtime-settings.json").exists()
        assert not (controller.settings.data_dir / "credentials").exists()

    asyncio.run(test())
    assert not fake_cli.calls, "Saving must not invoke even local probes"


def test_tui_start_and_worker_argv_carry_quota_authorization_without_usd(
    controller, fake_cli, monkeypatch, tmp_path
):
    from textual.widgets import Checkbox

    from doxa.cli import operations
    from doxa.cli.console import ResearchConsole
    from doxa.cli.operations import StartScreen, start_worker

    run, _ = configured(controller, fake_cli)
    asyncio.run(cli.check_installed_clis())
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))
    spawned = []
    monkeypatch.setattr(
        operations.subprocess, "Popen", lambda argv, **kw: spawned.append((argv, kw))
    )

    async def test():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            screen = StartScreen(app.controller, run.id)
            app.push_screen(screen)
            await pilot.pause()
            assert screen.query_one("#start-quota").display
            assert not screen.query_one("#start-paid").display
            assert not screen.query_one("#start-bound").display
            screen.query_one("#start-external", Checkbox).value = True
            screen.query_one("#start-quota", Checkbox).value = True
            from textual.widgets import Button

            screen.on_button_pressed(Button.Pressed(screen.query_one("#start-save", Button)))
            await pilot.pause()

    asyncio.run(test())
    assert spawned and "--authorize-quota" in spawned[0][0]
    assert "--authorize-external" in spawned[0][0] and "--authorize-paid" not in spawned[0][0]
    assert "--upper-bound" not in spawned[0][0]
    assert start_worker


def test_api_accepts_quota_without_paid_authorization_and_persists_result(controller, fake_cli):
    import time

    from fastapi.testclient import TestClient

    from doxa.api.app import create_app

    run, _ = configured(controller, fake_cli)
    asyncio.run(cli.check_installed_clis())
    with TestClient(create_app(controller.settings)) as client:
        denied = client.post(
            f"/api/workbench/runs/{run.id}/start",
            json={"authorize_external": True, "authorize_paid": True},
        )
        assert denied.status_code == 403
        accepted = client.post(
            f"/api/workbench/runs/{run.id}/start",
            json={"authorize_external": True, "authorize_quota": True},
        )
        assert accepted.status_code == 202, accepted.text
        for _ in range(100):
            if controller.inspect(run.id).run.status in {"completed", "failed"}:
                break
            time.sleep(0.02)
        assert controller.inspect(run.id).run.status == "completed"
    assert BudgetStore(controller.settings.database_path).operations()[0]["billed_microusd"] is None


def test_quota_preflight_explains_unknown_cost_instead_of_zero(controller, fake_cli):
    from doxa.core.preflight import format_preflight

    run, _ = configured(controller, fake_cli)
    asyncio.run(cli.check_installed_clis())
    report = format_preflight(preflight(controller, run.id))
    assert "USD billing unavailable, not zero" in report
    assert "Run spending ceiling USD" not in report


def test_outer_timeout_is_uncertain_and_never_retried(fake_cli, monkeypatch):
    async def slow_check(_):
        await asyncio.sleep(10)

    monkeypatch.setattr(cli, "check_cli", slow_check)
    p = profile(timeout_seconds=0.01)
    result = asyncio.run(cli.CodexCliProvider(p).generate(request(p)))
    assert result.error.category == "timeout"
    assert result.error.billing_uncertain and not result.error.retryable
    assert not fake_cli.calls


def test_final_size_rejection_preserves_observed_usage(fake_cli):
    fake_cli.text = "x" * 513
    result = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert result.error.category == "invalid_response"
    assert result.usage.input_tokens == 12 and result.usage.output_tokens == 4


def test_native_schema_missing_fails_before_model_dispatch(fake_cli):
    fake_cli.flags = " ".join(cli.REQUIRED_FLAGS)
    result = asyncio.run(
        cli.CodexCliProvider(profile()).generate(request(response_schema=cli.research_schema()))
    )
    assert result.error.category == "unsupported" and not result.error.billing_uncertain
    assert not any(call[0][-1] == "-" for call in fake_cli.calls)


def test_disabled_cli_profile_and_oversized_input_never_spawn(fake_cli):
    with pytest.raises(PermissionError, match="disabled"):
        asyncio.run(cli.CodexCliProvider(profile(enabled=False)).generate(request()))
    with pytest.raises(ValueError, match="input size"):
        asyncio.run(cli.CodexCliProvider(profile(max_input_bytes=1)).generate(request()))
    assert not fake_cli.calls


def test_cli_exit_without_turn_completion_retains_uncertain_quota(controller, fake_cli):
    from doxa.core.execution import ProviderCallFailed

    run, _ = configured(controller, fake_cli)
    fake_cli.events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": fake_cli.text}}
    ]
    with pytest.raises(ProviderCallFailed, match="incomplete"):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(
                DebateExecution(authorize_external=True, authorize_quota=True)
            )
        )
    bundle = controller.inspect(run.id)
    assert bundle.run.status == "failed"
    calls = [p for e in bundle.events for p in e.payload if isinstance(p, ModelCall)]
    assert calls[-1].status == "uncertain" and calls[-1].completion_state == "incomplete"
    assert calls[-1].billing_uncertain
    assert BudgetStore(controller.settings.database_path).operations()[0]["state"] == "uncertain"
    assert len([c for c in fake_cli.calls if c[0][-1] == "-"]) == 1


@pytest.mark.parametrize("kind", ["synthetic", "replay"])
def test_non_live_records_cannot_dispatch_cli_inference(controller, fake_cli, kind):
    from doxa.core.execution import ExecuteTask, Runtime

    run, _ = configured(controller, fake_cli)
    runtime = Runtime(controller, run.id)
    runtime.run = runtime.run.model_copy(update={"execution_kind": kind})
    runtime.command = ExecuteTask(authorize_external=True, authorize_quota=True)
    with pytest.raises(PermissionError, match="Synthetic and replay"):
        asyncio.run(
            runtime.model_text(
                runtime.experiment.agents[0], "not-live", (ModelMessage(role="user", content="x"),)
            )
        )
    assert not fake_cli.calls


def test_paid_admission_cannot_ignore_prior_quota_call_in_same_run(controller, fake_cli):
    from decimal import Decimal

    from doxa.storage.budget import BudgetExceeded

    run, _ = configured(controller, fake_cli)
    asyncio.run(
        DebateRuntime(controller, run.id).execute_debate(
            DebateExecution(authorize_external=True, authorize_quota=True)
        )
    )
    budget = BudgetStore(controller.settings.database_path)
    with pytest.raises(BudgetExceeded, match="call limit"):
        budget.reserve(
            run.id,
            uuid4(),
            Decimal("0.01"),
            service="openai",
            service_cap_usd=Decimal("1"),
            request_hash="separate-mocked-paid-operation",
            max_calls=1,
        )
    assert len(budget.operations()) == 1
    with connection(controller.settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 0


def test_cli_request_respects_smaller_experiment_timeout(controller, fake_cli):
    run, _ = configured(controller, fake_cli, timeout=60)
    asyncio.run(
        DebateRuntime(controller, run.id).execute_debate(
            DebateExecution(authorize_external=True, authorize_quota=True)
        )
    )
    invocation = next(call for call in fake_cli.calls if call[0][-1] == "-")
    assert invocation[3]["timeout"] == 30


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
def test_explicit_cli_reasoning_effort_is_allowlisted_and_recorded(fake_cli, effort):
    p = profile(reasoning={"effort": effort})
    response = asyncio.run(cli.CodexCliProvider(p).generate(request(p)))
    assert response.error is None
    assert 'model_reasoning_effort="' + effort + '"' in fake_cli.calls[-1][0]
    assert response.raw_response["requested_reasoning_effort"] == effort
    assert response.raw_response["native_retry_policy"] == "client_managed_not_pinned"


@pytest.mark.parametrize(
    "reasoning", [{"effort": "auto"}, {"effort": "ultra"}, {"effort": "low", "command": "unsafe"}]
)
def test_unsupported_cli_reasoning_is_rejected_before_dispatch(fake_cli, reasoning):
    with pytest.raises(ValueError):
        cli.validate_cli_profile(profile(reasoning=reasoning))
    assert not fake_cli.calls


def test_reserved_provider_error_is_safe_incomplete_and_pre_request(fake_cli):
    fake_cli.code = 1
    fake_cli.events = []
    fake_cli.stderr = (
        b"Error loading config.toml: model_providers contains reserved built-in "
        b"provider IDs: `openai`. PRIVATE SECRET FIXTURE"
    )
    response = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert response.error.category == "configuration"
    assert not response.error.billing_uncertain and not response.error.retryable
    assert response.completion_state == "incomplete"
    assert response.raw_response["diagnostic_code"] == "reserved_builtin_provider"
    assert response.raw_response["exit_code"] == 1
    assert response.raw_response["cli_version"] == "1.2.3"
    assert "PRIVATE" not in response.model_dump_json()
    assert len([call for call in fake_cli.calls if call[0][-1] == "-"]) == 1


def test_unrecognized_failure_remains_uncertain_and_sanitized(fake_cli):
    fake_cli.code = 1
    fake_cli.stderr = b"PRIVATE SECRET FIXTURE"
    response = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert response.error.billing_uncertain
    assert response.completion_state == "incomplete"
    assert "PRIVATE" not in response.model_dump_json()


def test_real_fixture_process_identity_is_recorded(tmp_path):
    observed = []
    result = asyncio.run(
        REAL_RUN([sys.executable, "-c", "print('fixture')"], tmp_path, on_spawn=observed.append)
    )
    assert result.code == 0 and result.stdout.strip() == b"fixture"
    assert observed == [result.pid] and result.pid > 0


def test_startup_error_text_with_started_events_cannot_clear_uncertainty(fake_cli):
    fake_cli.code = 1
    fake_cli.stderr = b"Error loading config.toml: invalid config"
    fake_cli.events = [{"type": "thread.started"}]
    response = asyncio.run(cli.CodexCliProvider(profile()).generate(request()))
    assert response.error.billing_uncertain
    assert response.completion_state == "incomplete"


def test_known_local_startup_failure_has_durable_failed_not_uncertain_admission(
    controller, fake_cli
):
    from doxa.core.execution import ProviderCallFailed

    run, _ = configured(controller, fake_cli)
    fake_cli.code = 1
    fake_cli.events = []
    fake_cli.stderr = b"Error loading config.toml: invalid CLI configuration"
    with pytest.raises(ProviderCallFailed):
        asyncio.run(
            DebateRuntime(controller, run.id).execute_debate(
                DebateExecution(authorize_external=True, authorize_quota=True)
            )
        )
    operation = BudgetStore(controller.settings.database_path).operations()[0]
    assert operation["state"] == "failed"
    assert operation["quota_consumed"] is None and operation["billed_microusd"] is None
    calls = [
        r for e in controller.inspect(run.id).events for r in e.payload if isinstance(r, ModelCall)
    ]
    assert calls[-1].completion_state == "incomplete" and not calls[-1].billing_uncertain
