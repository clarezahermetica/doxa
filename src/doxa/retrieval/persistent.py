"""Reusable FTS5 cache. Eligibility always comes from the controller, never this index."""

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from doxa.storage.database import connection


class PersistentSearch:
    def __init__(self, database: Path):
        self.database = database

    def rank(
        self, documents: Sequence[tuple[UUID, str, str]], query: str, limit: int = 10
    ) -> tuple[UUID, ...]:
        words = tuple(dict.fromkeys(re.findall(r"[^\W_]+", query, re.UNICODE)))[:64]
        if not documents or not words:
            return ()
        expression = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
        allowed = {str(i) for i, _, _ in documents}
        with connection(self.database) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for identity, title, text in documents:
                digest = hashlib.sha256((title + "\0" + text).encode()).hexdigest()
                prior = db.execute(
                    "SELECT content_hash FROM search_documents WHERE record_id=?", (str(identity),)
                ).fetchone()
                if prior is None:
                    db.execute(
                        "INSERT INTO search_documents VALUES (?,?,?,?)",
                        (str(identity), digest, title, text),
                    )
                elif prior[0] != digest:
                    raise ValueError(
                        "Immutable search record changed content; rebuild the derived index"
                    )
            # Rank IDs, not snippets. Canonical text is retrieved and authorized separately.
            rows = db.execute(
                "SELECT d.record_id FROM search_fts JOIN search_documents d "
                "ON d.rowid=search_fts.rowid WHERE search_fts MATCH ? "
                "ORDER BY bm25(search_fts),d.record_id",
                (expression,),
            ).fetchall()
        return tuple(UUID(row[0]) for row in rows if row[0] in allowed)[:limit]

    def rebuild(self) -> None:
        with connection(self.database) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM search_documents")
