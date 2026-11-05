"""Non-USD subscription call admission in the same authoritative workspace."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE quota_operations (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES records(id),
        service TEXT NOT NULL, request_hash TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('in_flight','uncertain','completed','failed')),
        reserved_calls INTEGER NOT NULL DEFAULT 1 CHECK(reserved_calls=1),
        quota_consumed INTEGER CHECK(quota_consumed IS NULL),
        billed_microusd INTEGER CHECK(billed_microusd IS NULL))""")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade unsupported")
