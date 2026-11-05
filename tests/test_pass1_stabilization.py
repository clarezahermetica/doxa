import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from doxa.core.config import Settings
from doxa.core.controller import Controller
from doxa.core.models import Event, EventType, ModelAssignment, ModelCall, Provenance
from doxa.core.workspaces import default_workspace, remember_workspace
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.database import connection


def test_recent_workspaces_preserve_independent_ledgers(tmp_path, monkeypatch, command):
    from doxa.core.workspaces import recent_workspaces

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))
    monkeypatch.delenv("DOXA_DATA_DIR", raising=False)
    paths = [tmp_path / "Research Ω % space" / ".doxa", tmp_path / "unrelated"]
    for path in paths:
        ctrl = Controller(Settings(data_dir=path))
        ctrl.initialize()
        ctrl.configure_run(command.model_copy(update={"idempotency_key": str(path)}))
        remember_workspace(path)
    assert recent_workspaces() == [p.resolve() for p in reversed(paths)]
    assert default_workspace() == paths[1].resolve()
    remember_workspace(paths[0])
    assert len(Controller(Settings(data_dir=paths[0])).list_runs()) == 1
    assert len(Controller(Settings(data_dir=paths[1])).list_runs()) == 1


def test_unrelated_database_must_not_be_migrated_or_remembered(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))
    path = tmp_path / "foreign"
    path.mkdir()
    db = sqlite3.connect(path / "ledger.sqlite3")
    db.execute("CREATE TABLE personal_notes(body TEXT)")
    db.commit()
    db.close()
    before = (path / "ledger.sqlite3").read_bytes()
    with pytest.raises(ValueError, match="workspace"):
        Controller(Settings(data_dir=path)).initialize()
    with pytest.raises(ValueError, match="workspace"):
        remember_workspace(path)
    assert (path / "ledger.sqlite3").read_bytes() == before


def test_missing_remembered_workspace_and_invalid_preferences(tmp_path, monkeypatch):
    from doxa.core.workspaces import preferences_path

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))
    monkeypatch.delenv("DOXA_DATA_DIR", raising=False)
    selected = tmp_path / "missing Ω"
    pref = preferences_path()
    pref.parent.mkdir(parents=True)
    pref.write_text(json.dumps({"workspace": str(selected)}))
    assert default_workspace() == selected.resolve()
    with pytest.raises(ValueError, match="missing"):
        Controller(Settings()).initialize()
    assert not selected.exists()
    pref.write_text('{"workspace": []}')
    assert isinstance(default_workspace(), Path)


def test_backup_restore_is_verified_and_non_overwriting(controller, command, tmp_path):
    from doxa.storage.backup import backup_workspace, restore_workspace

    run = controller.configure_run(command)
    ArtifactStore(controller.settings.data_dir / "artifacts").put(b"preserve original artifact")
    (controller.settings.data_dir / ".env").write_text("PRIVATE=must-not-copy")
    backup = tmp_path.with_name(tmp_path.name + "-backup")
    backup_workspace(controller.settings.data_dir, backup)
    assert not (backup / ".env").exists()
    restored = tmp_path / "restored"
    restore_workspace(backup, restored)
    clone = Controller(Settings(data_dir=restored))
    clone.initialize()
    assert clone.inspect(run.id) == controller.inspect(run.id)
    with pytest.raises(FileExistsError):
        restore_workspace(backup, restored)
    (backup / "ledger.sqlite3").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        restore_workspace(backup, tmp_path / "bad-restore")
    assert not (tmp_path / "bad-restore").exists()


def test_projection_reconstruction_detects_disagreement(controller, command):
    from doxa.storage.integrity import verify_workspace

    run = controller.configure_run(command)
    assert verify_workspace(controller.settings.data_dir)["events"] == 1
    with connection(controller.settings.database_path) as db, db:
        db.execute("DROP TRIGGER records_no_update")
        db.execute("UPDATE records SET kind='claim' WHERE id=?", (str(run.id),))
    with pytest.raises(ValueError, match="projection"):
        verify_workspace(controller.settings.data_dir)


