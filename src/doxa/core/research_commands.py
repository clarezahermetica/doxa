"""Typed research commands. These describe proposals, never direct repository writes."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from doxa.core.models import ArtifactRef, Contract
from doxa.environments.cache_policy import Candidate


class ResearchCommand(Contract):
    idempotency_key: str = Field(min_length=1, max_length=200)


class LifecycleCommand(ResearchCommand):
    operation: Literal["lifecycle"] = "lifecycle"
    status: Literal["running", "completed", "cancelled"]
    reason_code: str = Field(min_length=1)


class CloseBranchCommand(ResearchCommand):
    operation: Literal["close_branch"] = "close_branch"
    status: Literal["completed", "abandoned"]
    reason_code: str = Field(min_length=1)


class ClaimCommand(ResearchCommand):
    operation: Literal["claim"] = "claim"
    author_id: UUID
    proposition: str = Field(min_length=1, max_length=4000)
    revises_id: UUID | None = None
    status: Literal[
        "proposed", "contested", "supported", "qualified", "retracted", "superseded", "rejected"
    ] = "proposed"
    evidence_ids: tuple[UUID, ...] = ()
    contradicting_evidence_ids: tuple[UUID, ...] = ()
    rejected_evidence_ids: tuple[UUID, ...] = ()
    dependency_ids: tuple[UUID, ...] = ()
    inferred_dependency_ids: tuple[UUID, ...] = ()


class EvidenceCommand(ResearchCommand):
    operation: Literal["evidence"] = "evidence"
    description: str
    source: str
    # External evidence is an imported assertion, not independently certified.
    artifacts: tuple[ArtifactRef, ...] = ()


class DecisionCommand(ResearchCommand):
    operation: Literal["decision"] = "decision"
    claim_id: UUID
    dependency_ids: tuple[UUID, ...] = ()
    reason: str


class EnvironmentCommand(ResearchCommand):
    operation: Literal["environment"] = "environment"
    action: Literal["initialize", "read", "update", "delete", "select_policy"]
    candidate: Candidate | None = None
    key: str = "x"
    value: int | None = None


class VerifyCommand(ResearchCommand):
    operation: Literal["verify"] = "verify"
    claim_id: UUID


class CheckpointCommand(ResearchCommand):
    operation: Literal["checkpoint"] = "checkpoint"


class ForkCommand(ResearchCommand):
    operation: Literal["fork"] = "fork"
    checkpoint_id: UUID
    intervention: str = Field(min_length=1)
    continuation: Literal["historical_replay", "fresh_execution"] = "fresh_execution"


class ChallengeCommand(ResearchCommand):
    operation: Literal["challenge"] = "challenge"
    claim_id: UUID
    critic_id: UUID
    objection: str
    alleged_cases: tuple[str, ...] = ()
    proposed_revision: Candidate | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    target_decision_id: UUID | None = None


class AdjudicateCommand(ResearchCommand):
    operation: Literal["adjudicate"] = "adjudicate"
    challenge_id: UUID


class RespondCommand(ResearchCommand):
    operation: Literal["respond"] = "respond"
    challenge_id: UUID
    author_id: UUID
    response: Literal["accept", "reject", "qualify", "investigate", "defer"]


class ReflectCommand(ResearchCommand):
    operation: Literal["reflect"] = "reflect"
    trigger_event_id: UUID


class EvaluateCommand(ResearchCommand):
    operation: Literal["evaluate"] = "evaluate"
    baseline_run_id: UUID | None = None


class AnnotateCommand(ResearchCommand):
    operation: Literal["annotate"] = "annotate"
    reviewer_id: str = Field(min_length=1)
    rubric_version: Literal["trajectory-quality-v1"] = "trajectory-quality-v1"
    dimensions: dict[str, int] = Field(default_factory=dict)
    preference: Literal["A", "B", "tie", "neither"] | None = None
    other_trajectory_id: UUID | None = None
    notes: str = ""


Command = Annotated[
    LifecycleCommand
    | CloseBranchCommand
    | ClaimCommand
    | EvidenceCommand
    | DecisionCommand
    | EnvironmentCommand
    | VerifyCommand
    | CheckpointCommand
    | ForkCommand
    | ChallengeCommand
    | AdjudicateCommand
    | RespondCommand
    | ReflectCommand
    | EvaluateCommand
    | AnnotateCommand,
    Field(discriminator="operation"),
]


class CheckpointManifest(Contract):
    environment: Literal["cache-policy-state-v1"] = "cache-policy-state-v1"
    workspace: ArtifactRef
    fixture: ArtifactRef
    event_cursor: UUID
    memory_ids: tuple[UUID, ...]
    model_config_artifact: ArtifactRef
    policy_artifact: ArtifactRef
    observations: tuple[ArtifactRef, ...]
    equality: Literal["canonical_serialized_state_sha256"] = "canonical_serialized_state_sha256"
    external_effects_restorable: Literal[False] = False
