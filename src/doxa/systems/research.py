"""Pure research projections and rules. Persistence is owned by Controller commands."""

from typing import Literal
from uuid import UUID

from doxa.core.models import (
    Claim,
    Contract,
    Decision,
    Event,
    ReflectionDecision,
    Trajectory,
)


def branch_events(events: list[Event], branch: UUID, cursor: UUID | None = None) -> list[Event]:
    """Inherit only the ancestor prefix pinned at each fork, never its future writes."""
    trajectories = {r.id: r for e in events for r in e.payload if isinstance(r, Trajectory)}
    if branch not in trajectories:
        raise ValueError("Unknown trajectory")
    end = len(events)
    if cursor is not None:
        matches = [i for i, e in enumerate(events) if e.id == cursor]
        if not matches:
            raise ValueError("Unknown event cursor")
        end = matches[0] + 1
    trajectory = trajectories[branch]
    inherited: list[Event] = []
    cutoff: UUID | None
    if trajectory.parent_id:
        from doxa.core.models import Checkpoint

        if trajectory.checkpoint_id:
            checkpoint = next(
                r
                for e in events
                for r in e.payload
                if isinstance(r, Checkpoint) and r.id == trajectory.checkpoint_id
            )
            cutoff = checkpoint.event_cursor
        else:
            cutoff = trajectory.fork_event_id
        inherited = branch_events(events, trajectory.parent_id, cutoff)
    return inherited + [e for e in events[:end] if e.trajectory_id == branch]


def commitments(events: list[Event], branch: UUID, cursor: UUID | None = None) -> tuple[Claim, ...]:
    claims = [
        r for e in branch_events(events, branch, cursor) for r in e.payload if isinstance(r, Claim)
    ]
    revised = {r.revises_id for r in claims}
    return tuple(r for r in claims if r.id not in revised)


def impact(events: list[Event], branch: UUID, upstream: UUID) -> tuple[UUID, ...]:
    """Conservative transitive review flags; never infer a downstream truth value."""
    records = [
        r
        for e in branch_events(events, branch)
        for r in e.payload
        if isinstance(r, (Claim, Decision))
    ]
    affected = {upstream}
    while True:
        extra = {r.id for r in records if set(r.dependency_ids) & affected}
        if extra.issubset(affected):
            return tuple(sorted(affected - {upstream}, key=str))
        affected |= extra


class CommitmentChange(Contract):
    commitment_id: UUID
    before_id: UUID | None
    after_id: UUID | None
    author_id: UUID | None
    added_evidence: tuple[UUID, ...] = ()
    rejected_evidence: tuple[UUID, ...] = ()
    affected_ids: tuple[UUID, ...] = ()
    before_proposition: str | None = None
    after_proposition: str | None = None
    before_status: str | None = None
    after_status: str | None = None
    removed_evidence: tuple[UUID, ...] = ()
    contradicting_evidence: tuple[UUID, ...] = ()
    declared_dependencies: tuple[UUID, ...] = ()
    inferred_dependencies: tuple[UUID, ...] = ()


def commitment_diff(
    events: list[Event],
    left: UUID,
    right: UUID,
    before_cursor: UUID | None = None,
    after_cursor: UUID | None = None,
) -> tuple[CommitmentChange, ...]:
    a = {r.commitment_id or r.id: r for r in commitments(events, left, before_cursor)}
    b = {r.commitment_id or r.id: r for r in commitments(events, right, after_cursor)}
    result = []
    for identity in sorted(a.keys() | b.keys(), key=str):
        old, new = a.get(identity), b.get(identity)
        if old == new:
            continue
        result.append(
            CommitmentChange(
                commitment_id=identity,
                before_id=old.id if old else None,
                after_id=new.id if new else None,
                author_id=new.author_id if new else None,
                added_evidence=tuple(
                    i for i in new.evidence_ids if not old or i not in old.evidence_ids
                )
                if new
                else (),
                rejected_evidence=new.rejected_evidence_ids if new else (),
                affected_ids=new.reconsider_ids if new else (),
                before_proposition=old.proposition if old else None,
                after_proposition=new.proposition if new else None,
                before_status=old.status if old else None,
                after_status=new.status if new else None,
                removed_evidence=tuple(
                    i for i in old.evidence_ids if not new or i not in new.evidence_ids
                )
                if old
                else (),
                contradicting_evidence=new.contradicting_evidence_ids if new else (),
                declared_dependencies=new.dependency_ids if new else (),
                inferred_dependencies=new.inferred_dependency_ids if new else (),
            )
        )
    return tuple(result)


class Signals(Contract):
    """Derived observations; callers cannot assert verifier success or remaining funds."""

    signal: str
    exhausted: bool = False
    success: bool = False
    failed: bool = False
    regression: bool = False
    checkpoint: bool = False
    validated_criticism: bool = False
    unsupported_criticism: bool = False
    contradiction: bool = False
    uncertainty: bool = False
    verified_memory: bool = False
    repeated_failures: int = 0


Action = Literal[
    "continue", "verify", "retrieve", "critique", "reflect", "rollback", "escalate", "stop"
]


def reflection_rule(
    signals: Signals,
    prior: tuple[ReflectionDecision, ...],
    cap: int,
) -> tuple[Action, str]:
    # First-match order is part of adaptive-v1. A decision proposes an action;
    # paid dispatch still passes through the separate persistent spending guard.
    if signals.exhausted:
        return "stop", "01_hard_resource_stop"
    if signals.success:
        return "stop", "02_verified_success_skip"
    if any(p.trigger_event_id for p in prior if p.signal == signals.signal):
        return "escalate", "03_repeated_trigger"
    if signals.regression and signals.checkpoint:
        return "rollback", "04_verified_regression"
    if signals.repeated_failures >= 3:
        return "escalate", "05_stagnation"
    if signals.contradiction:
        return "verify", "06_contradiction"
    interventions = sum(p.action in {"reflect", "critique"} for p in prior)
    if signals.validated_criticism:
        return (
            ("reflect", "07_validated_criticism")
            if interventions < cap
            else ("escalate", "07_intervention_cap")
        )
    if signals.unsupported_criticism:
        return "continue", "08_unsupported_objection_skip"
    if signals.failed:
        if not prior or prior[-1].action != "verify":
            return "verify", "09_test_failure"
        return (
            ("critique", "10_targeted_critique")
            if interventions < cap
            else ("escalate", "10_intervention_cap")
        )
    if signals.uncertainty:
        return "retrieve", "11_seek_evidence"
    if signals.verified_memory:
        return "retrieve", "12_available_verified_memory"
    return "continue", "13_no_intervention"