def test_recovery_preserves_local_uncertainty(controller, command):
    run = controller.configure_run(command)
    previous = controller.inspect(run.id).events[-1]
    call = ModelCall(
        experiment_id=previous.experiment_id,
        run_id=run.id,
        trajectory_id=previous.trajectory_id,
        provenance=Provenance.SYSTEM_INFERENCE,
        call_id=uuid4(),
        agent_id=uuid4(),
        assignment=ModelAssignment(provider="custom", model_id="unknown", instruction_version="1"),
        status="started",
        request_settings={"location": "loopback"},
        billing_uncertain=False,
    )
    controller.ledger.append(
        Event(
            experiment_id=previous.experiment_id,
            run_id=run.id,
            trajectory_id=previous.trajectory_id,
            sequence=1,
            type=EventType.ACTION_REQUESTED,
            payload=(call,),
            parent_event_ids=(previous.id,),
            idempotency_key="local-interruption",
        )
    )
    controller.cancel(run.id)
    recovered = controller.recover_run(run.id)
    calls = [p for e in recovered.events for p in e.payload if isinstance(p, ModelCall)]
    assert calls[-1].status == "uncertain"
    assert controller.recover_run(run.id) == recovered
    with pytest.raises(ValueError):
        controller.reconcile_local_call(call.call_id, evidence="", confirmed_stopped=False)
    controller.reconcile_local_call(
        call.call_id, evidence="Operator stopped the mock runtime process.", confirmed_stopped=True
    )
    assert [
        p for e in controller.inspect(run.id).events for p in e.payload if isinstance(p, ModelCall)
    ][-1].status == "failed"


def test_cancelled_run_blocks_paid_and_local_admission(controller, command):
    from decimal import Decimal

    from doxa.storage.budget import BudgetStore
    from doxa.storage.local_dispatch import admit_local

    run = controller.configure_run(command)
    operation = uuid4()
    budgets = BudgetStore(controller.settings.database_path)
    budgets.reserve(
        run.id,
        operation,
        Decimal(".1"),
        service="mock",
        service_cap_usd=Decimal("1"),
        request_hash="fixed",
    )
    controller.cancel(run.id)
    with pytest.raises(ValueError, match="terminal"):
        budgets.dispatch_once(operation)
    assert budgets.operations()[0]["state"] == "prepared"
    previous = controller.inspect(run.id).events[-1]
    call = ModelCall(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=previous.trajectory_id,
        provenance=Provenance.SYSTEM_INFERENCE,
        call_id=uuid4(),
        agent_id=uuid4(),
        assignment=ModelAssignment(provider="mock", model_id="m", instruction_version="1"),
        status="started",
    )
    event = Event(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=previous.trajectory_id,
        sequence=1,
        type=EventType.ACTION_REQUESTED,
        payload=(call,),
        idempotency_key="forbidden",
    )
    with pytest.raises(ValueError, match="terminal"):
        admit_local(controller.ledger, event, 1, 5)
    assert not controller.ledger.records("model_call")


def test_worker_lease_excludes_duplicate_workers_and_recovery(controller, command):
    from doxa.storage.workers import worker_lease

    run = controller.configure_run(command)
    controller.cancel(run.id)
    with worker_lease(controller.settings.data_dir, run.id):
        with pytest.raises(ValueError, match="owns"):
            with worker_lease(controller.settings.data_dir, run.id):
                pytest.fail("Duplicate owner admitted")
        with pytest.raises(ValueError, match="owns"):
            controller.recover_run(run.id)
    controller.recover_run(run.id)


