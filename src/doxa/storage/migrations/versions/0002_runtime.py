"""Append-only configuration history and durable operation metadata."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE configurations (
        kind TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        body TEXT NOT NULL, PRIMARY KEY(kind,id,version))""")
    for operation in ("UPDATE", "DELETE"):
        op.execute(f"""CREATE TRIGGER config_no_{operation.lower()} BEFORE {operation}
        ON configurations BEGIN SELECT RAISE(ABORT,'append-only configuration'); END""")
    op.execute("""CREATE TABLE operations (
        id TEXT PRIMARY KEY REFERENCES reservations(id), service TEXT NOT NULL,
        request_hash TEXT NOT NULL, state TEXT NOT NULL,
        CHECK(state IN ('prepared','in_flight','uncertain','completed','failed')))""")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade unsupported")
