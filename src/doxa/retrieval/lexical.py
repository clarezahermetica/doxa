"""Deterministic SQLite FTS5 ranking over an already-authorized snapshot.

This disposable index contains no authority: callers supply eligible records and
recheck their IDs before disclosure. It is never a second research database.
"""

import re
import sqlite3
from collections.abc import Sequence
from uuid import UUID


def lexical_rank(
    items: Sequence[tuple[UUID, str]], query: str, limit: int = 10
) -> tuple[UUID, ...]:
    words = tuple(dict.fromkeys(re.findall(r"[^\W_]+", query, re.UNICODE)))[:64]
    if not items or not words:
        return ()
    expression = " OR ".join('"' + w.replace('"', '""') + '"' for w in words)
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE VIRTUAL TABLE search USING fts5(identity UNINDEXED, content)")
        db.executemany("INSERT INTO search VALUES (?,?)", [(str(i), t) for i, t in items])
        rows = db.execute(
            "SELECT identity FROM search WHERE search MATCH ? ORDER BY rank,identity LIMIT ?",
            (expression, limit),
        ).fetchall()
    return tuple(UUID(r[0]) for r in rows)