def test_ledger_batches_sequences_idempotency_and_direct_immutability(controller, command):
    from concurrent.futures import ThreadPoolExecutor

    from doxa.storage.ledger import LedgerConflict

    run = controller.configure_run(command)
    previous = controller.inspect(run.id).events[-1]

    def event(key):
        return Event(
            experiment_id=run.experiment_id,
            run_id=run.id,
            trajectory_id=previous.trajectory_id,
            sequence=1,
            type=EventType.OBSERVATION_RECEIVED,
            idempotency_key=key,
            parent_event_ids=(previous.id,),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        saved = list(
            pool.map(lambda i: controller.ledger.append(event(f"parallel-{i}")), range(12))
        )
    assert sorted(e.sequence for e in saved) == list(range(2, 14))
    assert controller.ledger.append(event("parallel-0")).id == saved[0].id
    with pytest.raises(LedgerConflict):
        controller.ledger.append_batch(
            (
                event("must-rollback"),
                event("parallel-0").model_copy(update={"command_digest": "different"}),
            )
        )
    assert len(controller.inspect(run.id).events) == 13
    with connection(controller.settings.database_path) as db:
        for table in ("records", "events"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                db.execute(f"DELETE FROM {table}")


def test_backup_retains_wal_commits_and_legacy_upgrade(tmp_path, command):
    from doxa.storage.backup import backup_workspace, restore_workspace
    from doxa.storage.database import migrate

    source = tmp_path / "legacy Ω % path"
    migrate(source / "ledger.sqlite3", "0001")
    ctrl = Controller(Settings(data_dir=source))
    run = ctrl.configure_run(command)
    with connection(ctrl.settings.database_path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE backup_wal_probe(value TEXT)")
        db.execute("INSERT INTO backup_wal_probe VALUES ('committed')")
        db.commit()
        backup_workspace(source, tmp_path / "snapshot")
    restore_workspace(tmp_path / "snapshot", tmp_path / "restored")
    clone = Controller(Settings(data_dir=tmp_path / "restored"))
    before = clone.ledger.events(run.id)
    clone.initialize()
    assert clone.ledger.events(run.id) == before
    assert clone.inspect(run.id).run == run
    with connection(clone.settings.database_path) as db:
        assert db.execute("SELECT value FROM backup_wal_probe").fetchone()[0] == "committed"


def test_subcommands_do_not_create_missing_workspace(tmp_path):
    from typer.testing import CliRunner

    from doxa.cli.main import app

    for args in (["runs"], ["models"], ["experiment", "new", "--name", "x", "--question", "q"]):
        missing = tmp_path / "not-created"
        result = CliRunner().invoke(app, [*args, "--data-dir", str(missing)])
        assert result.exit_code != 0 and not missing.exists()


def test_failed_migration_rolls_back_ddl_and_can_retry(tmp_path, monkeypatch):
    from alembic.operations import Operations

    from doxa.storage.database import migrate

    path = tmp_path / "ledger.sqlite3"
    migrate(path, "0002")
    execute = Operations.execute

    def fail(self, sqltext, *args, **kwargs):
        if "CREATE VIRTUAL TABLE" in str(sqltext):
            raise RuntimeError("simulated interruption")
        return execute(self, sqltext, *args, **kwargs)

    monkeypatch.setattr(Operations, "execute", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        migrate(path)
    with connection(path) as db:
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='search_documents'"
        ).fetchone()
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
    monkeypatch.setattr(Operations, "execute", execute)
    migrate(path)


def test_dead_process_releases_os_ownership_without_replay(controller, command):
    import os
    import signal
    import subprocess
    import sys

    from doxa.storage.workers import worker_lease

    run = controller.configure_run(command)
    code = (
        "from pathlib import Path; from uuid import UUID; import os,sys\n"
        "from doxa.storage.workers import worker_lease\n"
        "with worker_lease(Path(sys.argv[1]),UUID(sys.argv[2])):\n"
        " print(os.getpid(),flush=True); sys.stdin.read()"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(controller.settings.data_dir), str(run.id)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    identity = None
    try:
        line = child.stdout.readline().strip()
        assert line, child.stderr.read()
        identity = int(line)
        with pytest.raises(ValueError, match="owns"):
            with worker_lease(controller.settings.data_dir, run.id):
                pytest.fail("Live child ownership lost")
        os.kill(identity, signal.SIGTERM)
        child.wait(timeout=15)
        identity = None
        with worker_lease(controller.settings.data_dir, run.id):
            assert controller.inspect(run.id).run.status == "configured"
        assert len(controller.inspect(run.id).events) == 1
    finally:
        if identity:
            os.kill(identity, signal.SIGTERM)
        child.communicate(timeout=15)


def test_local_response_after_cancellation_does_not_continue_execution(controller, command):
    import asyncio

    import httpx

    from doxa.core.execution import ExecuteTask, Runtime
    from doxa.core.models import Agent, Permissions, Role, RunState
    from doxa.core.profiles import CouncilConfig, ModelProfile
    from doxa.providers.contracts import ModelMessage
    from doxa.providers.runpod import RunPodProvider

    profile = ModelProfile(
        id="mock-local",
        provider="openai_compatible",
        local=True,
        authentication="none",
        enabled=True,
        base_url="http://127.0.0.1:8080/v1",
        model_id="mock",
    )
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    actor = Agent(
        role=Role.EXECUTOR,
        instructions="Fixture",
        permissions=Permissions(remote_inference=True),
        model_profile_id=profile.id,
        model_profile_version=1,
        model=ModelAssignment(
            provider=profile.provider, model_id=profile.model_id, instruction_version="1"
        ),
    )
    run = controller.configure_run(
        command.model_copy(
            update={
                "execution_kind": "live",
                "experiment": command.experiment.model_copy(update={"agents": (actor,)}),
            }
        )
    )
    previous = controller.inspect(run.id).events[-1]
    controller.ledger.append(
        Event(
            experiment_id=run.experiment_id,
            run_id=run.id,
            trajectory_id=previous.trajectory_id,
            sequence=1,
            type=EventType.RUN_STARTED,
            idempotency_key="started",
            payload=(
                RunState(
                    experiment_id=run.experiment_id,
                    run_id=run.id,
                    trajectory_id=previous.trajectory_id,
                    provenance=Provenance.SYSTEM_INFERENCE,
                    status="running",
                    reason_code="fixture",
                ),
            ),
        )
    )

    def respond(request):
        controller.cancel(run.id)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Observed response after cancellation"}}]},
        )

    controller.providers.create = lambda *a, **kw: RunPodProvider(
        profile, {}, httpx.MockTransport(respond)
    )
    runtime = Runtime(controller, run.id)
    runtime.command = ExecuteTask()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            runtime.model_text(actor, "fixture", (ModelMessage(role="user", content="Fixture"),))
        )
    assert controller.inspect(run.id).run.status == "cancelled"
    assert not controller.ledger.records("claim")
    assert controller.ledger.records("model_call")[-1].status == "completed"


@pytest.mark.parametrize("preference", ["missing", "empty"])
def test_terminal_workspace_error_and_recent_selection(tmp_path, monkeypatch, command, preference):
    import asyncio

    from textual.widgets import Input, Select, Static

    from doxa.cli.console import ResearchConsole
    from doxa.core.workspaces import preferences_path

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))
    existing = tmp_path / "existing"
    ctrl = Controller(Settings(data_dir=existing))
    ctrl.initialize()
    ctrl.configure_run(command)
    remember_workspace(existing)
    current = tmp_path / "empty"
    if preference == "empty":
        Controller(Settings(data_dir=current)).initialize()

    async def interact():
        app = ResearchConsole(current, show_guide=False)
        async with app.run_test(size=(90, 28)) as pilot:
            await pilot.pause()
            if preference == "empty":
                assert "No runs" in str(app.query_one("#notice", Static).render())
                app.action_workspace()
                await pilot.pause()
            for _ in range(30):
                if app.screen.query("#workspace-recent"):
                    break
                await pilot.pause()
            await pilot.pause()
            app.screen.query_one("#workspace-recent", Select).value = str(existing.resolve())
            await pilot.pause()
            assert app.screen.query_one("#workspace-path", Input).value == str(existing.resolve())
            await pilot.click("#workspace-open")
            await pilot.pause()
            assert len(app.controller.list_runs()) == 1
            assert app.controller.settings.data_dir.resolve() == existing.resolve()
            await pilot.press("q")

    asyncio.run(interact())
    assert json.loads(preferences_path().read_text())["workspace"] == str(existing.resolve())


