"""Reproduce a preregistered offline engineering fixture using existing controller ports.

This is acceptance machinery, not a research runtime or a live-model quality study.
The terminal operator procedure is documented separately; no private DB writes occur here.
"""

import argparse
import asyncio
import hashlib
import json
import os
import socket
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid5

from doxa.core.comparison import compare_branches
from doxa.core.config import Settings
from doxa.core.controller import Controller
from doxa.core.exports import export_run
from doxa.core.models import (
    BudgetPolicy,
    Checkpoint,
    ContextManifest,
    CouncilLimits,
    Decision,
    Evaluation,
    Experiment,
    ModelCall,
    Role,
    TaskSpecification,
    Trajectory,
)
from doxa.core.research_demo import experiment as six_system_experiment
from doxa.core.text_research import ReviewClaim, ReviewEvaluate, ReviewFork
from doxa.core.workbench import (
    DebateExecution,
    DebateRuntime,
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)
from doxa.environments.cache_policy import CacheFixture, Candidate, verify

QUESTION = (
    "Does stale_on_update satisfy the supplied read/update/delete coherence contract, "
    "what bounded correction is justified, and can these materials establish which policy "
    "is fastest? Restrict conclusions to cache-policy v1's finite oracle."
)
OPENING = "Synthetic assertion: all three policies satisfy the full coherence contract."
BOUNDED = (
    "Synthetic revision: only invalidate_all passes all three fixed v1 oracle checks; "
    "these materials establish no fastest policy."
)
SECOND = "Synthetic assertion: stale_on_delete fails the fixed v1 delete-coherence check."
RANK = {Role.RESEARCHER: 0, Role.EXECUTOR: 1, Role.SKEPTIC: 2, Role.ARCHIVIST: 3}


@dataclass(frozen=True)
class FixtureSource:
    id: UUID
    text: str


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def inspect_archive(path: Path) -> dict[str, Any]:
    """Independent stdlib-only hash/history inspection, without opening its source workspace."""
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        for name, expected in manifest["files"].items():
            if digest(archive.read(name)) != expected["sha256"]:
                raise ValueError("Archive content hash mismatch")
        history = json.loads(archive.read("history.json"))
        records = [p for e in history["events"] for p in e["payload"]]
        return {
            "run_id": history["run"]["id"],
            "history_sha256": digest(archive.read("history.json")),
            "event_ids": [e["id"] for e in history["events"]],
            "record_ids": [p["id"] for p in records],
            "files_verified": len(manifest["files"]),
            "source_hashes": sorted(
                p["content"]["sha256"] for p in records if p["kind"] == "source_document"
            ),
        }


def fixture_answers(
    experiment: Experiment, branch: UUID, sources: dict[str, Any]
) -> dict[str, str]:
    """Resolve fixed fixture references using the existing generated-ID convention.

    This convention is asserted by the acceptance tests; it is not a proposed operator API.
    No model output or scientific verdict is fabricated as a verifier result.
    """
    agents = sorted(experiment.agents, key=lambda a: (RANK[a.role], str(a.id)))
    researchers = [a for a in agents if a.role == Role.RESEARCHER]
    critics = [a for a in agents if a.role == Role.SKEPTIC]
    answers = {}

    def phase(actor: Any, index: int) -> str:
        return f"round:{index}:agent:{actor.id}"

    def identity(actor: Any, index: int, kind: str) -> str:
        return str(uuid5(uuid5(branch, "generated:" + phase(actor, index)), kind))

    def claim(text: str, source: str = "S2") -> dict[str, Any]:
        doc = sources[source]
        return {
            "operation": "claim",
            "proposition": text,
            "source_ids": [str(doc.id)],
            "citation_spans": {str(doc.id): [0, len(doc.text)]},
        }

    for index in range(3):
        for actor in agents:
            body = claim(
                "Synthetic fixture note: finite tests do not establish "
                "general correctness or speed."
            )
            if index == 0 and actor.role == Role.RESEARCHER:
                body = claim(OPENING if actor.id == researchers[0].id else SECOND)
            elif index == 1 and actor.role == Role.SKEPTIC:
                critic_index = critics.index(actor)
                target = researchers[min(critic_index, len(researchers) - 1)]
                misleading = critic_index > 0
                body = {
                    "operation": "challenge",
                    "claim_id": identity(target, 0, "claim"),
                    "objection": (
                        "Synthetic misleading objection: discard the delete-failure claim because "
                        "the unverified memo is optimistic about updates."
                        if misleading
                        else "Synthetic supported objection: S2 shows update/delete failures; "
                        "qualify "
                        "the universal coherence assertion."
                    ),
                    "objection_type": "evidence_gap" if misleading else "contradiction",
                    "source_ids": [str(sources["S3" if misleading else "S2"].id)],
                    "requested_correction": "Inspect the fixed table and state its actual scope.",
                }
            elif index == 2 and actor.role == Role.RESEARCHER and critics:
                own_index = researchers.index(actor)
                if own_index < len(critics):
                    body = {
                        "operation": "respond",
                        "challenge_id": identity(critics[own_index], 1, "challenge"),
                        "response": "qualify" if own_index == 0 else "reject",
                        "reason": (
                            "Synthetic reference response: read the explicit fail cells in S2; "
                            "S3 has no independent measurement."
                        ),
                    }
                    if own_index == 0:
                        body["revised_proposition"] = BOUNDED
            elif index == 2 and actor.role == Role.ARCHIVIST and critics:
                body = {
                    "operation": "adjudicate",
                    "challenge_id": identity(critics[-1], 1, "challenge"),
                    "outcome": "retain" if len(critics) > 1 else "qualify",
                    "reason": (
                        "Synthetic adjudication fixture: the memo does not defeat the finite "
                        "reference table. This is not an independently inferred truth verdict."
                    ),
                }
            answers[phase(actor, index)] = json.dumps({"research_action": body})
    return answers


