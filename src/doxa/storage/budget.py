from decimal import Decimal
from pathlib import Path
from uuid import UUID

from doxa.core.models import Experiment, Run
from doxa.storage.database import connection
from doxa.storage.ledger import record_adapter


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

    def operations(self) -> list[dict[str, str | int | None]]:
        with connection(self.path) as db:
            rows = db.execute("""SELECT o.id,r.run_id,o.service,o.state,
                r.reserved_microusd,r.billed_microusd FROM operations o
                JOIN reservations r ON r.id=o.id ORDER BY o.rowid""").fetchall()
        names = ("id", "run_id", "service", "state", "reserved_microusd", "billed_microusd")
        return [dict(zip(names, row, strict=True)) for row in rows]

    def reconcile(self, operation_id: UUID, billed_usd: Decimal) -> None:
        # Operator-supplied vendor reconciliation; never infer a zero bill from an error.
        self.settle(operation_id, billed_usd)
        with connection(self.path) as db, db:
            db.execute("UPDATE operations SET state='completed' WHERE id=?", (str(operation_id),))

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
