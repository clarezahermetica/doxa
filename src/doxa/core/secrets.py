"""Backend-only resolution and defense against accidental secret persistence."""

import json
import os
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


def local_env() -> dict[str, str]:
    values = {
        k: v
        for k, v in dotenv_values(Path(os.environ.get("DOXA_ENV_FILE", ".env"))).items()
        if v is not None
    }
    return {**values, **os.environ}


def workspace_env(directory: Path) -> dict[str, str]:
    """Resolve existing workspace credentials independent of the launch directory."""
    directory = directory.expanduser().resolve()
    explicit = os.environ.get("DOXA_ENV_FILE")
    path = Path(explicit).expanduser().resolve() if explicit else directory / ".env"
    if not explicit and not path.is_file() and directory.name == ".doxa":
        path = directory.parent / ".env"
    values = {k: v for k, v in dotenv_values(path).items() if v is not None}
    from doxa.core.credential_store import load_credentials

    protected = load_credentials(directory)
    controls: dict[str, str] = {}
    control_file = directory / "runtime-settings.json"
    if control_file.is_file():
        parsed = json.loads(control_file.read_text(encoding="utf-8"))
        controls = {
            k: str(v)
            for k, v in parsed.items()
            if re.fullmatch(r"DOXA_[A-Z0-9_]+_(ENABLED|ALLOWANCE_USD)", k)
        }
    return {**protected, **values, **controls, **os.environ}


def configure_runtime_guard(directory: Path, runtime: str, allowance: str) -> None:
    from decimal import Decimal

    from doxa.providers.registry import provider_environment

    enabled, amount_key = provider_environment(runtime)
    amount = Decimal(allowance)
    cap = 25 if runtime == "runpod" else 75
    if not amount.is_finite() or not 0 < amount <= cap:
        raise ValueError("Enter a positive allowance within the installation ceiling")
    path = directory / "runtime-settings.json"
    from doxa.core.local_files import atomic_write, read_json_object

    values = read_json_object(path)
    values.update({enabled: "true", amount_key: str(amount)})
    atomic_write(path, json.dumps(values).encode())


def _credential_references(directory: Path, database: sqlite3.Connection | None = None) -> set[str]:
    """Read all saved versions, without creating/migrating a database or changing history."""
    path = directory.resolve() / "ledger.sqlite3"
    if not path.is_file():
        return set()

    def read(db: sqlite3.Connection) -> set[str]:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='configurations'"
        ).fetchone()
        if not exists:  # Historical foundation workspaces have no profile table yet.
            return set()
        rows = db.execute("SELECT body FROM configurations WHERE kind='profile'").fetchall()
        return {str(json.loads(row[0]).get("credential_env", "RUNPOD_API_KEY")) for row in rows}

    try:
        if database is not None:
            return read(database)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            return read(db)
    except (sqlite3.Error, ValueError, TypeError):
        raise ValueError("Workspace credential references could not be checked") from None


def secret_values(
    directory: Path | None = None,
    *,
    credential_names: Iterable[str] = (),
    database: sqlite3.Connection | None = None,
) -> tuple[str, ...]:
    """Discover credentials without losing shadowed dotenv/protected/environment values.

    Runtime resolution still uses workspace_env's existing precedence. Here every copy of
    a credential remains sensitive, including old profile aliases and short explicit keys.
    """
    explicit = os.environ.get("DOXA_ENV_FILE")
    sources = [
        {k: v for k, v in dotenv_values(Path(explicit or ".env")).items() if v is not None},
        dict(os.environ),
    ]
    names = set(credential_names)
    protected: dict[str, str] = {}
    if directory is not None:
        from doxa.core.credential_store import load_credentials

        directory = directory.expanduser().resolve()
        protected = load_credentials(directory)
        names.update(protected)
        names.update(_credential_references(directory, database))
        path = Path(explicit).expanduser().resolve() if explicit else directory / ".env"
        if not explicit and not path.is_file() and directory.name == ".doxa":
            path = directory.parent / ".env"
        sources.append({k: v for k, v in dotenv_values(path).items() if v is not None})
    values = {value for value in protected.values() if value and value != "replace_me"}
    for source in sources:
        values.update(
            value
            for name, value in source.items()
            if value
            and value != "replace_me"
            and (
                name in names
                or (
                    name.upper().endswith(("_KEY", "_TOKEN", "_PASSWORD", "_SECRET", "_CREDENTIAL"))
                    and len(value) >= 12
                )
            )
        )
    return tuple(sorted(values, key=lambda value: (-len(value), value)))


