"""Versioned wire contracts shared by storage, systems, CLI and Studio.

Records represent observable commitments, never inferred private chain-of-thought.
Revisions receive new IDs; prior records remain immutable.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )
    schema_version: Literal[1] = 1


class Role(StrEnum):
    EXECUTOR = "executor"
    SKEPTIC = "skeptic"
    RESEARCHER = "researcher"
    ARCHIVIST = "archivist"
    ORCHESTRATOR = "orchestrator"
    INDEPENDENT_VERIFIER = "independent_verifier"


class ProtocolMode(StrEnum):
    SOLO_DIRECT = "solo_direct"
    SOLO_DELIBERATIVE = "solo_deliberative"
    COLLABORATIVE = "collaborative_multi_agent"
    ADVERSARIAL = "adversarial_multi_agent"


class Provenance(StrEnum):
    MODEL_OUTPUT = "model_output"
    TOOL_OBSERVATION = "tool_observation"
    DETERMINISTIC_VERIFIER = "deterministic_verifier"
    TASK_ANSWER_KEY = "task_answer_key"
    HUMAN_ANNOTATION = "human_annotation"
    IMPORTED_SOURCE = "imported_source"
    SYSTEM_INFERENCE = "system_inference"
    LLM_EVALUATOR = "llm_evaluator"


class EventType(StrEnum):
    RUN_STARTED = "RUN_STARTED"
    RUN_CANCELLED = "RUN_CANCELLED"
    RUN_FAILED = "RUN_FAILED"
    MODEL_CALL_RECORDED = "MODEL_CALL_RECORDED"
    RETRIEVAL_RECORDED = "RETRIEVAL_RECORDED"
    EXPERIMENT_STARTED = "EXPERIMENT_STARTED"
    RUN_CREATED = "RUN_CREATED"
    AGENT_CONFIGURED = "AGENT_CONFIGURED"
    ENVIRONMENT_INITIALIZED = "ENVIRONMENT_INITIALIZED"
    OBSERVATION_RECEIVED = "OBSERVATION_RECEIVED"
    CLAIM_PROPOSED = "CLAIM_PROPOSED"
    CLAIM_REVISED = "CLAIM_REVISED"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    DECISION_RECORDED = "DECISION_RECORDED"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    TOOL_RESULT_OBSERVED = "TOOL_RESULT_OBSERVED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    CHALLENGE_SUBMITTED = "CHALLENGE_SUBMITTED"
    CHALLENGE_RESPONDED = "CHALLENGE_RESPONDED"
    VERIFICATION_RECORDED = "VERIFICATION_RECORDED"
    ADJUDICATION_RECORDED = "ADJUDICATION_RECORDED"
    REFLECTION_TRIGGERED = "REFLECTION_TRIGGERED"
    REFLECTION_SKIPPED = "REFLECTION_SKIPPED"
    ROLLBACK_REQUESTED = "ROLLBACK_REQUESTED"
    CHECKPOINT_RESTORED = "CHECKPOINT_RESTORED"
    BRANCH_CREATED = "BRANCH_CREATED"
    MEMORY_PROPOSED = "MEMORY_PROPOSED"
    MEMORY_STATUS_CHANGED = "MEMORY_STATUS_CHANGED"
    TRAJECTORY_COMPLETED = "TRAJECTORY_COMPLETED"
    EVALUATION_RECORDED = "EVALUATION_RECORDED"
    HUMAN_ANNOTATION_ADDED = "HUMAN_ANNOTATION_ADDED"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    RUN_CLOSED = "RUN_CLOSED"


class ModelAssignment(Contract):
    provider: str
    model_id: str
    settings: dict[str, JsonValue] = Field(default_factory=dict)
    instruction_version: str
    pricing_version: str | None = None


class Permissions(Contract):
    allowed_tools: tuple[str, ...] = ()
    remote_inference: bool = False
    share_memory: bool = False


class Agent(Contract):
    id: UUID = Field(default_factory=uuid4)
    role: Role
    instructions: str
    model: ModelAssignment | None = None
    permissions: Permissions = Field(default_factory=Permissions)
    memory_scope: Literal["private", "shared"] = "private"
    accepted_messages: tuple[str, ...] = ()
    display_name: str = ""
    instruction_version: str = "1"
    model_profile_id: str | None = None
    model_profile_version: int | None = None
    enabled: bool = True


class BudgetPolicy(Contract):
    run_cap_usd: Decimal = Field(default=Decimal("1"), gt=0, le=75)
    max_model_calls: int = Field(default=10, ge=0)
    max_output_tokens: int = Field(default=1024, gt=0)
    max_context_tokens: int = Field(default=8192, gt=0)
    max_tool_calls: int = Field(default=10, ge=0)
    max_retries: int = Field(default=2, ge=0, le=3)
    timeout_seconds: float = Field(default=30, gt=0)
    max_reflections_per_branch: int = Field(default=2, ge=0, le=2)


class Experiment(Contract):
    kind: Literal["experiment"] = "experiment"
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    task_id: str
    task_version: str
    environment_version: str
    policy_version: str
    evaluator_version: str
    initial_snapshot: str | None = None
    agents: tuple[Agent, ...] = ()
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)


class Run(Contract):
    kind: Literal["run"] = "run"
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    mode: ProtocolMode
    status: Literal["configured", "running", "completed", "failed", "cancelled"] = "configured"
    execution_kind: Literal["live", "synthetic", "replay"] = "live"


class Trajectory(Contract):
    kind: Literal["trajectory"] = "trajectory"
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    parent_id: UUID | None = None
    fork_event_id: UUID | None = None
    checkpoint_id: UUID | None = None
    intervention: str | None = None

    @model_validator(mode="after")
    def ancestry(self) -> Self:
        if self.parent_id is None:
            if self.fork_event_id or self.checkpoint_id or self.intervention:
                raise ValueError("Root trajectory cannot carry fork metadata")
        elif not (self.fork_event_id or self.checkpoint_id):
            raise ValueError("A child trajectory requires a fork event or checkpoint")
        if self.parent_id == self.id:
            raise ValueError("Trajectory cannot parent itself")
        return self


class ArtifactRef(Contract):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    relative_path: str = Field(pattern=r"^sha256/[0-9a-f]{2}/[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str = "application/octet-stream"


class ScopedRecord(Contract):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    run_id: UUID
    trajectory_id: UUID
    provenance: Provenance


class Claim(ScopedRecord):
    kind: Literal["claim"] = "claim"
    proposition: str
    status: Literal[
        "proposed", "contested", "supported", "rejected", "superseded", "qualified", "retracted"
    ] = "proposed"
    commitment_id: UUID | None = None
    author_id: UUID | None = None
    revises_id: UUID | None = None
    evidence_ids: tuple[UUID, ...] = ()
    dependency_ids: tuple[UUID, ...] = ()
    inferred_dependency_ids: tuple[UUID, ...] = ()
    contradicting_evidence_ids: tuple[UUID, ...] = ()
    rejected_evidence_ids: tuple[UUID, ...] = ()
    reconsider_ids: tuple[UUID, ...] = ()


class Evidence(ScopedRecord):
    kind: Literal["evidence"] = "evidence"
    description: str
    source: str
    artifacts: tuple[ArtifactRef, ...] = ()


class Decision(ScopedRecord):
    kind: Literal["decision"] = "decision"
    claim_id: UUID
    outcome: Literal["retain", "qualify", "revise", "investigate", "abstain"]
    reason: str
    verification_ids: tuple[UUID, ...] = ()
    policy_version: str
    dependency_ids: tuple[UUID, ...] = ()
    reconsider_ids: tuple[UUID, ...] = ()


class Challenge(ScopedRecord):
    kind: Literal["challenge"] = "challenge"
    claim_id: UUID
    objection: str
    proposed_revision: str | None = None
    evidence_ids: tuple[UUID, ...] = ()
    critic_id: UUID | None = None
    alleged_cases: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)
    response: Literal["accept", "reject", "qualify", "investigate", "defer"] | None = None
    responds_to_id: UUID | None = None
    target_decision_id: UUID | None = None


class Verification(ScopedRecord):
    kind: Literal["verification"] = "verification"
    subject_id: UUID
    evaluator_id: str
    evaluator_version: str
    verdict: Literal["valid", "invalid", "partially_valid", "unverified"]
    evidence_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def distinguish_judgment(self) -> Self:
        if self.provenance not in {
            Provenance.DETERMINISTIC_VERIFIER,
            Provenance.TASK_ANSWER_KEY,
            Provenance.LLM_EVALUATOR,
        }:
            raise ValueError("Verification requires explicit evaluator provenance")
        if self.provenance == Provenance.LLM_EVALUATOR and self.verdict != "unverified":
            raise ValueError("LLM evaluation alone cannot establish independent validity")
        return self


class Checkpoint(ScopedRecord):
    kind: Literal["checkpoint"] = "checkpoint"
    task_version: str
    fixture_hash: str
    workspace: ArtifactRef
    environment_config: ArtifactRef
    observations: tuple[ArtifactRef, ...] = ()
    memory_ids: tuple[UUID, ...] = ()
    model_configs: tuple[ModelAssignment, ...] = ()
    event_cursor: UUID
    manifest: ArtifactRef | None = None


class Memory(ScopedRecord):
    kind: Literal["memory"] = "memory"
    text: str
    scope: Literal["private", "shared"] = "private"
    owner_agent_id: UUID | None = None
    trust: Literal["quarantined", "approved", "rejected", "revoked"] = "quarantined"
    source_event_id: UUID
    validation_ids: tuple[UUID, ...] = ()
    eligibility: tuple[str, ...] = ()
    revises_id: UUID | None = None
    memory_id: UUID | None = None
    category: Literal["episodic", "semantic", "procedural", "reflective"] = "semantic"
    branch_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def scope_and_validation(self) -> Self:
        if self.scope == "private" and self.owner_agent_id is None:
            raise ValueError("Private memory requires an owner")
        if self.trust == "approved" and not self.validation_ids:
            raise ValueError("Approved memory requires validation references")
        return self


class Usage(Contract):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_usd: Decimal | None = Field(default=None, ge=0)
    billed_usd: Decimal | None = Field(default=None, ge=0)
    pricing_version: str | None = None
    latency_seconds: float | None = Field(default=None, ge=0)


class Evaluation(ScopedRecord):
    kind: Literal["evaluation"] = "evaluation"
    evaluator_version: str
    baseline_run_id: UUID | None = None
    metrics: dict[str, float | None]
    denominators: dict[str, int] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)


class Annotation(ScopedRecord):
    kind: Literal["annotation"] = "annotation"
    provenance: Literal[Provenance.HUMAN_ANNOTATION] = Provenance.HUMAN_ANNOTATION
    reviewer_id: str
    rubric_version: str
    subject_id: UUID
    labels: tuple[str, ...] = ()
    notes: str = ""
    preferred_over_id: UUID | None = None
    dimensions: dict[str, int] = Field(default_factory=dict)
    preference: Literal["A", "B", "tie", "neither"] | None = None


class CouncilMessage(ScopedRecord):
    kind: Literal["council_message"] = "council_message"
    message_type: Literal[
        "CLAIM",
        "EVIDENCE",
        "CHALLENGE",
        "RESPONSE",
        "ACTION",
        "VERIFICATION",
        "MEMORY_PROPOSAL",
        "REQUEST_EVIDENCE",
        "HANDOFF",
        "RESOLUTION",
    ]
    sender_id: UUID
    target_id: UUID | None = None
    visibility: Literal["private", "shared"]
    linked_ids: tuple[UUID, ...] = ()
    content: str


class ReflectionDecision(ScopedRecord):
    kind: Literal["reflection_decision"] = "reflection_decision"
    action: Literal[
        "continue",
        "verify",
        "retrieve",
        "critique",
        "reflect",
        "rollback",
        "fork",
        "escalate",
        "stop",
    ]
    trigger_event_id: UUID
    reason_code: str
    policy_version: str
    skipped: bool = False
    signal: str | None = None
    budget_before: dict[str, float | int | None] = Field(default_factory=dict)
    budget_after: dict[str, float | int | None] = Field(default_factory=dict)
    resulting_state: str | None = None
    considered_actions: tuple[str, ...] = ()


class RunState(ScopedRecord):
    kind: Literal["run_state"] = "run_state"
    status: Literal["running", "completed", "failed", "cancelled"]
    reason_code: str


class TrajectoryState(ScopedRecord):
    kind: Literal["trajectory_state"] = "trajectory_state"
    status: Literal["completed", "abandoned"]
    reason_code: str


class ModelCall(ScopedRecord):
    kind: Literal["model_call"] = "model_call"
    call_id: UUID
    agent_id: UUID
    assignment: ModelAssignment
    response_id: str | None = None
    reported_model_id: str | None = None
    usage: Usage = Field(default_factory=Usage)
    error_category: str | None = None
    status: Literal["completed", "failed", "uncertain"]


class RetrievalAudit(ScopedRecord):
    kind: Literal["retrieval_audit"] = "retrieval_audit"
    agent_id: UUID
    query: str
    backend: str
    index_version: str | None = None
    candidate_ids: tuple[UUID, ...] = ()
    eligible_ids: tuple[UUID, ...] = ()
    rejected_ids: tuple[UUID, ...] = ()
    latency_seconds: float = Field(ge=0)
    cost_usd: Decimal | None = Field(default=None, ge=0)
    fallback_reason: str | None = None
    conditions: tuple[str, ...] = ()


Record = Annotated[
    Experiment
    | Run
    | Trajectory
    | Claim
    | Evidence
    | Decision
    | Challenge
    | Verification
    | Checkpoint
    | Memory
    | Evaluation
    | Annotation
    | CouncilMessage
    | ReflectionDecision
    | RunState
    | TrajectoryState
    | ModelCall
    | RetrievalAudit,
    # New v1 record discriminators are additive; historical readers retain defaults.
    Field(discriminator="kind"),
]


class Event(Contract):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    run_id: UUID
    trajectory_id: UUID
    sequence: int = Field(ge=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    type: EventType
    actor_id: UUID | None = None
    actor_role: Role = Role.ORCHESTRATOR
    provenance: Provenance = Provenance.SYSTEM_INFERENCE
    parent_event_ids: tuple[UUID, ...] = ()
    model: ModelAssignment | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    idempotency_key: str = Field(min_length=1)
    payload: tuple[Record, ...] = ()
    command_digest: str | None = None
    expected_cursor: UUID | None = None
    expected_trajectory_id: UUID | None = None

    @model_validator(mode="after")
    def utc_timestamp(self) -> Self:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() != UTC.utcoffset(None):
            raise ValueError("Event timestamp must be UTC-aware")
        return self
