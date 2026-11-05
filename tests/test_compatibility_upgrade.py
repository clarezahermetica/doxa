from doxa.core.config import Settings
from doxa.core.controller import Controller
from doxa.core.models import Event, EventType, Run, Trajectory
from doxa.storage.database import connection, migrate
from doxa.storage.ledger import Ledger


def test_foundation_revision_0001_history_survives_forward_upgrades(tmp_path, command):
    settings = Settings(data_dir=tmp_path)
    migrate(settings.database_path, "0001")
    run = Run(experiment_id=command.experiment.id, mode=command.mode)
    trajectory = Trajectory(run_id=run.id)
    event = Event(
        experiment_id=command.experiment.id,
        run_id=run.id,
        trajectory_id=trajectory.id,
        sequence=1,
        type=EventType.RUN_CREATED,
        idempotency_key="legacy-foundation",
        payload=(command.experiment, run, trajectory),
    )
    saved = Ledger(settings.database_path).append(event)
    with connection(settings.database_path) as db:
        original = db.execute("SELECT body FROM events WHERE id=?", (str(saved.id),)).fetchone()[0]
    ctrl = Controller(settings)
    ctrl.initialize()
    assert ctrl.inspect(run.id).events == (saved,)
    with connection(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0004"
        assert (
            db.execute("SELECT body FROM events WHERE id=?", (str(saved.id),)).fetchone()[0]
            == original
        )
