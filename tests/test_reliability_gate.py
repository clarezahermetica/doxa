"""Reliability tests operate only on isolated ledgers and dummy credentials."""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from doxa.cli.console import ResearchConsole

CHILD = Path(__file__).with_name("reliability_child.py")


def spawn_probe(mode, workspace, marker, *extra, window=False):
    env = dict(os.environ, LOCALAPPDATA=str(marker.parent / "client"), PYTHONUTF8="1")
    env.update(DOXA_OPENAI_COMPATIBLE_ENABLED="true", DOXA_OPENAI_COMPATIBLE_ALLOWANCE_USD="1")
    startup = None
    flags = 0
    if window:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        flags = subprocess.CREATE_NEW_CONSOLE
    log = marker.with_suffix(".log").open("wb")
    try:
        return subprocess.Popen(
            [sys.executable, str(CHILD), mode, str(workspace), str(marker), *map(str, extra)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            env=env,
            startupinfo=startup,
            creationflags=flags,
        )
    finally:
        log.close()


def acknowledged(child, marker):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if marker.exists():
            try:
                value = json.loads(marker.read_text())
                assert value["pid"] == child.pid or value["parent_pid"] == child.pid
                child.actual_pid = value["pid"]
                return value
            except ValueError:
                pass
        if child.poll() is not None:
            pytest.fail(marker.with_suffix(".log").read_text(errors="replace")[-2000:])
        time.sleep(0.03)
    pytest.fail("Owned fault-injection process did not reach its checkpoint")


def stop(child):
    import signal

    actual = getattr(child, "actual_pid", child.pid)
    if actual != child.pid and child.poll() is None:
        try:
            os.kill(actual, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if child.poll() is None:
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
    child.wait(timeout=15)


def test_theme_survives_normal_exit(controller, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))

    async def scenario():
        first = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with first.run_test(size=(80, 24)) as pilot:
            assert "nord" in first.available_themes
            from textual.theme import ThemeProvider

            dict(ThemeProvider(first.screen).commands)["nord"]()
            await pilot.pause()
        second = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with second.run_test(size=(80, 24)):
            assert second.theme == "nord"

    asyncio.run(scenario())


def test_credential_flush_failure_cannot_publish_partial_secret(tmp_path, monkeypatch):
    import os

    from doxa.core import credential_store

    monkeypatch.setattr(credential_store, "_protect", lambda data: b"dummy-encrypted-value")

    def failed_flush(fd):
        raise OSError("injected durable-write failure")

    monkeypatch.setattr(os, "fsync", failed_flush)
    with pytest.raises(OSError, match="injected"):
        credential_store.save_credential(tmp_path, "FIXTURE_KEY", "dummy-value")
    assert not (tmp_path / "credentials/FIXTURE_KEY.dpapi").exists()


def test_runtime_guard_flush_failure_preserves_existing_settings(tmp_path, monkeypatch):
    import os

    from doxa.core.secrets import configure_runtime_guard

    path = tmp_path / "runtime-settings.json"
    original = json.dumps({"DOXA_OPENAI_ENABLED": "false", "keep": "existing"}).encode()
    path.write_bytes(original)

    def failed_flush(fd):
        raise OSError("injected durable-write failure")

    monkeypatch.setattr(os, "fsync", failed_flush)
    with pytest.raises(OSError, match="injected"):
        configure_runtime_guard(tmp_path, "openai", "1")
    assert path.read_bytes() == original


def test_theme_survives_abrupt_viewer_termination(controller, tmp_path, monkeypatch):
    marker = tmp_path / "theme-ready.json"
    child = spawn_probe("theme", controller.settings.data_dir, marker)
    try:
        assert acknowledged(child, marker)["theme"] == "nord"
    finally:
        stop(child)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))
    assert ResearchConsole(controller.settings.data_dir, show_guide=False).theme == "nord"


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows console-window closure")
def test_theme_survives_console_window_close(controller, tmp_path, monkeypatch):
    import ctypes

    marker = tmp_path / "window-ready.json"
    child = spawn_probe("window", controller.settings.data_dir, marker, window=True)
    try:
        state = acknowledged(child, marker)
        assert state["hwnd"] and state["theme"] == "nord"
        post = ctypes.windll.user32.PostMessageW
        post.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        assert post(state["hwnd"], 0x0010, None, None)  # WM_CLOSE on this child's console only
        child.wait(timeout=15)
        assert child.poll() is not None
    finally:
        stop(child)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))
    assert ResearchConsole(controller.settings.data_dir, show_guide=False).theme == "nord"