def test_backup_preserves_held_reservations_and_no_automatic_replay(controller, command, tmp_path):
    from decimal import Decimal

    from doxa.storage.backup import backup_workspace, restore_workspace
    from doxa.storage.budget import BudgetExceeded, BudgetStore

    run = controller.configure_run(command)
    budget = BudgetStore(controller.settings.database_path)
    identity = uuid4()
    budget.reserve(
        run.id,
        identity,
        Decimal(".5"),
        service="mock",
        service_cap_usd=Decimal("1"),
        request_hash="known",
    )
    budget.dispatch_once(identity)
    destination = tmp_path.with_name(tmp_path.name + "-snapshot")
    backup_workspace(controller.settings.data_dir, destination)
    restored = tmp_path / "restored"
    restore_workspace(destination, restored)
    other = BudgetStore(restored / "ledger.sqlite3")
    assert other.operations()[0]["state"] == "in_flight"
    assert other.operations()[0]["billed_microusd"] is None
    assert other.operations()[0]["reserved_microusd"] == 500000
    with pytest.raises(BudgetExceeded):
        other.dispatch_once(identity)


def test_failed_atomic_completion_does_not_release_reservation(controller, command):
    from decimal import Decimal

    from doxa.storage.budget import BudgetStore

    run = controller.configure_run(command)
    budget = BudgetStore(controller.settings.database_path)
    identity = uuid4()
    budget.reserve(
        run.id,
        identity,
        Decimal(".5"),
        service="mock",
        service_cap_usd=Decimal("1"),
        request_hash="known",
    )
    budget.dispatch_once(identity)
    before = controller.inspect(run.id)
    invalid = Event(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=uuid4(),
        sequence=1,
        type=EventType.PROVIDER_FAILED,
        idempotency_key="rollback-call",
    )
    with pytest.raises(ValueError):
        budget.complete_call(identity, "completed", Decimal("0"), invalid, controller.ledger)
    assert controller.inspect(run.id) == before
    assert budget.operations()[0]["state"] == "in_flight"
    assert budget.operations()[0]["billed_microusd"] is None


