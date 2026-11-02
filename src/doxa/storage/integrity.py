"""Read-only validation and reconstruction of the ledger's record projection."""

from pathlib import Path
from typing import Any

from doxa.core.models import ArtifactRef, Event, Experiment, ScopedRecord
from doxa.core.workspaces import validate_workspace
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.database import connection
from doxa.storage.ledger import record_adapter


def verify_workspace(directory: Path) -> dict[str, int]:
    directory = validate_workspace(directory)
    expected: dict[str, tuple[Any, ...]] = {}
    sequences: dict[str, int] = {}
    event_ids: set[str] = set()
    keys: set[str] = set()
    artifacts: dict[str, ArtifactRef] = {}

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            if {"sha256", "relative_path", "size_bytes"} <= value.keys():
                ref = ArtifactRef.model_validate(value)
                artifacts[ref.relative_path] = ref
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    with connection(directory / "ledger.sqlite3") as db:
        db.execute("BEGIN")  # one consistent read snapshot, including accounting/configuration
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Workspace integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Workspace foreign-key integrity check failed")
        if db.execute(
            "SELECT 1 FROM reservations WHERE (status='settled') != (billed_microusd IS NOT NULL)"
        ).fetchone():
            raise ValueError("Reservation settlement integrity check failed")
        rows = db.execute("SELECT * FROM events ORDER BY rowid").fetchall()
        for row in rows:
            event = Event.model_validate_json(row[6])
            identity = str(event.id)
            trajectory = str(event.trajectory_id)
            sequence = sequences.get(trajectory, 0) + 1
            if row[:6] != (
                identity,
                str(event.experiment_id),
                str(event.run_id),
                trajectory,
                sequence,
                event.idempotency_key,
            ):
                raise ValueError("Event index/sequence integrity check failed")
            if event.sequence != sequence or event.idempotency_key in keys:
                raise ValueError("Event sequence/idempotency integrity check failed")
            if any(str(p) not in event_ids for p in event.parent_event_ids):
                raise ValueError("Event ancestry integrity check failed")
            sequences[trajectory] = sequence
            event_ids.add(identity)
            keys.add(event.idempotency_key)
            collect(event.model_dump(mode="json"))
            for record in event.payload:
                key = str(record.id)
                if key in expected:
                    if (
                        not isinstance(record, Experiment)
                        or record_adapter.validate_json(expected[key][-1]) != record
                    ):
                        raise ValueError("Duplicate immutable record identity in history")
                    continue
                expected[key] = (
                    key,
                    record.kind,
                    str(event.experiment_id),
                    None if isinstance(record, Experiment) else str(event.run_id),
                    trajectory if isinstance(record, ScopedRecord) else None,
                    identity,
                    record.model_dump_json(),
                )
        actual = db.execute("SELECT * FROM records").fetchall()
        if len(actual) != len(expected):
            raise ValueError("Record projection disagrees with reconstructed history")
        for row in actual:
            target = expected.get(row[0])
            if (
                target is None
                or row[:6] != target[:6]
                or record_adapter.validate_json(row[6]) != record_adapter.validate_json(target[6])
            ):
                raise ValueError("Record projection disagrees with reconstructed history")
        triggers = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        required = {
            f"{table}_no_{op}" for table in ("events", "records") for op in ("update", "delete")
        }
        if not required <= triggers:
            raise ValueError("Missing immutable event/projection protections")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "configurations" in tables:
            from doxa.core.profiles import AgentDefinition, ModelProfile

            for kind, identity, version, body in db.execute(
                "SELECT kind,id,version,body FROM configurations"
            ):
                if kind not in {"profile", "agent"}:
                    raise ValueError("Unknown configuration kind")
                config_record = (
                    ModelProfile if kind == "profile" else AgentDefinition
                ).model_validate_json(body)
                if str(config_record.id) != identity or config_record.version != version:
                    raise ValueError("Configuration index integrity check failed")
            if not {"config_no_update", "config_no_delete"} <= triggers:
                raise ValueError("Missing immutable configuration protections")
    store = ArtifactStore(directory / "artifacts")
    for ref in artifacts.values():
        store.get(ref)
    return {"events": len(rows), "records": len(expected), "referenced_artifacts": len(artifacts)}