@pytest.mark.parametrize("mode", ["ledger", "configuration"])
def test_process_death_before_commit_rolls_back_whole_transaction(
    controller, command, tmp_path, mode
):
    from doxa.core.config import Settings
    from doxa.core.controller import Controller
    from doxa.storage.integrity import verify_workspace

    controller.configure_run(command)
    before = controller.list_runs()
    events = controller.inspect(before[0].id)
    config = controller.configuration()
    marker = tmp_path / (mode + "-ready.json")
    child = spawn_probe(mode, controller.settings.data_dir, marker)
    try:
        acknowledged(child, marker)
        # A separate reader sees the last committed state even while the writer is alive.
        assert controller.configuration() == config
        assert controller.list_runs() == before
    finally:
        stop(child)
    reopened = Controller(Settings(data_dir=controller.settings.data_dir))
    reopened.initialize()
    assert reopened.configuration() == config
    assert reopened.list_runs() == before
    assert reopened.inspect(before[0].id) == events
    assert verify_workspace(reopened.settings.data_dir)["events"] == len(events.events)


def test_worker_death_with_pending_request_preserves_hold_and_never_replays(controller, tmp_path):
    from uuid import uuid4

    from test_pass3_execution import configured

    from doxa.core.config import Settings
    from doxa.core.controller import ConfigureRun, Controller
    from doxa.core.profiles import CouncilConfig
    from doxa.core.workbench import DebateExecution, DebateRuntime
    from doxa.storage.budget import BudgetStore
    from doxa.storage.workers import worker_lease

    local = configured(controller)
    experiment = controller.ledger.get(local.experiment_id)
    profiles = tuple(
        p.model_copy(
            update={"id": p.id + "-remote", "local": False, "base_url": "https://mock.invalid/v1"}
        )
        for p in controller.configuration().profiles
    )
    controller.save_configuration(CouncilConfig(profiles=profiles))
    agents = tuple(
        a.model_copy(update={"model_profile_id": a.model_profile_id + "-remote"})
        for a in experiment.agents
    )
    run = controller.configure_run(
        ConfigureRun(
            experiment=experiment.model_copy(update={"id": uuid4(), "agents": agents}),
            execution_kind="live",
            mode=local.mode,
            idempotency_key="pending-request",
        )
    )
    marker = tmp_path / "pending-ready.json"
    worker = spawn_probe("pending", controller.settings.data_dir, marker, run.id)
    viewer = None
    try:
        state = acknowledged(worker, marker)
        assert state["operation_id"]
        viewer_marker = tmp_path / "viewer-ready.json"
        viewer = spawn_probe("viewer", controller.settings.data_dir, viewer_marker)
        acknowledged(viewer, viewer_marker)
        stop(viewer)
        assert worker.poll() is None
        assert controller.inspect(run.id).run.status == "running"
        with pytest.raises(ValueError, match="owns"):
            with worker_lease(controller.settings.data_dir, run.id):
                pytest.fail("Worker ownership was lost with the viewer")
        with pytest.raises(ValueError, match="owns"):
            controller.recover_run(run.id)
    finally:
        if viewer:
            stop(viewer)
        stop(worker)
    restarted = Controller(Settings(data_dir=controller.settings.data_dir))
    restarted.initialize()
    operations = BudgetStore(restarted.settings.database_path).operations()
    assert operations[0]["state"] == "in_flight"
    assert operations[0]["billed_microusd"] is None
    with pytest.raises(ValueError, match="Cancel"):
        restarted.recover_run(run.id)
    restarted.cancel(run.id)
    recovered = restarted.recover_run(run.id)
    held = BudgetStore(restarted.settings.database_path).operations()[0]
    assert held["state"] == "uncertain" and held["reserved_microusd"] == 100000
    assert held["billed_microusd"] is None
    assert restarted.recover_run(run.id) == recovered
    with pytest.raises(ValueError, match="already started"):
        asyncio.run(DebateRuntime(restarted, run.id).execute_debate(DebateExecution()))
    assert BudgetStore(restarted.settings.database_path).operations()[0] == held


