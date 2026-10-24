import sqlite3
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from pydantic import TypeAdapter

from doxa.core.models import (
    Annotation,
    Challenge,
    Checkpoint,
    Claim,
    CouncilMessage,
    Decision,
    Event,
    EventType,
    Experiment,
    Memory,
    Provenance,
    Record,
    Run,
    RunState,
    ScopedRecord,
    Trajectory,
    Verification,
)
from doxa.core.secrets import reject_secrets
from doxa.storage.database import connection

# Pydantic versions differ in typing the constructor's runtime Annotated alias.
# Bridge only that dynamic input; retain precise typed validation output.
record_adapter: TypeAdapter[Record] = TypeAdapter(cast(Any, Record))


class LedgerConflict(ValueError):
    pass


class Ledger:
    """Atomic event + immutable record index. Writers are serialized by SQLite.

    This is an internal repository, not an untrusted event-ingestion endpoint.
    Higher-level transitions belong to the deterministic controller.
    """

    def __init__(self, path: Path):
        self.path = path

    def append(self, event: Event) -> Event:
        return self.append_batch((event,))[0]

    def append_batch(self, events: tuple[Event, ...]) -> tuple[Event, ...]:
        """One serialized transaction for a consequential multi-event transition."""
        for event in events:
            reject_secrets(event.model_dump_json())
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            return tuple(self._append(event, db) for event in events)

    def _append(self, event: Event, db: sqlite3.Connection) -> Event:
        # Also protect callers composing ledger writes into a financial transaction.
        reject_secrets(event.model_dump_json())
        existing = db.execute(
            "SELECT body FROM events WHERE idempotency_key=?", (event.idempotency_key,)
        ).fetchone()
        if existing:
            saved = Event.model_validate_json(existing[0])
            # IDs/timestamp/sequence are allocated at commit, not part of command identity.
            excluded = {"id", "timestamp", "sequence"}
            if saved.model_dump(exclude=excluded) != event.model_dump(exclude=excluded):
                raise LedgerConflict("Idempotency key reused with different content")
            return saved

        if event.expected_cursor is not None:
            cursor = db.execute(
                "SELECT id FROM events WHERE trajectory_id=? ORDER BY rowid DESC LIMIT 1",
                (str(event.expected_trajectory_id),),
            ).fetchone()
            if cursor is None or cursor[0] != str(event.expected_cursor):
                raise LedgerConflict("Branch changed while command was being prepared")

        def find(record_id: UUID) -> Record:
            for record in event.payload:
                if record.id == record_id:
                    return record
            row = db.execute("SELECT body FROM records WHERE id=?", (str(record_id),)).fetchone()
            if row is None:
                raise LedgerConflict(f"Unknown record: {record_id}")
            return record_adapter.validate_json(row[0])

        experiment = find(event.experiment_id)
        run = find(event.run_id)
        trajectory = find(event.trajectory_id)
        if not isinstance(experiment, Experiment) or not isinstance(run, Run):
            raise LedgerConflict("Event must reference an experiment and run")
        if run.experiment_id != experiment.id or not isinstance(trajectory, Trajectory):
            raise LedgerConflict("Invalid event scope")
        if trajectory.run_id != run.id:
            raise LedgerConflict("Trajectory belongs to another run")
        for record in event.payload:
            if isinstance(record, RunState):
                row = db.execute(
                    """SELECT body FROM records WHERE run_id=?
                    AND kind='run_state' ORDER BY rowid DESC LIMIT 1""",
                    (str(run.id),),
                ).fetchone()
                current = RunState.model_validate_json(row[0]).status if row else "configured"
                allowed = {
                    "configured": {"running", "cancelled"},
                    "running": {"completed", "failed", "cancelled"},
                }
                if record.status not in allowed.get(current, set()):
                    raise LedgerConflict(f"Invalid run transition: {current} -> {record.status}")
                expected = {
                    "running": EventType.RUN_STARTED,
                    "completed": EventType.RUN_CLOSED,
                    "failed": EventType.RUN_FAILED,
                    "cancelled": EventType.RUN_CANCELLED,
                }
                if event.type != expected[record.status]:
                    raise LedgerConflict("Run state and event type disagree")
            references: list[tuple[UUID, str]] = []
            if isinstance(record, Claim):
                references.extend((i, "evidence") for i in record.evidence_ids)
                references.extend((i, "evidence") for i in record.contradicting_evidence_ids)
                references.extend((i, "evidence") for i in record.rejected_evidence_ids)
                references.extend((i, "claim") for i in record.dependency_ids)
                references.extend((i, "claim") for i in record.inferred_dependency_ids)
                if record.revises_id:
                    references.append((record.revises_id, "claim"))
            if isinstance(record, Challenge):
                references.append((record.claim_id, "claim"))
                references.extend((i, "evidence") for i in record.evidence_ids)
                if record.responds_to_id:
                    references.append((record.responds_to_id, "challenge"))
                if record.target_decision_id:
                    references.append((record.target_decision_id, "decision"))
            if isinstance(record, Decision):
                references.append((record.claim_id, "claim"))
                references.extend((i, "verification") for i in record.verification_ids)
                references.extend((i, "claim") for i in record.dependency_ids)
            if isinstance(record, Verification):
                subject = find(record.subject_id)
                if not isinstance(subject, ScopedRecord) or subject.run_id != run.id:
                    raise LedgerConflict("Verification subject is outside this run")
                references.extend((i, "evidence") for i in record.evidence_ids)
                if record.verdict != "unverified" and not record.evidence_ids:
                    raise LedgerConflict("A definitive verdict requires evidence")
            if isinstance(record, Memory):
                source = db.execute(
                    "SELECT body FROM events WHERE id=?", (str(record.source_event_id),)
                ).fetchone()
                if source is None or Event.model_validate_json(source[0]).run_id != run.id:
                    raise LedgerConflict("Memory source must exist in its run")
                if record.revises_id:
                    previous = find(record.revises_id)
                    if not isinstance(previous, Memory):
                        raise LedgerConflict("Memory revision must reference memory")
                    if (previous.scope, previous.owner_agent_id) != (
                        record.scope,
                        record.owner_agent_id,
                    ):
                        raise LedgerConflict("Sharing requires a separate explicit memory proposal")
                    # No stale branch can revive a revoked or already superseded version.
                    rows = db.execute("SELECT body FROM records WHERE kind='memory'").fetchall()
                    if any(
                        Memory.model_validate_json(r[0]).revises_id == previous.id for r in rows
                    ):
                        raise LedgerConflict("Memory version is already superseded")
                    if previous.trust in {"revoked", "rejected"}:
                        raise LedgerConflict("Revoked/rejected memories are terminal")
                elif record.trust != "quarantined":
                    raise LedgerConflict("New memories must enter quarantine")
                if record.trust == "approved":
                    for identity in record.validation_ids:
                        validation = find(identity)
                        if not isinstance(validation, Verification) or (
                            validation.verdict != "valid"
                            or validation.provenance
                            not in {
                                Provenance.DETERMINISTIC_VERIFIER,
                                Provenance.TASK_ANSWER_KEY,
                            }
                            or validation.subject_id != record.revises_id
                        ):
                            raise LedgerConflict("Promotion needs independent validation of memory")
                references.extend((i, "verification") for i in record.validation_ids)
                if record.revises_id:
                    references.append((record.revises_id, "memory"))
            if isinstance(record, Annotation):
                subject = find(record.subject_id)
                if not isinstance(subject, (ScopedRecord, Trajectory)) or subject.run_id != run.id:
                    raise LedgerConflict("Annotation subject outside run")
                if record.preferred_over_id:
                    other = find(record.preferred_over_id)
                    if not isinstance(other, Trajectory) or other.id == subject.id:
                        raise LedgerConflict("Pairwise target must be another trajectory")
            if isinstance(record, Checkpoint):
                cursor = db.execute(
                    "SELECT body FROM events WHERE id=?", (str(record.event_cursor),)
                ).fetchone()
                if cursor is None or (
                    Event.model_validate_json(cursor[0]).trajectory_id != record.trajectory_id
                ):
                    raise LedgerConflict("Checkpoint cursor must exist on its trajectory")
            if isinstance(record, CouncilMessage):
                participants = {a.id for a in experiment.agents}
                if record.sender_id not in participants or (
                    record.target_id is not None and record.target_id not in participants
                ):
                    raise LedgerConflict("Unknown Council participant")
            for identity, kind in references:
                target = find(identity)
                if (
                    target.kind != kind
                    or not isinstance(target, ScopedRecord)
                    or (target.run_id != run.id)
                ):
                    raise LedgerConflict("Invalid typed causal reference")
            if isinstance(record, Run) and record.experiment_id != experiment.id:
                raise LedgerConflict("Cross-experiment run")
            if isinstance(record, Trajectory):
                if record.run_id != run.id:
                    raise LedgerConflict("Cross-run trajectory")
                if record.parent_id:
                    parent_row = db.execute(
                        "SELECT body FROM records WHERE id=?", (str(record.parent_id),)
                    ).fetchone()
                    if parent_row is None:
                        raise LedgerConflict("Parent trajectory must already exist")
                    parent = record_adapter.validate_json(parent_row[0])
                    if not isinstance(parent, Trajectory) or parent.run_id != run.id:
                        raise LedgerConflict("Invalid parent trajectory")
                    if record.fork_event_id:
                        origin = db.execute(
                            "SELECT body FROM events WHERE id=?", (str(record.fork_event_id),)
                        ).fetchone()
                        if origin is None or (
                            Event.model_validate_json(origin[0]).trajectory_id != parent.id
                        ):
                            raise LedgerConflict("Fork event must belong to parent trajectory")
                    if record.checkpoint_id:
                        checkpoint = find(record.checkpoint_id)
                        if checkpoint.kind != "checkpoint" or checkpoint.trajectory_id != parent.id:
                            raise LedgerConflict("Checkpoint must belong to parent")
            if isinstance(record, ScopedRecord) and (
                record.experiment_id != experiment.id
                or record.run_id != run.id
                or record.trajectory_id != trajectory.id
            ):
                raise LedgerConflict("Record scope differs from event scope")
        parents = set(event.parent_event_ids)
        for record in event.payload:
            if isinstance(record, Trajectory) and record.fork_event_id:
                parents.add(record.fork_event_id)
        for parent_id in parents:
            row = db.execute("SELECT body FROM events WHERE id=?", (str(parent_id),)).fetchone()
            if row is None or Event.model_validate_json(row[0]).run_id != run.id:
                raise LedgerConflict("Causal parent must exist in the same run")
        sequence = db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE trajectory_id=?",
            (str(event.trajectory_id),),
        ).fetchone()[0]
        saved = event.model_copy(update={"sequence": sequence})
        db.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?)",
            (
                str(saved.id),
                str(saved.experiment_id),
                str(saved.run_id),
                str(saved.trajectory_id),
                saved.sequence,
                saved.idempotency_key,
                saved.model_dump_json(),
            ),
        )
        for record in saved.payload:
            if isinstance(record, Experiment):
                # Configurations may be referenced by concurrent run commands.
                # Compare and reuse atomically instead of racing an outer read.
                prior = db.execute(
                    "SELECT body FROM records WHERE id=?", (str(record.id),)
                ).fetchone()
                if prior:
                    if record_adapter.validate_json(prior[0]) != record:
                        raise LedgerConflict("Experiment configuration identity conflict")
                    continue
            db.execute(
                "INSERT INTO records VALUES (?,?,?,?,?,?,?)",
                (
                    str(record.id),
                    record.kind,
                    str(saved.experiment_id),
                    None if isinstance(record, Experiment) else str(saved.run_id),
                    str(saved.trajectory_id) if isinstance(record, ScopedRecord) else None,
                    str(saved.id),
                    record.model_dump_json(),
                ),
            )
        return saved

    def events(self, run_id: UUID) -> list[Event]:
        with connection(self.path) as db:
            rows = db.execute(
                "SELECT body FROM events WHERE run_id=? ORDER BY rowid", (str(run_id),)
            ).fetchall()
        return [Event.model_validate_json(row[0]) for row in rows]

    def records(self, kind: str | None = None) -> list[Record]:
        with connection(self.path) as db:
            rows = db.execute(
                "SELECT body FROM records WHERE (? IS NULL OR kind=?) ORDER BY rowid", (kind, kind)
            ).fetchall()
        return [record_adapter.validate_json(row[0]) for row in rows]

    def get(self, record_id: UUID) -> Record:
        with connection(self.path) as db:
            row = db.execute("SELECT body FROM records WHERE id=?", (str(record_id),)).fetchone()
        if row is None:
            raise KeyError(str(record_id))
        return record_adapter.validate_json(row[0])