def _redact(text: str, values: tuple[str, ...], depth: int = 0) -> str:
    if depth > 128:
        raise ValueError("Credential validation requires bounded JSON nesting")
    for value in values:
        for spelling in (
            value,
            json.dumps(value)[1:-1],
            json.dumps(value, ensure_ascii=False)[1:-1],
        ):
            text = text.replace(spelling, "[REDACTED]")
    text = re.sub(r"moss_[A-Za-z0-9]{24,}", "[REDACTED]", text)
    if not text.lstrip().startswith(("{", "[", '"')):
        return text
    objects: list[list[tuple[str, Any]]] = []

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        objects.append(pairs)
        return dict(pairs)

    try:
        decoded = json.loads(text, object_pairs_hook=object_pairs)
    except json.JSONDecodeError:
        return text
    except RecursionError:
        raise ValueError("Credential validation requires bounded JSON nesting") from None

    def visit(value: Any, level: int) -> Any:
        if level > 128:
            raise ValueError("Credential validation requires bounded JSON nesting")
        if isinstance(value, str):
            return _redact(value, values, level + 1)
        if isinstance(value, list):
            return [visit(item, level + 1) for item in value]
        if isinstance(value, dict):
            return {
                _redact(key, values, level + 1): visit(item, level + 1)
                for key, item in value.items()
            }
        return value

    sanitized = visit(decoded, depth)
    # Inspect overwritten members too: an embedded JSON string retains their bytes
    # even though an ordinary JSON parser would discard them.
    changed = sanitized != decoded or any(
        visit(key, depth) != key or visit(value, depth) != value
        for pairs in objects
        for key, value in pairs
    )
    return json.dumps(sanitized, ensure_ascii=False) if changed else text


def safe_text(text: str, *, directory: Path | None = None, extra_values: Iterable[str] = ()) -> str:
    values = set(secret_values(directory)) | {v for v in extra_values if v and v != "replace_me"}
    return _redact(text, tuple(sorted(values, key=lambda value: (-len(value), value))))


def reject_secrets(
    text: str,
    directory: Path | None = None,
    *,
    credential_names: Iterable[str] = (),
    database: sqlite3.Connection | None = None,
) -> None:
    if (
        _redact(
            text, secret_values(directory, credential_names=credential_names, database=database)
        )
        != text
    ):
        raise ValueError("Secret-bearing data cannot be persisted or exported")


def reject_artifact_secrets(data: bytes, directory: Path) -> None:
    """Check ordinary text and bounded ZIP members, including original DOCX metadata.

    This is a known-credential guard, not a classifier for all sensitive documents or
    arbitrary encrypted/binary encodings. No archive member is extracted or executed.
    """
    import io
    import zipfile

    values = secret_values(directory)
    expanded = 0
    members = 0

    def check(content: bytes, depth: int) -> None:
        nonlocal expanded, members
        if depth > 4:
            raise ValueError("Credential validation requires bounded archive nesting")
        text = content.decode("utf-8", errors="ignore")
        if _redact(text, values) != text:
            raise ValueError("Secret-bearing data cannot be persisted or exported")
        stream = io.BytesIO(content)
        if not zipfile.is_zipfile(stream):
            return
        with zipfile.ZipFile(stream) as archive:
            for entry in archive.infolist():
                members += 1
                expanded += entry.file_size
                if members > 512 or expanded > 20_000_000 or entry.flag_bits & 1:
                    raise ValueError("Credential validation requires a bounded unencrypted archive")
                check(archive.read(entry), depth + 1)

    check(data, 0)