def test_corrupt_appearance_and_publication_failure_preserve_last_settings(
    controller, tmp_path, monkeypatch
):
    from doxa.cli.appearance import appearance_path, save_theme
    from doxa.core import local_files

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))
    save_theme("nord")
    previous = appearance_path().read_bytes()

    def fail_replace(*args):
        raise OSError("injected replace failure")

    with monkeypatch.context() as patch:
        patch.setattr(local_files.os, "replace", fail_replace)
        with pytest.raises(OSError, match="injected"):
            save_theme("monokai")
    assert appearance_path().read_bytes() == previous
    assert not list(appearance_path().parent.glob("appearance.json-*.tmp"))
    appearance_path().write_bytes(b'{"version":')
    broken = appearance_path().read_bytes()
    app = ResearchConsole(controller.settings.data_dir, show_guide=False)
    assert app.appearance_error and appearance_path().read_bytes() == broken
    with pytest.raises(ValueError):
        save_theme("nord")
    assert appearance_path().read_bytes() == broken


def test_all_committed_state_survives_restore_and_unsaved_forms_are_transient(
    controller, tmp_path, monkeypatch
):
    import hashlib
    import sqlite3
    from decimal import Decimal
    from uuid import uuid4

    from test_pass3_execution import configured

    from doxa.core.config import Settings
    from doxa.core.controller import Controller
    from doxa.storage.artifacts import ArtifactStore
    from doxa.storage.backup import backup_workspace, restore_workspace
    from doxa.storage.budget import BudgetStore

    run = configured(controller)
    budget = BudgetStore(controller.settings.database_path)
    operation = uuid4()
    budget.reserve(
        run.id,
        operation,
        Decimal(".25"),
        service="mock",
        service_cap_usd=Decimal("1"),
        request_hash="fixture",
    )
    ArtifactStore(controller.settings.data_dir / "artifacts").put(b"Additional immutable artifact")
    before = controller.inspect(run.id)
    configuration = controller.configuration()
    backup = tmp_path.with_name(tmp_path.name + "-snapshot")
    restored = tmp_path.with_name(tmp_path.name + "-isolated-restored")
    manifest = backup_workspace(controller.settings.data_dir, backup)
    result = restore_workspace(backup, restored)
    reopened = Controller(Settings(data_dir=restored))
    reopened.initialize()
    assert reopened.inspect(run.id) == before
    assert reopened.configuration() == configuration
    assert result["events"] == len(before.events)
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((restored / name).read_bytes()).hexdigest() == expected
    for name in ("events", "records", "configurations", "reservations", "operations"):
        with (
            sqlite3.connect(controller.settings.database_path) as left,
            sqlite3.connect(restored / "ledger.sqlite3") as right,
        ):
            assert (
                left.execute(f"SELECT * FROM {name} ORDER BY rowid").fetchall()
                == right.execute(f"SELECT * FROM {name} ORDER BY rowid").fetchall()
            )
    assert BudgetStore(reopened.settings.database_path).operations()[0]["billed_microusd"] is None
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))

    async def view():
        from textual.widgets import DataTable, Input

        from doxa.cli.screens import SetupScreen

        app = ResearchConsole(restored, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            assert app.query_one("#runs", DataTable).row_count == 1
            app.push_screen(SetupScreen(app.controller, "agent"))
            await pilot.pause()
            app.screen.query_one("#setup-name", Input).value = "Unsaved draft"
            await pilot.press("escape")

    asyncio.run(view())
    assert reopened.configuration() == configuration
    assert reopened.inspect(run.id) == before


def test_artifact_failure_cannot_replace_published_content(tmp_path, monkeypatch):
    import os

    from doxa.storage.artifacts import ArtifactStore

    store = ArtifactStore(tmp_path / "artifacts")
    original = store.put(b"existing content")

    def fail(*args):
        raise OSError("injected partial artifact publication")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="injected"):
        store.put(b"new content")
    assert store.get(original) == b"existing content"
    assert [p for p in store.root.rglob("*") if p.is_file()] == [
        store.root / original.relative_path
    ]


