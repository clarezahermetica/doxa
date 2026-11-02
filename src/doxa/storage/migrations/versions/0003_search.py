"""Derived local full-text indexes in the canonical database; safe to rebuild."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE search_documents (record_id TEXT UNIQUE NOT NULL, "
        "content_hash TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL)"
    )
    op.execute(
        "CREATE VIRTUAL TABLE search_fts USING fts5(title,body,"
        "content='search_documents',content_rowid='rowid')"
    )
    op.execute("""CREATE TRIGGER search_insert AFTER INSERT ON search_documents BEGIN
        INSERT INTO search_fts(rowid,title,body) VALUES(new.rowid,new.title,new.body); END""")
    op.execute("""CREATE TRIGGER search_delete AFTER DELETE ON search_documents BEGIN
        INSERT INTO search_fts(search_fts,rowid,title,body)
        VALUES('delete',old.rowid,old.title,old.body);
        END""")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade unsupported; rebuild derived indexes instead")
