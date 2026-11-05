"""Atomic admission for unbilled loopback inference; no synthetic financial charge."""

from doxa.core.models import Event, ModelCall
from doxa.storage.database import connection, require_active_run
from doxa.storage.ledger import Ledger


def admit_local(
    ledger: Ledger, event: Event, concurrency: int, max_calls: int, *, quota: bool = False
) -> Event:
    requested = event.payload[0]
    assert isinstance(requested, ModelCall)
    with connection(ledger.path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        require_active_run(db, str(requested.run_id))
        calls: dict[str, ModelCall] = {}
        starts = 0
        for row in db.execute("SELECT body FROM records WHERE kind='model_call' ORDER BY rowid"):
            call = ModelCall.model_validate_json(row[0])
            calls[str(call.call_id)] = call
            if call.run_id == requested.run_id and call.status == "started":
                starts += 1
        if starts >= max_calls or str(requested.call_id) in calls:
            raise ValueError("Local model call admission limit or replay guard reached")

        def runtime_key(call: ModelCall) -> tuple[object, ...]:
            settings = call.assignment.settings
            return (
                call.assignment.provider,
                settings.get("profile_id"),
                settings.get("profile_version"),
                call.assignment.model_id,
            )

        active = sum(
            c.status in {"started", "uncertain"} and runtime_key(c) == runtime_key(requested)
            for c in calls.values()
        )
        if active >= concurrency:
            raise ValueError("Local runtime concurrency or interrupted-call guard reached")
        if quota:
            service = str(requested.request_settings["adapter"])
            if db.execute(
                "SELECT 1 FROM quota_operations WHERE service=? "
                "AND state IN ('in_flight','uncertain')",
                (service,),
            ).fetchone():
                raise ValueError("CLI account concurrency or uncertain-operation guard reached")
            admitted = {str(c.call_id) for c in calls.values() if c.run_id == requested.run_id}
            admitted.update(
                r[0]
                for r in db.execute(
                    "SELECT id FROM reservations WHERE run_id=? UNION SELECT id FROM "
                    "quota_operations WHERE run_id=?",
                    (str(requested.run_id), str(requested.run_id)),
                )
            )
            if len(admitted) >= max_calls:
                raise ValueError("Model call admission limit reached")
            db.execute(
                "INSERT INTO quota_operations (id,run_id,service,request_hash,state) "
                "VALUES (?,?,?,?,'in_flight')",
                (str(requested.call_id), str(requested.run_id), service, requested.request_hash),
            )
        return ledger._append(event, db)
