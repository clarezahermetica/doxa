from typing import TYPE_CHECKING
from uuid import UUID

from doxa.core.models import (
    Checkpoint,
    Claim,
    Contract,
    Evaluation,
    Evidence,
    Experiment,
    SourceDocument,
    Trajectory,
)
from doxa.systems.research import CommitmentChange, branch_events, commitment_diff

if TYPE_CHECKING:
    from doxa.core.controller import Controller


class Comparison(Contract):
    baseline_run_id: UUID
    treatment_run_id: UUID
    added_commitments: tuple[str, ...]
    removed_commitments: tuple[str, ...]
    baseline_metrics: dict[str, float | None]
    treatment_metrics: dict[str, float | None]
    comparable_task_version: str
    caveat: str = "Descriptive comparison; no causal or model-superiority inference."
    configuration_differences: tuple[str, ...] = ()
    evidence_equal: bool = False
    comparison_kind: str = "descriptive"


def compare(controller: "Controller", baseline: UUID, treatment: UUID) -> Comparison:
    left = controller.inspect(baseline)
    right = controller.inspect(treatment)
    configs = [controller.ledger.get(bundle.run.experiment_id) for bundle in (left, right)]
    assert all(isinstance(c, Experiment) for c in configs)
    # Explicit checks keep accidental cross-task comparisons from looking controlled.
    a = Experiment.model_validate(configs[0].model_dump())
    b = Experiment.model_validate(configs[1].model_dump())
    if (a.task_id, a.task_version, a.environment_version, a.evaluator_version) != (
        b.task_id,
        b.task_version,
        b.environment_version,
        b.evaluator_version,
    ):
        raise ValueError("Comparison requires matching task/environment/evaluator versions")
    commitments = []
    scores = []
    for bundle in (left, right):
        records = [r for event in bundle.events for r in event.payload]
        claims = [r for r in records if isinstance(r, Claim)]
        superseded = {r.revises_id for r in claims if r.revises_id}
        commitments.append({r.proposition for r in claims if r.id not in superseded})
        evaluations = [r for r in records if isinstance(r, Evaluation)]
        scores.append(evaluations[-1].metrics if evaluations else {})
    left_config = a.model_dump(
        mode="json", exclude={"id", "comparison_parent_id", "condition_changes"}
    )
    right_config = b.model_dump(
        mode="json", exclude={"id", "comparison_parent_id", "condition_changes"}
    )

    def differences(x: object, y: object, prefix: str = "") -> list[str]:
        if isinstance(x, dict) and isinstance(y, dict):
            return [
                v
                for key in sorted(x.keys() | y.keys())
                for v in differences(x.get(key), y.get(key), prefix + "." + key)
            ]
        return [] if x == y else [prefix.lstrip(".")]

    changed = tuple(differences(left_config, right_config))
    evidence = []
    for bundle in (left, right):
        docs = [p for e in bundle.events for p in e.payload if isinstance(p, SourceDocument)]
        old_sources = {d.revises_id for d in docs}
        evidence.append(
            sorted(
                (d.content.sha256, d.visibility, str(d.owner_agent_id))
                for d in docs
                if d.id not in old_sources
            )
        )
    matched = evidence[0] == evidence[1]
    kind = "matched_configuration_attempts" if not changed and matched else "descriptive"
    if (
        changed == ("task.criticism_strategy",)
        and matched
        and b.comparison_parent_id == a.id
        and b.condition_changes
    ):
        kind = "declared_criticism_strategy_condition"
    return Comparison(
        baseline_run_id=baseline,
        treatment_run_id=treatment,
        added_commitments=tuple(sorted(commitments[1] - commitments[0])),
        removed_commitments=tuple(sorted(commitments[0] - commitments[1])),
        baseline_metrics=scores[0],
        treatment_metrics=scores[1],
        comparable_task_version=a.task_id + ":" + a.task_version,
        configuration_differences=changed,
        evidence_equal=matched,
        comparison_kind=kind,
    )


class BranchComparison(Contract):
    run_id: UUID
    baseline_trajectory_id: UUID
    treatment_trajectory_id: UUID
    starting_state_equivalent: bool
    interventions: tuple[str | None, ...]
    commitments: tuple[CommitmentChange, ...]
    final_state_hashes: tuple[str | None, ...]
    evaluations: tuple[Evaluation | None, ...]
    configuration: Experiment
    caveat: str = (
        "Descriptive only. Synthetic inputs are not model-performance evidence. "
        "Shared configuration does not prove causal isolation of stochastic continuations. "
        "Evaluation resources include inherited work; branch totals must not be summed."
    )


def compare_branches(
    controller: "Controller",
    run_id: UUID,
    baseline: UUID,
    treatment: UUID,
) -> BranchComparison:
    events = controller.ledger.events(run_id)
    branches = [controller.ledger.get(i) for i in (baseline, treatment)]
    if not all(isinstance(b, Trajectory) and b.run_id == run_id for b in branches):
        raise ValueError("Comparison needs actual trajectories in the selected run")
    states, evaluations, origins = [], [], []
    for branch in (baseline, treatment):
        records = [r for e in branch_events(events, branch) for r in e.payload]
        snapshots = [r for r in records if isinstance(r, Evidence) and r.source == "cache-state-v1"]
        states.append(snapshots[-1].artifacts[0].sha256 if snapshots else None)
        results = [r for r in records if isinstance(r, Evaluation)]
        evaluations.append(results[-1] if results else None)
        # Successful restore evidence is generated atomically with the child, not
        # inferred solely from equal checkpoint IDs.
        restores = [
            r
            for e in events
            if e.trajectory_id == branch
            for r in e.payload
            if isinstance(r, Evidence)
            and r.source == "verified-cache-restore-v1"
            and r.provenance.value == "deterministic_verifier"
        ]
        import json

        origins.append(json.loads(restores[0].description)["actual_sha256"] if restores else None)
    experiment = controller.ledger.get(events[0].experiment_id)
    assert isinstance(experiment, Experiment)
    if experiment.task and experiment.task.task_type == "research_debate":
        from doxa.storage.artifacts import ArtifactStore

        store = ArtifactStore(controller.settings.data_dir / "artifacts")
        for index, child in enumerate(branches):
            if isinstance(child, Trajectory) and child.parent_id in (baseline, treatment):
                checkpoint = (
                    controller.ledger.get(child.checkpoint_id) if child.checkpoint_id else None
                )
                proofs = [
                    p
                    for e in events
                    if e.trajectory_id == child.id
                    for p in e.payload
                    if isinstance(p, Evidence)
                    and p.source == "text-snapshot-integrity-v1"
                    and p.provenance.value == "deterministic_verifier"
                ]
                if isinstance(checkpoint, Checkpoint) and any(
                    checkpoint.workspace in proof.artifacts for proof in proofs
                ):
                    store.get(checkpoint.workspace)
                    origins[index] = origins[1 - index] = checkpoint.workspace.sha256
    return BranchComparison(
        run_id=run_id,
        baseline_trajectory_id=baseline,
        treatment_trajectory_id=treatment,
        starting_state_equivalent=origins[0] is not None and origins[0] == origins[1],
        interventions=tuple(b.intervention for b in branches if isinstance(b, Trajectory)),
        commitments=commitment_diff(events, baseline, treatment),
        final_state_hashes=tuple(states),
        evaluations=tuple(evaluations),
        configuration=experiment,
    )
