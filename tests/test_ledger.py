from concurrent.futures import ThreadPoolExecutor
from sqlite3 import IntegrityError
from uuid import uuid4

import pytest

from doxa.core.controller import ConfigureRun, Controller
from doxa.core.models import Claim, Event, EventType, Provenance, Trajectory
from doxa.storage.database import connection
from doxa.storage.ledger import Ledger, LedgerConflict


def test_roundtrip_retry_and_conflicting_idempotency(controller: Controller, command: ConfigureRun):
    run = controller.configure_run(command)
    assert controller.configure_run(command) == run
    assert tuple(Ledger(controller.settings.database_path).events(run.id)) == (
        controller.inspect(run.id).events
    )
    assert len(controller.inspect(run.id).events) == 1
    changed = command.model_copy(update={"execution_kind": "replay"})
    with pytest.raises(LedgerConflict):
        controller.configure_run(changed)
    assert len(controller.list_runs()) == 1


def test_atomic_rollback_and_database_immutability(controller: Controller, command: ConfigureRun):
    run = controller.configure_run(command)
    first = controller.inspect(run.id).events[0]
    # Duplicate object ID fails after event insertion; transaction rolls the event back too.
    with pytest.raises(IntegrityError):
        controller.ledger.append(
            first.model_copy(
                update={
                    "id": uuid4(),
                    "idempotency_key": "duplicate-object",
                }
            )
        )
    assert len(controller.inspect(run.id).events) == 1
    with connection(controller.settings.database_path) as db:
        for table in ("events", "records"):
            for sql in (f"DELETE FROM {table}", f"UPDATE {table} SET body='{{}}'"):
                with pytest.raises(IntegrityError, match="append-only"):
                    db.execute(sql)


def test_concurrent_sequence_allocation(controller: Controller, command: ConfigureRun):
    run = controller.configure_run(command)
    first = controller.inspect(run.id).events[0]

    def append(index: int):
        return controller.ledger.append(
            Event(
                experiment_id=first.experiment_id,
                run_id=run.id,
                trajectory_id=first.trajectory_id,
                sequence=1,
                type=EventType.OBSERVATION_RECEIVED,
                idempotency_key=f"concurrent-{index}",
                parent_event_ids=(first.id,),
            )
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(append, range(12)))
    assert [e.sequence for e in controller.ledger.events(run.id)] == list(range(1, 14))


def test_cross_scope_record_rejected(controller: Controller, command: ConfigureRun):
    run = controller.configure_run(command)
    first = controller.inspect(run.id).events[0]
    claim = Claim(
        experiment_id=first.experiment_id,
        run_id=uuid4(),
        trajectory_id=first.trajectory_id,
        provenance=Provenance.MODEL_OUTPUT,
        proposition="synthetic",
    )
    with pytest.raises(LedgerConflict, match="scope"):
        controller.ledger.append(
            first.model_copy(
                update={
                    "id": uuid4(),
                    "idempotency_key": "cross-scope",
                    "payload": (claim,),
                }
            )
        )


def test_fork_ancestry_preserves_parent_and_per_branch_sequences(
    controller: Controller,
    command: ConfigureRun,
):
    run = controller.configure_run(command)
    parent = controller.inspect(run.id).events[0]
    child = Trajectory(run_id=run.id, parent_id=parent.trajectory_id, fork_event_id=parent.id)
    fork = controller.ledger.append(
        Event(
            experiment_id=parent.experiment_id,
            run_id=run.id,
            trajectory_id=child.id,
            sequence=1,
            type=EventType.BRANCH_CREATED,
            payload=(child,),
            idempotency_key="synthetic-fork",
            parent_event_ids=(parent.id,),
        )
    )
    assert fork.sequence == 1
    assert controller.ledger.events(run.id)[0] == parent
    assert controller.ledger.get(child.id) == child
    # This checks ledger lineage only. It does not simulate environment restoration.


def test_migration_repeat_preserves_history(controller: Controller, command: ConfigureRun):
    run = controller.configure_run(command)
    before = controller.inspect(run.id)
    controller.initialize()
    assert controller.inspect(run.id) == before


def test_concurrent_runs_reuse_one_immutable_experiment(
    controller: Controller,
    command: ConfigureRun,
):
    def configure(index: int):
        return controller.configure_run(
            command.model_copy(
                update={
                    "idempotency_key": f"parallel-run-{index}",
                }
            )
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(configure, range(8)))
    assert len({run.id for run in runs}) == 8
    assert len(controller.ledger.records("experiment")) == 1
    assert len(controller.list_runs()) == 8


def test_fork_origin_cannot_reference_an_unrelated_branch(
    controller: Controller,
    command: ConfigureRun,
):
    run = controller.configure_run(command)
    root = controller.inspect(run.id).events[0]
    child = Trajectory(run_id=run.id, parent_id=root.trajectory_id, fork_event_id=root.id)
    fork = controller.ledger.append(
        Event(
            experiment_id=root.experiment_id,
            run_id=run.id,
            trajectory_id=child.id,
            sequence=1,
            type=EventType.BRANCH_CREATED,
            payload=(child,),
            idempotency_key="child",
        )
    )
    bad = Trajectory(run_id=run.id, parent_id=root.trajectory_id, fork_event_id=fork.id)
    with pytest.raises(LedgerConflict, match="parent trajectory"):
        controller.ledger.append(
            Event(
                experiment_id=root.experiment_id,
                run_id=run.id,
                trajectory_id=bad.id,
                sequence=1,
                type=EventType.BRANCH_CREATED,
                payload=(bad,),
                idempotency_key="bad",
            )
        )
