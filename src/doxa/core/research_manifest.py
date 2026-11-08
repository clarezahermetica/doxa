"""Procedural manifests and deliberately limited public summaries, never auth data."""

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from doxa.core.models import Experiment, ModelCall, ResearchOutcome, SourceDocument
from doxa.core.runtime_identity import runtime_identity

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def procedure_manifest(controller: "Controller", run_id: UUID) -> dict[str, Any]:
    bundle = controller.inspect(run_id)
    experiment = controller.ledger.get(bundle.run.experiment_id)
    assert isinstance(experiment, Experiment)
    identity = runtime_identity(controller.settings.data_dir)
    root = Path(__file__).resolve().parents[3]
    source_hash = hashlib.sha256()
    for path in sorted((root / "src/doxa").rglob("*.py")):
        if "desktop" not in path.parts:
            source_hash.update(path.relative_to(root).as_posix().encode())
            source_hash.update(path.read_bytes())
    sources = [p for e in bundle.events for p in e.payload if isinstance(p, SourceDocument)]
    return {
        "schema": "procedure-manifest-v1",
        "guarantee": "procedure, not deterministic model output",
        "application_version": identity["application_version"],
        "terminal_build": identity["terminal_build"],
        "source_commit": identity["source_commit"],
        "source_tree_sha256": source_hash.hexdigest() if (root / "src/doxa").is_dir() else None,
        "python_version": identity["python_version"],
        "experiment_id": str(experiment.id),
        "run_id": str(run_id),
        "task": experiment.task.model_dump(mode="json") if experiment.task else None,
        "agents": [a.model_dump(mode="json") for a in experiment.agents],
        "source_artifacts": [
            {
                "source_id": str(s.id),
                "version": s.version,
                "text_sha256": s.content.sha256,
                "original_sha256": s.original.sha256 if s.original else None,
            }
            for s in sources
        ],
        "limits": experiment.budget.model_dump(mode="json"),
        "requested_model_metadata": True,
        "resolved_models": None,
        "context_strategy": "required_state_and_relevant_passages_v3",
        "random_seed": None,
        "evaluation_warning": "Structural metrics/model judgments do not establish correctness.",
    }


def public_summary(controller: "Controller", run_id: UUID) -> dict[str, Any]:
    """No paths, endpoints, prompts, authentication references, source text or identities."""
    bundle = controller.inspect(run_id)
    experiment = controller.ledger.get(bundle.run.experiment_id)
    assert isinstance(experiment, Experiment)
    calls = {p.call_id: p for e in bundle.events for p in e.payload if isinstance(p, ModelCall)}
    outcome = next(
        (p for e in reversed(bundle.events) for p in e.payload if isinstance(p, ResearchOutcome)),
        None,
    )
    return {
        "schema": "public-research-summary-v1",
        "epistemic_outcome": outcome.epistemic_outcome if outcome else "unknown",
        "research_execution_status": outcome.execution_status if outcome else "unknown",
        "judgment_basis": outcome.judgment_basis if outcome else None,
        "execution_kind": bundle.run.execution_kind,
        "execution_status": bundle.run.status,
        "events": len(bundle.events),
        "calls": len(calls),
        "completed_calls": sum(c.status == "completed" for c in calls.values()),
        "control_condition": experiment.task.control_condition
        if experiment.task
        else "unspecified",
        "objective_correctness": None,
        "research_quality_improvement": None,
        "usd_cost": None,
        "warning": "Exact workspace archives are private, not sanitized public reports.",
    }
