"""Initial immutable ledger, rebuildable record index, and spending reservations."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE events (
        id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, run_id TEXT NOT NULL,
        trajectory_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence > 0),
        idempotency_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL,
        UNIQUE(trajectory_id, sequence))""")
    op.execute("CREATE INDEX events_run ON events(run_id, trajectory_id, sequence)")
    op.execute("""CREATE TABLE records (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, experiment_id TEXT NOT NULL,
        run_id TEXT, trajectory_id TEXT, event_id TEXT NOT NULL REFERENCES events(id),
        body TEXT NOT NULL)""")
    op.execute("CREATE INDEX records_scope ON records(experiment_id, run_id, kind)")
    op.execute("""CREATE TABLE reservations (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES records(id),
        reserved_microusd INTEGER NOT NULL CHECK(reserved_microusd > 0),
        billed_microusd INTEGER CHECK(billed_microusd >= 0),
        status TEXT NOT NULL CHECK(status IN ('reserved', 'settled')))""")
    for table in ("events", "records"):
        for operation in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER {table}_no_{operation.lower()}
                BEFORE {operation} ON {table}
                BEGIN SELECT RAISE(ABORT, 'append-only history'); END""")


def downgrade() -> None:
    raise RuntimeError("Destructive ledger downgrade is unsupported; restore a verified backup")
