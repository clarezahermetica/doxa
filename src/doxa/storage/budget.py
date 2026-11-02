from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from doxa.core.models import (
    Event,
    EventType,
    Evidence,
    Experiment,
    ModelCall,
    Provenance,
    Run,
    RunState,
)
from doxa.storage.database import connection, require_active_run
from doxa.storage.ledger import Ledger, record_adapter


class BudgetExceeded(ValueError):
    pass


def microusd(amount: Decimal) -> int:
    if not amount.is_finite() or amount < 0 or amount * 1_000_000 != int(amount * 1_000_000):
        raise ValueError("Cost must be finite, nonnegative, and exact to six decimal places")
    return int(amount * 1_000_000)


class BudgetStore:
    """Persistent reservations for a single installation's $75 aggregate ceiling.

    Unknown bills keep the full reservation. A reservation is an upper bound supplied
    by the future paid-operation controller, not a guarantee of vendor billing.
    """

    def __init__(self, path: Path):
        self.path = path

    def reserve(
        self,
        run_id: UUID,
        operation_id: UUID,
        upper_bound_usd: Decimal,
        *,
        service: str | None = None,
        service_cap_usd: Decimal | None = None,
        request_hash: str | None = None,
        max_calls: int | None = None,
    ) -> None:
        amount = microusd(upper_bound_usd)
        if amount <= 0:
            raise ValueError("A positive known upper bound is required")
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT run_id,reserved_microusd FROM reservations WHERE id=?", (str(operation_id),)
            ).fetchone()
            if existing:
                if existing != (str(run_id), amount):
                    raise ValueError("Reservation identity conflict")
                if service is not None:
                    operation = db.execute(
                        "SELECT service,request_hash FROM operations WHERE id=?",
                        (str(operation_id),),
                    ).fetchone()
                    if operation != (service, request_hash):
                        raise ValueError("Operation request identity conflict")
                return
            row = db.execute("SELECT body FROM records WHERE id=?", (str(run_id),)).fetchone()
            run = record_adapter.validate_json(row[0]) if row else None
            if not isinstance(run, Run):
                raise ValueError("Unknown run")
            row = db.execute(
                "SELECT body FROM records WHERE id=?", (str(run.experiment_id),)
            ).fetchone()
            experiment = record_adapter.validate_json(row[0])
            assert isinstance(experiment, Experiment)
            total, run_total = db.execute(
                """SELECT
                COALESCE(SUM(COALESCE(billed_microusd,reserved_microusd)),0),
                COALESCE(SUM(CASE WHEN run_id=? THEN
                    COALESCE(billed_microusd,reserved_microusd) ELSE 0 END),0)
                FROM reservations""",
                (str(run_id),),
            ).fetchone()
            if total + amount > 75_000_000:
                raise BudgetExceeded("Aggregate $75 ceiling exceeded")
            if run_total + amount > microusd(experiment.budget.run_cap_usd):
                raise BudgetExceeded("Run ceiling exceeded")
            if service is not None:
                if service_cap_usd is None or request_hash is None:
                    raise ValueError("Service operations require a cap and request hash")
                cap = microusd(service_cap_usd)
                if service == "runpod" and cap > 25_000_000:
                    raise BudgetExceeded("RunPod allowance cannot exceed reported $25 allocation")
                service_total = db.execute(
                    """SELECT COALESCE(SUM(
                    COALESCE(r.billed_microusd,r.reserved_microusd)),0)
                    FROM reservations r JOIN operations o ON r.id=o.id WHERE o.service=?""",
                    (service,),
                ).fetchone()[0]
                if service_total + amount > cap:
                    raise BudgetExceeded("Service allowance exceeded")
                count = db.execute(
                    """SELECT COUNT(*) FROM reservations r
                    JOIN operations o ON r.id=o.id WHERE r.run_id=?""",
                    (str(run_id),),
                ).fetchone()[0]
                if max_calls is not None and count >= max_calls:
                    raise BudgetExceeded("Model/service call limit reached")
            db.execute(
                "INSERT INTO reservations VALUES (?,?,?,NULL,'reserved')",
                (
                    str(operation_id),
                    str(run_id),
                    amount,
                ),
            )
            if service is not None:
                db.execute(
                    "INSERT INTO operations VALUES (?,?,?,?)",
                    (str(operation_id), service, request_hash, "prepared"),
                )

    def dispatch_once(self, operation_id: UUID, concurrency: int = 1) -> None:
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT service,state FROM operations WHERE id=?", (str(operation_id),)
            ).fetchone()
            if row is None or row[1] != "prepared":
                raise BudgetExceeded("Operation already dispatched or requires reconciliation")
            owner = db.execute(
                "SELECT run_id FROM reservations WHERE id=?", (str(operation_id),)
            ).fetchone()
            require_active_run(db, owner[0])
            uncertain = db.execute(
                "SELECT COUNT(*) FROM operations WHERE service=? AND state='uncertain'", (row[0],)
            ).fetchone()[0]
            if uncertain:
                raise BudgetExceeded("Service concurrency/uncertain-operation guard reached")
            active = db.execute(
                """SELECT COUNT(*) FROM operations WHERE service=?
                AND state IN ('in_flight','uncertain')""",
                (row[0],),
            ).fetchone()[0]
            if active >= concurrency:
                raise BudgetExceeded("Service concurrency/uncertain-operation guard reached")
            db.execute("UPDATE operations SET state='in_flight' WHERE id=?", (str(operation_id),))

    def finish(self, operation_id: UUID, state: str) -> None:
        if state not in {"uncertain", "completed", "failed"}:
            raise ValueError("Invalid operation outcome")
        with connection(self.path) as db, db:
            db.execute(
                """UPDATE operations SET state=? WHERE id=? AND state='in_flight' """,
                (state, str(operation_id)),
            )

    def complete_call(
        self,
        operation_id: UUID,
        state: str,
        billed_usd: Decimal | None,
        event: Event,
        ledger: Ledger,
    ) -> Event:
        """Persist observed response/error and durable operation state atomically."""
        if state not in {"completed", "failed", "uncertain"}:
            raise ValueError("Invalid operation outcome")
        amount = microusd(billed_usd) if billed_usd is not None else None
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            operation = db.execute(
                "SELECT state FROM operations WHERE id=?", (str(operation_id),)
            ).fetchone()
            if operation is None:
                raise ValueError("Unknown provider operation")
            if operation[0] not in {"in_flight", state}:
                raise ValueError("Provider operation cannot transition from its durable state")
            if amount is not None:
                prior = db.execute(
                    "SELECT billed_microusd FROM reservations WHERE id=?", (str(operation_id),)
                ).fetchone()[0]
                if prior is not None and prior != amount:
                    raise ValueError("Settled charge is immutable")
                db.execute(
                    "UPDATE reservations SET billed_microusd=?,status='settled' WHERE id=?",
                    (amount, str(operation_id)),
                )
            db.execute("UPDATE operations SET state=? WHERE id=?", (state, str(operation_id)))
            return ledger._append(event, db)

    def operations(self) -> list[dict[str, str | int | None]]:
        with connection(self.path) as db:
            rows = db.execute("""SELECT o.id,r.run_id,o.service,o.state,
                r.reserved_microusd,r.billed_microusd FROM operations o
                JOIN reservations r ON r.id=o.id ORDER BY o.rowid""").fetchall()
        names = ("id", "run_id", "service", "state", "reserved_microusd", "billed_microusd")
        return [dict(zip(names, row, strict=True)) for row in rows]

    def reconcile(
        self,
        operation_id: UUID,
        billed_usd: Decimal,
        *,
        ledger: Ledger | None = None,
        event: Event | None = None,
    ) -> None:
        # Operator-supplied vendor reconciliation; never infer a zero bill from an error.
        amount = microusd(billed_usd)
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT billed_microusd FROM reservations WHERE id=?", (str(operation_id),)
            ).fetchone()
            if row is None:
                raise ValueError("Unknown reservation")
            if row[0] is not None and row[0] != amount:
                raise ValueError("Settled charge is immutable")
            db.execute(
                "UPDATE reservations SET billed_microusd=?,status='settled' WHERE id=?",
                (amount, str(operation_id)),
            )
            db.execute("UPDATE operations SET state='completed' WHERE id=?", (str(operation_id),))
            if ledger is not None and event is not None:
                ledger._append(event, db)

    def recover_interrupted(self, run_id: UUID, ledger: Ledger) -> None:
        """Operator recovery after cancellation/failure, never a remote cancellation claim."""
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            states = db.execute(
                "SELECT body FROM records WHERE run_id=? AND kind='run_state' "
                "ORDER BY rowid DESC LIMIT 1",
                (str(run_id),),
            ).fetchone()
            if states is None or RunState.model_validate_json(states[0]).status not in {
                "cancelled",
                "failed",
                "completed",
            }:
                raise ValueError("Cancel the interrupted run before recovering its call states")
            operations = db.execute(
                "SELECT o.id,o.state FROM operations o JOIN reservations r ON o.id=r.id "
                "WHERE r.run_id=? AND o.state IN ('prepared','in_flight')",
                (str(run_id),),
            ).fetchall()
            previous_row = db.execute(
                "SELECT body FROM events WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (str(run_id),)
            ).fetchone()
            previous = Event.model_validate_json(previous_row[0])
            for identity, state in operations:
                outcome = "uncertain" if state == "in_flight" else "failed"
                evidence = Evidence(
                    id=uuid5(UUID(identity), "recovery"),
                    experiment_id=previous.experiment_id,
                    run_id=run_id,
                    trajectory_id=previous.trajectory_id,
                    provenance=Provenance.TOOL_OBSERVATION,
                    source="durable-operation-recovery-v1",
                    description=f"Operation {identity}: {state} -> {outcome}; "
                    "reservation retained; "
                    "remote billing/cancellation unverified",
                )
                event = Event(
                    id=uuid5(UUID(identity), "recovery-event"),
                    experiment_id=previous.experiment_id,
                    run_id=run_id,
                    trajectory_id=previous.trajectory_id,
                    sequence=1,
                    type=EventType.PROVIDER_FAILED,
                    provenance=Provenance.TOOL_OBSERVATION,
                    parent_event_ids=(previous.id,),
                    idempotency_key=f"operation-recovery:{identity}",
                    payload=(evidence,),
                )
                db.execute("UPDATE operations SET state=? WHERE id=?", (outcome, identity))
                previous = ledger._append(event, db)

            local: dict[UUID, ModelCall] = {}
            for row in db.execute(
                "SELECT body FROM records WHERE run_id=? AND kind='model_call' ORDER BY rowid",
                (str(run_id),),
            ):
                call = ModelCall.model_validate_json(row[0])
                local[call.call_id] = call
            for call in local.values():
                if call.status != "started" or call.request_settings.get("location") != "loopback":
                    continue
                uncertain = call.model_copy(
                    update={
                        "id": uuid5(call.call_id, "interrupted-local"),
                        "status": "uncertain",
                        "error_category": "worker_interrupted_execution_unknown",
                    }
                )
                previous = ledger._append(
                    Event(
                        id=uuid5(call.call_id, "interrupted-local-event"),
                        experiment_id=call.experiment_id,
                        run_id=run_id,
                        trajectory_id=call.trajectory_id,
                        sequence=1,
                        type=EventType.MODEL_CALL_RECORDED,
                        parent_event_ids=(previous.id,),
                        idempotency_key=f"local-recovery:{call.call_id}",
                        payload=(uncertain,),
                    ),
                    db,
                )

    def settle(self, operation_id: UUID, billed_usd: Decimal | None) -> None:
        if billed_usd is None:
            return  # Unknown is not zero; retain the reservation.
        amount = microusd(billed_usd)
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT reserved_microusd,billed_microusd FROM reservations WHERE id=?",
                (str(operation_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown reservation")
            if row[1] is not None and row[1] != amount:
                raise ValueError("Settled charge is immutable")
            # A larger observed bill must still be recorded, then blocks future reservations.
            db.execute(
                "UPDATE reservations SET billed_microusd=?,status='settled' WHERE id=?",
                (amount, str(operation_id)),
            )
