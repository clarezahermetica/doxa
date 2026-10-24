from decimal import Decimal
from uuid import uuid4

import pytest

from doxa.core.controller import ConfigureRun, Controller
from doxa.core.models import ArtifactRef, BudgetPolicy
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.budget import BudgetExceeded, BudgetStore


def test_artifact_roundtrip_tampering_and_paths(tmp_path):
    store = ArtifactStore(tmp_path)
    ref = store.put(b"synthetic artifact")
    assert store.put(b"synthetic artifact") == ref
    assert store.get(ref) == b"synthetic artifact"
    with pytest.raises(ValueError):
        ArtifactRef(sha256=ref.sha256, relative_path="../escape", size_bytes=1)
    (tmp_path / ref.relative_path).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="integrity"):
        store.get(ref)


def test_budget_persistence_idempotency_unknown_and_settlement(
    controller: Controller,
    command: ConfigureRun,
):
    run = controller.configure_run(command)
    path = controller.settings.database_path
    budget = BudgetStore(path)
    operation = uuid4()
    budget.reserve(run.id, operation, Decimal("0.75"))
    BudgetStore(path).reserve(run.id, operation, Decimal("0.75"))
    budget.settle(operation, None)
    with pytest.raises(BudgetExceeded):
        budget.reserve(run.id, uuid4(), Decimal("0.5"))
    budget.settle(operation, Decimal("0.2"))
    budget.reserve(run.id, uuid4(), Decimal("0.8"))
    with pytest.raises(ValueError, match="immutable"):
        budget.settle(operation, Decimal("0.1"))


def test_global_cap_spans_runs(controller: Controller, command: ConfigureRun):
    experiment = command.experiment.model_copy(
        update={
            "budget": BudgetPolicy(run_cap_usd=Decimal("75")),
        }
    )
    a = controller.configure_run(command.model_copy(update={"experiment": experiment}))
    b = controller.configure_run(
        command.model_copy(
            update={
                "experiment": experiment,
                "idempotency_key": "second-run",
            }
        )
    )
    budget = BudgetStore(controller.settings.database_path)
    budget.reserve(a.id, uuid4(), Decimal("50"))
    with pytest.raises(BudgetExceeded, match="Aggregate"):
        budget.reserve(b.id, uuid4(), Decimal("26"))


def test_invalid_cost_is_rejected(controller: Controller, command: ConfigureRun):
    run = controller.configure_run(command)
    budget = BudgetStore(controller.settings.database_path)
    for amount in ("-1", "NaN", "Infinity", "0.0000001", "0"):
        with pytest.raises(ValueError):
            budget.reserve(run.id, uuid4(), Decimal(amount))