def test_workspace_credential_is_rejected_by_ledger(controller, command):
    import os

    from doxa.core.credential_store import save_credential
    from doxa.core.models import Evidence

    if os.name != "nt":
        pytest.skip("Windows DPAPI acceptance")
    save_credential(
        controller.settings.data_dir, "SYNTHETIC_TEST_KEY", "synthetic-private-value-284638"
    )
    run = controller.configure_run(command)
    previous = controller.inspect(run.id).events[-1]
    item = Evidence(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=previous.trajectory_id,
        provenance=Provenance.IMPORTED_SOURCE,
        source="fixture",
        description="synthetic-private-value-284638",
    )
    with pytest.raises(ValueError):
        controller.ledger.append(
            Event(
                experiment_id=run.experiment_id,
                run_id=run.id,
                trajectory_id=previous.trajectory_id,
                sequence=1,
                type=EventType.OBSERVATION_RECEIVED,
                payload=(item,),
                idempotency_key="secret-rejected",
            )
        )
    assert len(controller.inspect(run.id).events) == 1


def test_restore_rejects_manifest_path_traversal_without_destination(controller, command, tmp_path):
    from doxa.storage.backup import backup_workspace, restore_workspace

    controller.configure_run(command)
    backup = tmp_path.with_name(tmp_path.name + "-backup")
    backup_workspace(controller.settings.data_dir, backup)
    manifest = backup / "backup-manifest.json"
    body = json.loads(manifest.read_text())
    body["files"]["artifacts/sha256/../../ledger.sqlite3"] = body["files"]["ledger.sqlite3"]
    manifest.write_text(json.dumps(body))
    target = tmp_path / "rejected"
    with pytest.raises(ValueError, match="integrity"):
        restore_workspace(backup, target)
    assert not target.exists()
