"""Shared explicit workspace selection. Preferences contain paths, never records."""

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


def preferences_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".config")))
    return base / "DOXA" / "client.json"


def _preferences() -> dict[str, Any]:
    try:
        value = json.loads(preferences_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def validate_workspace(directory: Path) -> Path:
    directory = directory.expanduser().resolve()
    path = directory / "ledger.sqlite3"
    if not path.is_file():
        raise ValueError("No DOXA workspace ledger found at the selected path")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"events", "records", "reservations", "alembic_version"} <= tables:
                raise ValueError("Selected database is not a DOXA workspace")
            revision = db.execute("SELECT version_num FROM alembic_version").fetchall()
            if len(revision) != 1 or revision[0][0] not in {"0001", "0002", "0003", "0004"}:
                raise ValueError(
                    "Unsupported DOXA workspace revision; use a compatible application"
                )
            # Validate shape before any migration can touch a similarly named database.
            db.execute("SELECT id,trajectory_id,sequence,idempotency_key,body FROM events LIMIT 0")
            db.execute("SELECT id,kind,event_id,body FROM records LIMIT 0")
    except sqlite3.Error:
        raise ValueError("Selected workspace ledger is unreadable or invalid") from None
    return directory


def default_workspace() -> Path:
    explicit = os.environ.get("DOXA_DATA_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    selected = _preferences().get("workspace")
    if isinstance(selected, str) and selected:
        # A missing remembered selection remains visible. Never fall back or create it.
        return Path(selected).expanduser().resolve()
    # Installation and source entry points share saved selection. Merely changing the
    # shell directory must not select a different research history.
    return (preferences_path().parent / "workspace").resolve()


def recent_workspaces() -> list[Path]:
    prefs = _preferences()
    values = prefs.get("recent", [])
    values = values if isinstance(values, list) else []
    result = []
    for value in [prefs.get("workspace"), *values]:
        if isinstance(value, str) and value:
            path = Path(value).expanduser().resolve()
            if path not in result:
                result.append(path)
    return result[:10]


def remember_workspace(directory: Path) -> None:
    directory = validate_workspace(directory)
    prefs = _preferences()
    recent = [directory, *(p for p in recent_workspaces() if p != directory)][:10]
    prefs.update(workspace=str(directory), recent=[str(p) for p in recent])
    target = preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix="client-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(prefs, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def refuse_missing_selection(directory: Path) -> None:
    selected = _preferences().get("workspace")
    if isinstance(selected, str) and selected and directory.resolve() == Path(selected).resolve():
        if not (directory / "ledger.sqlite3").is_file():
            raise ValueError(
                "Selected workspace is missing. Open it through the workspace selector."
            )