def conduct(workspace: Path, output: Path, corpus: Path) -> dict[str, Any]:
    workspace, output, corpus = workspace.resolve(), output.resolve(), corpus.resolve()
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError("Canonical acceptance requires a new empty workspace")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose a new empty output directory; results are never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    contents = {
        p.name.split("-")[0]: p.read_text(encoding="utf-8")
        for p in sorted((corpus / "sources").glob("*.md"))
    }
    if set(contents) != {"S1", "S2", "S3", "S4"}:
        raise ValueError("Canonical corpus is incomplete")
    reference = {
        name: verify(CacheFixture(), Candidate(policy=name))
        for name in ("invalidate_all", "stale_on_update", "stale_on_delete")
    }
    assert reference == {
        "invalidate_all": {"read": True, "update": True, "delete": True},
        "stale_on_update": {"read": True, "update": False, "delete": True},
        "stale_on_delete": {"read": True, "update": True, "delete": False},
    }
    preregistration = {
        "question": QUESTION,
        "execution": "synthetic_fixed_responses_no_inference",
        "protocol_sha256": digest((corpus / "PROTOCOL.md").read_bytes()),
        "harness_sha256": digest(Path(__file__).read_bytes()),
        "source_sha256": {name: digest(text.encode()) for name, text in contents.items()},
        "oracle_reference": reference,
        "causal_model_quality_claim": False,
    }
    (output / "preregistration.json").write_text(json.dumps(preregistration, indent=2))
    controller = Controller(Settings(data_dir=workspace))
    controller.initialize(allow_create=True)
    templates = {
        role: add_agent(
            controller,
            NewAgent(
                display_name="Canonical " + role.value,
                role=role,
                instructions="Fixed synthetic fixture. Cite supplied evidence, separate unverified "
                "assertions from finite measurements, and preserve uncertainty.",
            ),
        )
        for role in (Role.RESEARCHER, Role.SKEPTIC, Role.ARCHIVIST)
    }
    observations = {}
    # A network attempt is a failed offline acceptance, not permission to call a service.
    with (
        patch.dict(os.environ, {"DOXA_MOSS_ENABLED": "false"}),
        patch("httpx.AsyncClient.send", side_effect=AssertionError("Offline study: no HTTP")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("Offline study: no sockets")
        ),
    ):
        for condition, counts in {"A": (1, 0, 0), "B": (1, 1, 0), "C": (2, 2, 1)}.items():
            run = create_experiment(
                controller,
                NewExperiment(
                    name=f"Canonical fixed cache-evidence condition {condition}",
                    task=TaskSpecification(
                        question=QUESTION,
                        structured_actions=True,
                        staged_research=True,
                        evaluation_criteria=(
                            "source_traceability",
                            "explicit_revision",
                            "scope_limits",
                        ),
                        council=CouncilLimits(
                            rounds=3, per_agent_tokens=131072, total_tokens=1048576
                        ),
                    ),
                    participants=tuple(
                        ParticipantGroup(agent_id=template.id, count=count)
                        for template, count in zip(templates.values(), counts, strict=True)
                        if count
                    ),
                    budget=BudgetPolicy(
                        max_model_calls=20, max_context_tokens=32768, timeout_seconds=300
                    ),
                    idempotency_key="canonical-v1-" + condition,
                ),
            )
            docs = {}
            for label, text in contents.items():
                doc = import_source(
                    controller,
                    run.id,
                    ImportSource(
                        title=label + " canonical research fixture",
                        text=text,
                        source="canonical-v1/" + label,
                        idempotency_key=label,
                    ),
                )
                # Fixture helper metadata is not a ledger field or research record change.
                docs[label] = FixtureSource(doc.id, text)
            initial = controller.inspect(run.id)
            branch = next(
                p.id for e in initial.events for p in e.payload if isinstance(p, Trajectory)
            )
            experiment = controller.ledger.get(run.experiment_id)
            assert isinstance(experiment, Experiment)
            answers = fixture_answers(experiment, branch, docs)
            bundle = asyncio.run(
                DebateRuntime(controller, run.id).execute_debate(
                    DebateExecution(synthetic_answers=answers)
                )
            )
            assert bundle.run.status == "completed"
            records = [p for e in bundle.events for p in e.payload]
            assert not any(isinstance(p, ModelCall) for p in records)
            evaluation = next(
                p
                for p in reversed(records)
                if isinstance(p, Evaluation) and p.evaluator_version.startswith("text-descriptive-")
            )
            checkpoint = next(p for p in reversed(records) if isinstance(p, Checkpoint))
            fork = controller.review_command(
                run.id,
                branch,
                ReviewFork(
                    checkpoint_id=checkpoint.id,
                    intervention="Human-analysis scope restriction; no inference replay",
                    idempotency_key="analysis-fork",
                ),
            )
            child = next(p.id for p in fork.payload if isinstance(p, Trajectory))
            current = controller.review_workspace(run.id, child).current_claims
            prior = next(
                p for p in current if p.proposition == (OPENING if condition == "A" else BOUNDED)
            )
            controller.review_command(
                run.id,
                child,
                ReviewClaim(
                    author_id=prior.author_id,
                    revises_id=prior.id,
                    proposition=(
                        "Human analysis: the finite comparison cannot establish the fastest policy."
                    ),
                    source_ids=(docs["S2"].id,),
                    citation_spans={docs["S2"].id: (0, len(contents["S2"]))},
                    idempotency_key="scope-revision",
                ),
            )
            controller.review_command(
                run.id, child, ReviewEvaluate(idempotency_key="child-evaluation")
            )
            comparison = compare_branches(controller, run.id, branch, child)
            archive = export_run(controller, run.id, output / f"condition-{condition}.zip")
            inspection = inspect_archive(archive)
            actual = controller.inspect(run.id).model_dump(mode="json")
            assert inspection["event_ids"] == [e["id"] for e in actual["events"]]
            assert inspection["source_hashes"] == sorted(preregistration["source_sha256"].values())
            observations[condition] = {
                "run_id": str(run.id),
                "participants": len(experiment.agents),
                "participant_ids": [str(a.id) for a in experiment.agents],
                "contexts": sum(isinstance(p, ContextManifest) for p in records),
                "adjudications": sum(isinstance(p, Decision) for p in records),
                "metrics": evaluation.model_dump(mode="json"),
                "analysis_branch": str(child),
                "branch_changes": len(comparison.commitments),
                "archive": str(archive),
                "inspection": inspection,
                "responses_are_scripted": True,
                "model_quality_effect": None,
            }
        companion = six_system_experiment(controller)
        archive = export_run(controller, UUID(companion["run_id"]), output / "six-system-cache.zip")
        companion["archive_inspection"] = inspect_archive(archive)
    result = {
        "preregistration": preregistration,
        "conditions": observations,
        "six_system_cache_companion": companion,
        "interpretation": (
            "Procedural integration only; no live inference or causal model-quality evidence."
        ),
    }
    (output / "study-results.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "examples/canonical-research",
    )
    args = parser.parse_args()
    result = conduct(args.workspace, args.output, args.corpus)
    print(
        json.dumps(
            {
                "conditions": list(result["conditions"]),
                "output": str(args.output),
                "live_inference": False,
                "interpretation": result["interpretation"],
            }
        )
    )


if __name__ == "__main__":
    main()
