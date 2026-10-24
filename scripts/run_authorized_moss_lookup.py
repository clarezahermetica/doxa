"""Explicit one-shot JS SDK lookup authorized in the October 24 chat.

This does not enable the app's Moss adapter, index documents, or grant memory trust.
Do not run again without another live-test authorization.
"""

import hashlib
import json
import subprocess
from decimal import Decimal
from uuid import uuid4, uuid5

from doxa.core.config import Settings
from doxa.core.controller import ConfigureRun, Controller
from doxa.core.models import (
    BudgetPolicy,
    Event,
    EventType,
    Evidence,
    Experiment,
    Provenance,
    RunState,
)
from doxa.core.secrets import local_env, safe_text
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.budget import BudgetStore

settings = Settings()
controller = Controller(settings)
controller.initialize()
request_id = uuid4()
run = controller.configure_run(
    ConfigureRun(
        idempotency_key=f"authorized-moss-sdk-lookup:{request_id}",
        experiment=Experiment(
            name="Authorized live Moss JS lookup: how to sleep",
            task_id="moss-sdk-lookup",
            task_version="1",
            environment_version="moss-js-1.21.0",
            policy_version="single-authorized-read-v1",
            evaluator_version="sdk-result-only",
            budget=BudgetPolicy(run_cap_usd=Decimal("1")),
        ),
    )
)
root = controller.inspect(run.id).events[0]
operation_id = uuid5(run.id, "load-and-query")
budgets = BudgetStore(settings.database_path)
budgets.reserve(
    run.id,
    operation_id,
    Decimal("1"),
    service="moss",
    service_cap_usd=Decimal("1"),
    request_hash=hashlib.sha256(b"agent-memory-context|how to sleep|topK=3").hexdigest(),
)
budgets.dispatch_once(operation_id)
start = RunState(
    experiment_id=root.experiment_id,
    run_id=run.id,
    trajectory_id=root.trajectory_id,
    provenance=Provenance.SYSTEM_INFERENCE,
    status="running",
    reason_code="explicit_chat_authorization_one_sdk_lookup",
)
controller.ledger.append(
    Event(
        experiment_id=root.experiment_id,
        run_id=run.id,
        trajectory_id=root.trajectory_id,
        sequence=1,
        type=EventType.RUN_STARTED,
        idempotency_key=f"{run.id}:start",
        parent_event_ids=(root.id,),
        payload=(start,),
    )
)
try:
    result = subprocess.run(
        ["node", "scripts/moss_lookup.mjs"],
        env=local_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    output = safe_text(result.stdout + result.stderr)
    success = result.returncode == 0
    state = "completed" if success else "failed"
    reason = "sdk_lookup_returned" if success else "sdk_lookup_failed"
    budgets.finish(operation_id, state)
except subprocess.TimeoutExpired:
    output = "Moss SDK lookup exceeded 60 seconds; local process stopped; billing unknown."
    success = False
    state = "failed"
    reason = "sdk_lookup_timed_out"
    budgets.finish(operation_id, "uncertain")
artifact = ArtifactStore(settings.data_dir / "artifacts").put(output.encode(), "text/plain")
evidence = Evidence(
    experiment_id=root.experiment_id,
    run_id=run.id,
    trajectory_id=root.trajectory_id,
    provenance=Provenance.TOOL_OBSERVATION,
    description=reason + "; external SDK documents are unvetted, not approved memory",
    source="@moss-js/moss@1.21.0 live lookup",
    artifacts=(artifact,),
)
previous = controller.ledger.events(run.id)[-1]
controller.ledger.append(
    Event(
        experiment_id=root.experiment_id,
        run_id=run.id,
        trajectory_id=root.trajectory_id,
        sequence=1,
        type=EventType.TOOL_RESULT_OBSERVED,
        provenance=Provenance.TOOL_OBSERVATION,
        idempotency_key=f"{run.id}:result",
        parent_event_ids=(previous.id,),
        payload=(evidence,),
    )
)
final = RunState(
    experiment_id=root.experiment_id,
    run_id=run.id,
    trajectory_id=root.trajectory_id,
    provenance=Provenance.SYSTEM_INFERENCE,
    status="completed" if success else "failed",
    reason_code=reason,
)
previous = controller.ledger.events(run.id)[-1]
controller.ledger.append(
    Event(
        experiment_id=root.experiment_id,
        run_id=run.id,
        trajectory_id=root.trajectory_id,
        sequence=1,
        type=EventType.RUN_CLOSED if success else EventType.RUN_FAILED,
        idempotency_key=f"{run.id}:closed",
        parent_event_ids=(previous.id,),
        payload=(final,),
    )
)
summary = dict(
    run_id=str(run.id),
    operation_id=str(operation_id),
    success=success,
    reserved_usd="1",
    billed_usd=None,
    output=output,
)
(settings.data_dir / "moss-live-lookup.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
print(json.dumps(summary, indent=2))
