"""Explicit immutable research attempts, with a narrow controlled prompt condition."""

from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid5

from doxa.core.controller import ConfigureRun
from doxa.core.models import Experiment, Run

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def new_attempt(
    controller: "Controller",
    run_id: UUID,
    *,
    criticism_strategy: Literal["evidence_gaps", "counterexamples", "source_conflicts"]
    | None = None,
    idempotency_key: str,
) -> Run:
    previous = controller.inspect(run_id).run
    experiment = controller.ledger.get(previous.experiment_id)
    assert isinstance(experiment, Experiment)
    if previous.status in {"running", "configured"}:
        raise ValueError("Finish or cancel the existing attempt before configuring another")
    if not experiment.task or experiment.task.task_type != "research_debate":
        raise ValueError("New research attempts require a research-debate configuration")
    if criticism_strategy:
        if criticism_strategy == experiment.task.criticism_strategy:
            raise ValueError("Treatment must change the declared criticism strategy")
        experiment = experiment.model_copy(
            update={
                "id": uuid5(experiment.id, "condition:" + idempotency_key),
                "comparison_parent_id": experiment.id,
                "condition_changes": {
                    "criticism_strategy": {
                        "before": experiment.task.criticism_strategy,
                        "after": criticism_strategy,
                    }
                },
                "task": experiment.task.model_copy(
                    update={"criticism_strategy": criticism_strategy}
                ),
            }
        )
    # Sources are imported explicitly into each attempt. Comparison separately checks
    # source content hashes before calling attempts matched or controlled.
    return controller.configure_run(
        ConfigureRun(
            experiment=experiment,
            mode=previous.mode,
            execution_kind=previous.execution_kind,
            idempotency_key=idempotency_key,
        )
    )
