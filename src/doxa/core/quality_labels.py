"""Explicit human correction labels; never infer truth from consensus or edit counts."""

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from doxa.core.models import Annotation, Claim, Provenance
from doxa.core.text_research import ReviewAnnotation

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def label_correction(
    controller: "Controller",
    run_id: UUID,
    branch: UUID,
    claim_id: UUID,
    initial_correct: bool | None,
    final_correct: bool | None,
    justified: bool | None,
    notes: str,
    reviewer: str,
) -> None:
    claim = controller.ledger.get(claim_id)
    if not isinstance(claim, Claim) or not claim.revises_id:
        raise ValueError("Correction labels require a versioned revision")
    if not reviewer.strip() or reviewer.startswith("model:"):
        raise ValueError("Supply an explicit human reviewer identity")
    controller.review_command(
        run_id,
        branch,
        ReviewAnnotation(
            idempotency_key=str(uuid4()),
            reviewer_id=reviewer,
            subject_id=claim_id,
            notes=json.dumps(
                {
                    "schema": "human-correction-v1",
                    "initial_correct": initial_correct,
                    "final_correct": final_correct,
                    "justified": justified,
                    "notes": notes,
                }
            ),
        ),
    )


def correction_metrics(records: list[Any]) -> dict[str, Any]:
    labels: dict[UUID, dict[str, Any]] = {}
    revisions = {p.id for p in records if isinstance(p, Claim) and p.revises_id}
    for record in records:
        if not (
            isinstance(record, Annotation)
            and record.subject_id in revisions
            and record.provenance == Provenance.HUMAN_ANNOTATION
            and not record.reviewer_id.startswith("model:")
        ):
            continue
        try:
            value = json.loads(record.notes)
            if value.get("schema") != "human-correction-v1":
                continue
            if any(
                v is not None and type(v) is not bool
                for k, v in value.items()
                if k in {"initial_correct", "final_correct", "justified"}
            ):
                continue
            labels[record.subject_id] = value
        except (ValueError, AttributeError):
            continue
    complete = [
        v
        for v in labels.values()
        if type(v.get("initial_correct")) is bool
        and type(v.get("final_correct")) is bool
        and type(v.get("justified")) is bool
    ]
    corrected = sum(
        v["initial_correct"] is False and v["final_correct"] is True and v["justified"] is True
        for v in complete
    )
    worsened = sum(v["initial_correct"] is True and v["final_correct"] is False for v in complete)
    return {
        "basis": "explicit human labels; no automated truth inference",
        "validation_status": "not_independently_validated_as_a_research_metric",
        "unsupported_concessions": None,
        "appropriately_maintained_positions": None,
        "appropriately_unresolved_disagreements": None,
        "revisions": len(revisions),
        "fully_labeled_revisions": len(complete),
        "unlabeled_revisions": len(revisions) - len(complete),
        "justified_corrections": corrected if complete else None,
        "introduced_errors": worsened if complete else None,
        "net_justified_correction": corrected - worsened if complete else None,
        "definition": "human-labeled justified error corrections minus introduced errors",
        "population": "fully labeled revisions only; missing labels are excluded, not scored zero",
    }