def test_export_flush_failure_does_not_publish_incomplete_history(
    controller, command, tmp_path, monkeypatch
):
    from doxa.core.exports import export_run

    run = controller.configure_run(command)
    destination = tmp_path / "history.json"

    def fail(fd):
        raise OSError("injected export flush failure")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="injected"):
        export_run(controller, run.id, destination)
    assert not destination.exists()


def test_legacy_jsonl_export_flush_failure_does_not_publish_a_partial_stream(
    controller, command, tmp_path, monkeypatch
):
    from typer.testing import CliRunner

    from doxa.cli.main import app

    run = controller.configure_run(command)
    destination = tmp_path / "history.jsonl"

    def fail(fd):
        raise OSError("injected JSONL flush failure")

    monkeypatch.setattr(os, "fsync", fail)
    result = CliRunner().invoke(
        app,
        [
            "export-jsonl",
            str(run.id),
            str(destination),
            "--data-dir",
            str(controller.settings.data_dir),
        ],
    )
    assert result.exit_code != 0 and not destination.exists()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows detached worker / actual console closure"
)
def test_actual_console_close_does_not_kill_production_detached_worker(controller, tmp_path):
    import ctypes
    import signal
    from uuid import uuid4

    from test_pass3_execution import configured

    from doxa.core.controller import ConfigureRun
    from doxa.storage.workers import worker_lease

    source = configured(controller)
    experiment = controller.ledger.get(source.experiment_id)
    run = controller.configure_run(
        ConfigureRun(
            experiment=experiment.model_copy(update={"id": uuid4()}),
            mode=source.mode,
            execution_kind="synthetic",
            idempotency_key="window-owned-worker",
        )
    )
    hook = tmp_path / "owned-test-hook"
    hook.mkdir()
    worker_marker = tmp_path / "detached-worker-ready.json"
    # Trusted test hook pauses a synthetic turn inside real worker ownership. If the
    # hook is not loaded, the run remains synthetic and cannot contact a model.
    (hook / "sitecustomize.py").write_text(
        "import asyncio,json,os\nfrom pathlib import Path\n"
        "from doxa.core.workbench import DebateRuntime\n"
        "async def paused(self,*args,**kwargs):\n"
        f" Path({str(worker_marker)!r}).write_text("
        "json.dumps({'pid':os.getpid(),'parent_pid':os.getppid()}))\n"
        " await asyncio.Event().wait()\n"
        "DebateRuntime.turn=paused\n",
        encoding="utf-8",
    )
    marker = tmp_path / "owning-viewer-ready.json"
    old_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(hook) + (os.pathsep + old_pythonpath if old_pythonpath else "")
    try:
        viewer = spawn_probe(
            "window_owner", controller.settings.data_dir, marker, run.id, window=True
        )
    finally:
        if old_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = old_pythonpath
    worker_pid = None
    try:
        state = acknowledged(viewer, marker)
        deadline = time.monotonic() + 45
        worker = None
        while time.monotonic() < deadline:
            if worker_marker.exists():
                try:
                    worker = json.loads(worker_marker.read_text())
                    break
                except ValueError:
                    pass
            time.sleep(0.03)
        assert worker and worker["parent_pid"] == state["worker_launcher_pid"]
        worker_pid = worker["pid"]
        post = ctypes.windll.user32.PostMessageW
        post.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        assert post(state["hwnd"], 0x0010, None, None)
        viewer.wait(timeout=15)
        assert controller.inspect(run.id).run.status == "running"
        with pytest.raises(ValueError, match="owns"):
            with worker_lease(controller.settings.data_dir, run.id):
                pytest.fail("Closing the viewer released the independent worker's lock")
    finally:
        stop(viewer)
        if worker_pid is not None:
            try:
                os.kill(worker_pid, signal.SIGTERM)  # only the acknowledged owned test worker
            except ProcessLookupError:
                pass
