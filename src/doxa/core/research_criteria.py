"""Deterministic, bounded investigation criteria; never a truth oracle."""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from doxa.core.models import Decision, Record, TaskSpecification

if TYPE_CHECKING:
    from doxa.core.investigation import ClaimThread

# Stored in the existing versioned task criteria, avoiding a new historical schema field.
REVIEW_DISPUTES = "doxa:review-disputes-v1"


def validate_criteria(task: TaskSpecification) -> None:
    if REVIEW_DISPUTES in task.evaluation_criteria and task.research_protocol != "investigation":
        raise ValueError("Review disputes requires the Investigation protocol")


@dataclass(frozen=True)
class CycleCriteria:
    conclusion: tuple[str, str, str] | None
    reason: str
    pending_challenges: tuple[UUID, ...]
    pending_reviewers: tuple[UUID, ...]
    missing_judgments: int


def assess_cycle(
    threads: list["ClaimThread"],
    records: list[Record],
    skeptics: set[UUID],
    archivists: set[UUID],
    strict: bool,
) -> CycleCriteria:
    positions = {record.id: index for index, record in enumerate(records)}
    pending: list[UUID] = []
    reviewers: set[UUID] = set()
    missing = 0
    decisions: list[Decision] = []
    contradictory = False
    for thread in threads:
        answered = {response.responds_to_id for response in thread.responses}
        pending.extend(c.id for c in thread.criticisms if c.id not in answered)
        latest = {
            d.adjudicator_id: d
            for d in thread.decisions
            if d.claim_id == thread.current.id and d.adjudicator_id in archivists
        }
        missing += len(archivists - latest.keys())
        decisions.extend(latest.values())
        outcomes = {d.outcome for d in latest.values()}
        contradictory |= "reject" in outcomes and bool(outcomes & {"retain", "qualify"})
        assessments = {a.agent_id: a for a in thread.assessments if a.claim_id == thread.current.id}
        for skeptic in skeptics:
            assessment = assessments.get(skeptic)
            last_criticism = max(
                (positions[c.id] for c in thread.criticisms if c.critic_id == skeptic), default=-1
            )
            if (
                assessment is None
                or assessment.stance not in {"accept", "withdraw"}
                or positions[assessment.id] < last_criticism
            ):
                reviewers.add(skeptic)
    conclusion = None
    reason = "further_review_requested"
    if missing or not threads:
        reason = "current_archivist_judgments_missing"
    elif contradictory:
        reason = "conflicting_archivist_judgments"
        if not strict:
            conclusion = ("concluded", "unresolved", reason)
    elif decisions and all(d.outcome == "abstain" for d in decisions):
        reason = "available_evidence_insufficient"
        conclusion = ("concluded", "unresolved", reason)
    elif strict and (pending or reviewers):
        reason = "criticism_or_review_remains_open"
    elif decisions and all(d.outcome in {"retain", "qualify", "reject"} for d in decisions):
        conclusions = {"rejected" if d.outcome == "reject" else "supported" for d in decisions}
        reason = "archivist_judgments_recorded_not_independent_truth"
        conclusion = ("concluded", conclusions.pop() if len(conclusions) == 1 else "mixed", reason)
    return CycleCriteria(
        conclusion, reason, tuple(pending), tuple(sorted(reviewers, key=str)), missing
    )
