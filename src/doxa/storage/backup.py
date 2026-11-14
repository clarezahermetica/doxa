"""Verified local snapshots. Restore only into a new destination; never merge histories."""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

from doxa.core.secrets import _redact, reject_artifact_secrets, secret_values
from doxa.core.workspaces import validate_workspace
from doxa.storage.integrity import verify_workspace


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _new_destination(source: Path, destination: Path) -> tuple[Path, Path]:
    source, destination = source.resolve(), destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError("Destination must not exist; never overwrite or merge a workspace")
    if destination.is_relative_to(source):
        raise ValueError("Choose a destination outside the source workspace")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return source, destination


def backup_workspace(source: Path, destination: Path) -> dict[str, Any]:
    source = validate_workspace(source)
    source, destination = _new_destination(source, destination)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix="doxa-backup-") as temporary:
        stage = Path(temporary) / "snapshot"
        stage.mkdir()
        # SQLite's backup API includes committed WAL data, unlike copying a live DB file.
        with closing(
            sqlite3.connect((source / "ledger.sqlite3").as_uri() + "?mode=ro", uri=True)
        ) as original:
            with closing(sqlite3.connect(stage / "ledger.sqlite3")) as snapshot_db:
                original.backup(snapshot_db)
                known_values = secret_values(source, database=snapshot_db)
                # Older histories or artifacts can predate a credential registration.
                for table in ("events", "configurations"):
                    exists = snapshot_db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                    if exists:
                        for (body,) in snapshot_db.execute(f"SELECT body FROM {table}"):
                            if _redact(body, known_values) != body:
                                raise ValueError("Secret-bearing history cannot be backed up")
        root = source / "artifacts"
        if root.is_symlink():
            raise ValueError("Artifact symlinks are not supported in a backup")
        if root.exists():
            for path in root.rglob("*"):
                if path.is_symlink():
                    raise ValueError("Artifact symlinks are not supported in a backup")
                if path.is_file():
                    target = stage / "artifacts" / path.relative_to(root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
                    # Inspect exactly the bytes that will be published by this snapshot.
                    reject_artifact_secrets(target.read_bytes(), source, known_values=known_values)
        counts = verify_workspace(stage)
        files = {
            p.relative_to(stage).as_posix(): _digest(p) for p in stage.rglob("*") if p.is_file()
        }
        manifest = {"version": 1, "credentials_included": False, "files": files, "counts": counts}
        (stage / "backup-manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        os.rename(stage, destination)  # fails if another destination appeared; never replace
    return manifest


def restore_workspace(source: Path, destination: Path) -> dict[str, int]:
    source, destination = _new_destination(source, destination)
    try:
        manifest = json.loads((source / "backup-manifest.json").read_text(encoding="utf-8"))
        if manifest["version"] != 1 or manifest["credentials_included"] is not False:
            raise ValueError("Unsupported backup manifest")
        files = manifest["files"]
        if not isinstance(files, dict) or "ledger.sqlite3" not in files:
            raise ValueError("Invalid backup manifest")
        for name, digest in files.items():
            relative = Path(name)
            if relative.is_absolute() or relative.drive or ".." in relative.parts:
                raise ValueError("Unsafe backup entry")
            path = (source / name).resolve()
            if not path.is_relative_to(source) or not (
                name == "ledger.sqlite3" or name.startswith("artifacts/sha256/")
            ):
                raise ValueError("Unsafe backup entry")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError("Backup integrity check failed")
    except (KeyError, TypeError, OSError, ValueError):
        raise ValueError("Backup integrity check failed; destination was not restored") from None
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix="doxa-restore-") as temporary:
        stage = Path(temporary) / "workspace"
        stage.mkdir()
        for name in files:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
            if _digest(target) != files[name]:
                raise ValueError("Backup integrity changed during restore")
        counts = verify_workspace(stage)
        os.rename(stage, destination)
    return counts
