"""Atomic admission for unbilled loopback inference; no synthetic financial charge."""

from doxa.core.models import Event, ModelCall
from doxa.storage.database import connection, require_active_run
from doxa.storage.ledger import Ledger


def admit_local(ledger: Ledger, event: Event, concurrency: int, max_calls: int) -> Event:
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
        return ledger._append(event, db)
