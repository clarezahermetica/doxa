"""Text research commands: human review, immutable revisions and verified history forks.

Snapshot verification establishes serialized history equality, never argument truth.
The cache oracle and its research algorithms remain separate.
"""

import hashlib
import json
import re
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast
from uuid import UUID, uuid5

from pydantic import Field, TypeAdapter

from doxa.core.models import (
    Agent,
    Annotation,
    ArtifactRef,
    Challenge,
    Checkpoint,
    Claim,
    ClaimAssessment,
    Contract,
    Decision,
    Evaluation,
    Event,
    EventType,
    Evidence,
    Experiment,
    ModelCall,
    Provenance,
    Record,
    Role,
    ScopedRecord,
    SourceDocument,
    Trajectory,
    Usage,
)
from doxa.core.secrets import reject_secrets
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.ledger import LedgerConflict
from doxa.systems.research import branch_events, commitments, impact

if TYPE_CHECKING:
    from doxa.core.controller import Controller


class ReviewBase(Contract):
    idempotency_key: str = Field(min_length=1, max_length=200)
    reviewer_id: str = Field(default="local-operator", min_length=1, max_length=100)


class ReviewClaim(ReviewBase):
    operation: Literal["claim"] = "claim"
    author_id: UUID
    proposition: str = Field(min_length=1, max_length=4000)
    revises_id: UUID | None = None
    source_ids: tuple[UUID, ...] = ()
    dependency_ids: tuple[UUID, ...] = ()
    citation_spans: dict[UUID, tuple[int, int]] = Field(default_factory=dict)


class ReviewChallenge(ReviewBase):
    operation: Literal["challenge"] = "challenge"
    claim_id: UUID
    critic_id: UUID
    objection: str = Field(min_length=1, max_length=4000)
    source_ids: tuple[UUID, ...] = ()
    objection_type: Literal["unspecified", "evidence_gap", "contradiction", "method", "scope"] = (
        "unspecified"
    )
    requested_correction: str | None = Field(default=None, min_length=1, max_length=2000)


class ReviewResponse(ReviewBase):
    revision_of: UUID | None = None
    source_ids: tuple[UUID, ...] = ()
    operation: Literal["respond"] = "respond"
    challenge_id: UUID
    author_id: UUID
    response: Literal["accept", "reject", "qualify", "investigate", "defer"]
    reason: str = Field(min_length=1, max_length=4000)
    revised_proposition: str | None = Field(default=None, min_length=1, max_length=4000)


class ReviewAssessment(ReviewBase):
    operation: Literal["assess"] = "assess"
    claim_id: UUID
    author_id: UUID
    challenge_id: UUID | None = None
    stance: Literal["accept", "dispute", "withdraw", "insufficient_evidence"]
    reason: str = Field(min_length=1, max_length=4000)
    source_ids: tuple[UUID, ...] = ()


class ReviewDecision(ReviewBase):
    reviewer_agent_id: UUID | None = None
    operation: Literal["adjudicate"] = "adjudicate"
    claim_id: UUID | None = None
    challenge_id: UUID | None = None
    source_ids: tuple[UUID, ...] = ()
    outcome: Literal["retain", "qualify", "revise", "investigate", "abstain", "reject"]
    reason: str = Field(min_length=1, max_length=4000)


class ReviewAnnotation(ReviewBase):
    operation: Literal["annotate"] = "annotate"
    subject_id: UUID
    notes: str = Field(default="", max_length=8000)
    dimensions: dict[str, int] = Field(default_factory=dict)
    other_trajectory_id: UUID | None = None
    preference: Literal["A", "B", "tie", "neither"] | None = None


class ReviewCheckpoint(ReviewBase):
    operation: Literal["checkpoint"] = "checkpoint"


class ReviewFork(ReviewBase):
    operation: Literal["fork"] = "fork"
    checkpoint_id: UUID
    intervention: str = Field(min_length=1, max_length=2000)


class ReviewEvaluate(ReviewBase):
    operation: Literal["evaluate"] = "evaluate"


ReviewCommand = Annotated[
    ReviewClaim
    | ReviewChallenge
    | ReviewResponse
    | ReviewDecision
    | ReviewAssessment
    | ReviewAnnotation
    | ReviewCheckpoint
    | ReviewFork
    | ReviewEvaluate,
    Field(discriminator="operation"),
]
review_adapter: TypeAdapter[ReviewCommand] = TypeAdapter(cast(Any, ReviewCommand))


class TextSnapshot(Contract):
    environment: Literal["text-research-history-v1"] = "text-research-history-v1"
    event_cursor: UUID
    history: ArtifactRef
    configuration: ArtifactRef
    task: ArtifactRef
    external_effects_restorable: Literal[False] = False
    continuation: Literal["human_analysis_only"] = "human_analysis_only"


class ReviewWorkspace(Contract):
    branch: Trajectory
    events: tuple[Event, ...]
    current_claims: tuple[Claim, ...]
    unresolved_challenges: tuple[Challenge, ...]
    checkpoints: tuple[Checkpoint, ...]
    annotations: tuple[Annotation, ...]
    caveat: str = "Human review and model assertions do not establish independent truth."


RUBRIC = {"source_traceability", "counterargument_engagement", "uncertainty", "clarity"}


class TextResearch:
    def __init__(self, controller: "Controller", run_id: UUID, branch_id: UUID):
        self.controller = controller
        self.ledger = controller.ledger
        self.run = controller.inspect(run_id).run
        self.experiment = cast(Experiment, self.ledger.get(self.run.experiment_id))
        if not self.experiment.task or self.experiment.task.task_type != "research_debate":
            raise ValueError("Text review requires a research-debate task")
        branch = self.ledger.get(branch_id)
        if not isinstance(branch, Trajectory) or branch.run_id != run_id:
            raise ValueError("Branch must belong to the selected run")
        self.branch = branch
        self.events = self.ledger.events(run_id)
        self.visible = branch_events(self.events, branch_id)
        self.records = {p.id: p for e in self.visible for p in e.payload}
        self.cursor = next(e for e in reversed(self.events) if e.trajectory_id == branch_id)
        self.store = ArtifactStore(controller.settings.data_dir / "artifacts")
        self.namespace = branch_id
        self.key = ""
        self.digest = ""

    def workspace(self) -> ReviewWorkspace:
        responded = {p.responds_to_id for p in self.records.values() if isinstance(p, Challenge)}
        return ReviewWorkspace(
            branch=self.branch,
            events=tuple(self.visible),
            current_claims=commitments(self.events, self.branch.id),
            unresolved_challenges=tuple(
                p
                for p in self.records.values()
                if isinstance(p, Challenge) and p.responds_to_id is None and p.id not in responded
            ),
            checkpoints=tuple(p for p in self.records.values() if isinstance(p, Checkpoint)),
            annotations=tuple(p for p in self.records.values() if isinstance(p, Annotation)),
        )

    def scope(self, provenance: Provenance = Provenance.HUMAN_ANNOTATION) -> dict[str, Any]:
        return dict(
            experiment_id=self.experiment.id,
            run_id=self.run.id,
            trajectory_id=self.branch.id,
            provenance=provenance,
        )

    def identity(self, suffix: str) -> UUID:
        return uuid5(self.namespace, suffix)

    def get[T: ScopedRecord](self, identity: UUID, kind: type[T]) -> T:
        record = self.records.get(identity)
        if not isinstance(record, kind):
            raise ValueError("Reference is not visible on this branch")
        return record

    def participant(self, identity: UUID) -> Agent:
        agent = next((a for a in self.experiment.agents if a.id == identity and a.enabled), None)
        if agent is None:
            raise ValueError("Unknown or disabled participant")
        return agent

    def event(
        self, event_type: EventType, records: tuple[Record, ...], actor: Agent | None = None
    ) -> Event:
        return Event(
            **self.scope(),
            id=self.identity("event"),
            sequence=1,
            type=event_type,
            payload=records,
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else Role.ORCHESTRATOR,
            # A human-attributed action is not a new inference from the agent's model.
            parent_event_ids=(self.cursor.id,),
            expected_cursor=self.cursor.id,
            expected_trajectory_id=self.branch.id,
            idempotency_key=self.key,
            command_digest=self.digest,
        )

    def source_evidence(
        self,
        ids: tuple[UUID, ...],
        agent: Agent,
        spans: dict[UUID, tuple[int, int]] | None = None,
    ) -> tuple[Evidence, ...]:
        spans = spans or {}
        if not set(spans).issubset(ids):
            raise ValueError("Citation locations must refer to cited sources")
        result = []
        superseded = {p.revises_id for p in self.records.values() if isinstance(p, SourceDocument)}
        for identity in dict.fromkeys(ids):
            source = self.get(identity, SourceDocument)
            if identity in superseded or (
                source.visibility == "private" and source.owner_agent_id != agent.id
            ):
                raise PermissionError("Source is superseded or not available to this participant")
            content = self.store.get(source.content).decode("utf-8")
            location = None
            if identity in spans:
                start, end = spans[identity]
                if not 0 <= start < end <= len(content):
                    raise ValueError("Citation character span is outside source text")
                location = f"unicode_characters:{start}:{end}"
            result.append(
                Evidence(
                    **self.scope(source.provenance),
                    id=self.identity("evidence:" + str(identity)),
                    description=source.title,
                    source="source-document:" + str(source.id),
                    artifacts=(source.content,),
                    source_location=location,
                )
            )
        return tuple(result)

    def apply(self, command: ReviewCommand) -> Event:
        reject_secrets(command.model_dump_json(), directory=self.ledger.path.parent)
        self.namespace = uuid5(self.branch.id, "review:" + command.idempotency_key)
        self.key = f"review:{self.run.id}:{self.branch.id}:{command.idempotency_key}"
        self.digest = hashlib.sha256(command.model_dump_json().encode()).hexdigest()
        existing = next((e for e in self.events if e.idempotency_key == self.key), None)
        if existing:
            if existing.command_digest != self.digest:
                raise LedgerConflict("Review command idempotency conflict")
            return existing
        if isinstance(command, ReviewFork):
            return self.fork(command)
        event = self.propose(command)
        # Reviewer identity and original submitted command are durable provenance.
        audit = Annotation(
            **self.scope(),
            id=self.identity("operator-audit"),
            reviewer_id=command.reviewer_id,
            rubric_version="operator-command-v1",
            subject_id=self.branch.id,
            labels=(command.operation,),
            notes=command.model_dump_json(),
        )
        return self.ledger.append(event.model_copy(update={"payload": event.payload + (audit,)}))

    def apply_generated(
        self,
        body: dict[str, object],
        actor: Agent,
        phase: str,
        visible_source_ids: tuple[UUID, ...],
        synthetic: bool = False,
    ) -> Event:
        """Runtime-only structured proposals; model judgments are never verifier evidence."""
        operation = body.get("operation")
        if operation not in {"claim", "challenge", "respond", "adjudicate", "assess"}:
            raise ValueError("Unsupported generated research operation")
        if operation == "claim" and body.get("revises_id"):
            previous_claim = self.get(UUID(str(body["revises_id"])), Claim)
            if previous_claim.author_id != actor.id:
                raise PermissionError("A model may revise only its own attributed claim")
        controlled = {**body, "idempotency_key": phase, "reviewer_id": "model:" + str(actor.id)}
        if operation in {"claim", "respond", "assess"}:
            controlled["author_id"] = str(actor.id)
        elif operation == "challenge":
            controlled["critic_id"] = str(actor.id)
        elif actor.role != Role.ARCHIVIST:
            raise PermissionError("Only an assigned Archivist may propose model adjudication")
        else:
            controlled["reviewer_agent_id"] = str(actor.id)
        command = review_adapter.validate_python(controlled)
        supplied = getattr(command, "source_ids", ())
        if not set(supplied).issubset(visible_source_ids):
            raise PermissionError("Generated citations must refer to sources actually supplied")
        reject_secrets(command.model_dump_json(), directory=self.ledger.path.parent)
        self.namespace = uuid5(self.branch.id, "generated:" + phase)
        self.key = f"generated:{self.run.id}:{self.branch.id}:{phase}"
        self.digest = hashlib.sha256(command.model_dump_json().encode()).hexdigest()
        previous = next((e for e in self.events if e.idempotency_key == self.key), None)
        if previous:
            if previous.command_digest != self.digest:
                raise LedgerConflict("Generated operation idempotency conflict")
            return previous
        event = self.propose(command)
        provenance = (
            Provenance.IMPORTED_SOURCE
            if synthetic
            else Provenance.LLM_EVALUATOR
            if operation == "adjudicate"
            else Provenance.MODEL_OUTPUT
        )
        payload = tuple(
            p.model_copy(
                update={
                    "provenance": provenance,
                    **(
                        {"policy_version": "model-argument-review-v1"}
                        if isinstance(p, Decision)
                        else {}
                    ),
                }
            )
            if getattr(p, "provenance", None) == Provenance.HUMAN_ANNOTATION
            else p
            for p in event.payload
        )
        return self.ledger.append(
            event.model_copy(
                update={
                    "payload": payload,
                    "provenance": provenance,
                    "actor_id": actor.id,
                    "actor_role": actor.role,
                    "model": actor.model,
                }
            )
        )

    def related_claims(self, current_id: UUID, ancestor_id: UUID) -> bool:
        seen: set[UUID] = set()
        while current_id not in seen:
            if current_id == ancestor_id:
                return True
            seen.add(current_id)
            claim = self.get(current_id, Claim)
            if claim.revises_id is None:
                return False
            current_id = claim.revises_id
        return False

    def propose(self, command: ReviewCommand) -> Event:
        if isinstance(command, ReviewClaim):
            actor = self.participant(command.author_id)
            previous = self.get(command.revises_id, Claim) if command.revises_id else None
            if previous and previous.id not in {
                c.id for c in commitments(self.events, self.branch.id)
            }:
                raise ValueError("Revise the current claim version")
            for identity in command.dependency_ids:
                self.get(identity, Claim)
            evidence = self.source_evidence(command.source_ids, actor, command.citation_spans)
            claim = Claim(
                **self.scope(),
                id=self.identity("claim"),
                author_id=actor.id,
                proposition=command.proposition,
                revises_id=command.revises_id,
                commitment_id=(previous.commitment_id or previous.id)
                if previous
                else self.identity("claim"),
                evidence_ids=tuple(e.id for e in evidence),
                dependency_ids=command.dependency_ids,
                reconsider_ids=impact(self.events, self.branch.id, previous.id) if previous else (),
            )
            return self.event(
                EventType.CLAIM_REVISED if previous else EventType.CLAIM_PROPOSED,
                (*evidence, claim),
                actor,
            )
        if isinstance(command, ReviewChallenge):
            self.get(command.claim_id, Claim)
            actor = self.participant(command.critic_id)
            evidence = self.source_evidence(command.source_ids, actor)
            challenge = Challenge(
                **self.scope(),
                id=self.identity("challenge"),
                claim_id=command.claim_id,
                critic_id=actor.id,
                objection=command.objection,
                evidence_ids=tuple(e.id for e in evidence),
                objection_type=command.objection_type,
                requested_correction=command.requested_correction,
            )
            return self.event(EventType.CHALLENGE_SUBMITTED, (*evidence, challenge), actor)
        if isinstance(command, ReviewResponse):
            challenge = self.get(command.challenge_id, Challenge)
            if challenge.responds_to_id or any(
                isinstance(p, Challenge) and p.responds_to_id == challenge.id
                for p in self.records.values()
            ):
                raise ValueError("Challenge already has a response on this branch")
            original_target = self.get(challenge.claim_id, Claim)
            target = (
                self.get(command.revision_of, Claim) if command.revision_of else original_target
            )
            if not self.related_claims(target.id, original_target.id):
                raise ValueError("Revision target must descend from the challenged claim")
            actor = self.participant(command.author_id)
            if target.author_id != actor.id:
                raise PermissionError("Only the attributed claim author can respond")
            if command.revised_proposition and command.response not in {"accept", "qualify"}:
                raise ValueError("Only acceptance/qualification can include a proposed revision")
            added_evidence = self.source_evidence(command.source_ids, actor)
            response = Challenge(
                **self.scope(),
                id=self.identity("response"),
                claim_id=original_target.id,
                objection=command.reason,
                critic_id=challenge.critic_id,
                responds_to_id=challenge.id,
                response=command.response,
                evidence_ids=tuple(
                    dict.fromkeys((*challenge.evidence_ids, *(e.id for e in added_evidence)))
                ),
            )
            records: tuple[Record, ...] = (
                *added_evidence,
                response,
            )
            if command.revised_proposition:
                if target.id not in {c.id for c in commitments(self.events, self.branch.id)}:
                    raise ValueError("Cannot revise an outdated claim through a challenge response")
                revision = Claim(
                    **self.scope(),
                    id=self.identity("revision"),
                    author_id=actor.id,
                    proposition=command.revised_proposition,
                    revises_id=target.id,
                    commitment_id=target.commitment_id or target.id,
                    status="proposed",
                    evidence_ids=tuple(
                        dict.fromkeys((*target.evidence_ids, *(e.id for e in added_evidence)))
                    ),
                    reconsider_ids=impact(self.events, self.branch.id, target.id),
                )
                records += (revision,)
            return self.event(EventType.CHALLENGE_RESPONDED, records, actor)
        if isinstance(command, ReviewAssessment):
            self.get(command.claim_id, Claim)
            actor = self.participant(command.author_id)
            if command.challenge_id:
                challenge = self.get(command.challenge_id, Challenge)
                if not self.related_claims(command.claim_id, challenge.claim_id):
                    raise ValueError("Assessment challenge must target this claim or an ancestor")
            evidence = self.source_evidence(command.source_ids, actor)
            assessment = ClaimAssessment(
                **self.scope(),
                id=self.identity("assessment"),
                claim_id=command.claim_id,
                agent_id=actor.id,
                challenge_id=command.challenge_id,
                stance=command.stance,
                reason=command.reason,
                evidence_ids=tuple(e.id for e in evidence),
            )
            return self.event(EventType.OBSERVATION_RECEIVED, (*evidence, assessment), actor)
        if isinstance(command, ReviewDecision):
            decision_challenge = (
                self.get(command.challenge_id, Challenge) if command.challenge_id else None
            )
            claim_id = command.claim_id or (
                decision_challenge.claim_id if decision_challenge else None
            )
            if claim_id is None:
                raise ValueError("Judgment requires a visible claim or challenge")
            self.get(claim_id, Claim)
            if decision_challenge and not self.related_claims(
                claim_id, decision_challenge.claim_id
            ):
                raise ValueError("Judgment claim and challenge refer to unrelated propositions")
            if command.source_ids and command.reviewer_agent_id is None:
                raise ValueError("Evidence-linked judgment requires its participant identity")
            evidence = (
                self.source_evidence(
                    command.source_ids, self.participant(command.reviewer_agent_id)
                )
                if command.reviewer_agent_id
                else ()
            )
            decision = Decision(
                **self.scope(),
                challenge_id=decision_challenge.id if decision_challenge else None,
                adjudicator_id=command.reviewer_agent_id,
                evidence_ids=tuple(e.id for e in evidence),
                id=self.identity("decision"),
                claim_id=claim_id,
                outcome=command.outcome,
                reason=command.reason,
                policy_version="human-review-v1",
            )
            return self.event(EventType.ADJUDICATION_RECORDED, (*evidence, decision))
        if isinstance(command, ReviewAnnotation):
            subject = self.ledger.get(command.subject_id)
            if subject.id != self.branch.id and subject.id not in self.records:
                raise ValueError("Annotation subject is not visible")
            if not set(command.dimensions).issubset(RUBRIC) or any(
                type(v) is not int or not 1 <= v <= 5 for v in command.dimensions.values()
            ):
                raise ValueError("Research rubric uses named ratings from 1 through 5")
            if bool(command.preference) != bool(command.other_trajectory_id):
                raise ValueError("Pairwise preference requires another trajectory")
            if command.other_trajectory_id:
                other = self.ledger.get(command.other_trajectory_id)
                if (
                    not isinstance(other, Trajectory)
                    or other.run_id != self.run.id
                    or other.id == self.branch.id
                ):
                    raise ValueError("Preference target must be another branch in this run")
            annotation = Annotation(
                **self.scope(),
                id=self.identity("annotation"),
                reviewer_id=command.reviewer_id,
                rubric_version="research-review-v1",
                subject_id=subject.id,
                notes=command.notes,
                dimensions=command.dimensions,
                preferred_over_id=command.other_trajectory_id,
                preference=command.preference,
            )
            return self.event(EventType.HUMAN_ANNOTATION_ADDED, (annotation,))
        if isinstance(command, ReviewCheckpoint):
            snapshot = self.snapshot()
            checkpoint = Checkpoint(
                **self.scope(Provenance.SYSTEM_INFERENCE),
                id=self.identity("checkpoint"),
                task_version=self.experiment.task_version,
                fixture_hash=snapshot.task.sha256,
                workspace=snapshot.history,
                environment_config=snapshot.task,
                event_cursor=self.cursor.id,
                model_configs=tuple(a.model for a in self.experiment.agents if a.model),
                manifest=self.store.put(snapshot.model_dump_json().encode(), "application/json"),
            )
            return self.event(EventType.CHECKPOINT_CREATED, (checkpoint,))
        if isinstance(command, ReviewEvaluate):
            claims = commitments(self.events, self.branch.id)
            sources = {p.id for p in self.records.values() if isinstance(p, SourceDocument)}
            references = [
                UUID(v)
                for c in claims
                for v in re.findall(
                    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
                    c.proposition,
                )
            ]
            known = sum(i in sources for i in references)
            linked = sum(bool(claim.evidence_ids) for claim in claims)
            criticisms = [
                p
                for p in self.records.values()
                if isinstance(p, Challenge) and not p.responds_to_id
            ]
            responses = {
                p.responds_to_id
                for p in self.records.values()
                if isinstance(p, Challenge) and p.responds_to_id
            }
            versions = [p for p in self.records.values() if isinstance(p, Claim)]
            calls = {p.call_id: p for p in self.records.values() if isinstance(p, ModelCall)}
            # Preserve terminal version per call; starts do not double-count requests.
            for event in self.visible:
                for p in event.payload:
                    if isinstance(p, ModelCall):
                        calls[p.call_id] = p
            measured = list(calls.values())
            addressed = sum(c.id in responses for c in criticisms)
            from doxa.core.quality_labels import correction_metrics

            quality = correction_metrics(list(self.records.values()))
            from doxa.core.citation_audit import citation_counts

            citation_audit = citation_counts(self.controller, claims, self.records)
            evaluation = Evaluation(
                **self.scope(Provenance.SYSTEM_INFERENCE),
                id=self.identity("evaluation"),
                evaluator_version="text-descriptive-v3",
                parameters={
                    "criteria": list(self.experiment.task.evaluation_criteria)
                    if self.experiment.task
                    else [],
                    "citation_measure": "source/artifact linkage and exact character bounds only; "
                    "entailment and correctness unverified",
                    "disagreement_measure": "explicit criticism records, not semantic inference",
                    "quality_score": None,
                    "human_correction_labels": quality,
                },
                metrics={
                    **{f"citation_{key}": float(value) for key, value in citation_audit.items()},
                    "citation_located_span_rate": citation_audit["located_spans"]
                    / citation_audit["document_links"]
                    if citation_audit["document_links"]
                    else None,
                    "current_claims": float(len(claims)),
                    "known_source_reference_rate": known / len(references) if references else None,
                    "objective_correctness": None,
                    "initial_claim_accuracy": None,
                    "final_claim_accuracy": None,
                    "net_justified_correction": quality["net_justified_correction"],
                    "evidence_linked_claim_rate": linked / len(claims) if claims else None,
                    "challenge_response_rate": sum(c.id in responses for c in criticisms)
                    / len(criticisms)
                    if criticisms
                    else None,
                    "citation_entailment": None,
                    "claims_produced": float(len(versions)),
                    "evidence_linked_claims": float(sum(bool(c.evidence_ids) for c in claims)),
                    "claims_without_evidence": float(sum(not c.evidence_ids for c in claims)),
                    "criticisms": float(len(criticisms)),
                    "criticisms_addressed": float(addressed),
                    "criticisms_unresolved": float(len(criticisms) - addressed),
                    "revisions": float(sum(c.revises_id is not None for c in versions)),
                    "reported_contradictions": float(
                        sum(c.objection_type == "contradiction" for c in criticisms)
                    ),
                    "evidential_objections": float(sum(bool(c.evidence_ids) for c in criticisms)),
                    "requests": float(len(calls)),
                    "failed_requests": float(sum(c.status == "failed" for c in measured)),
                    "uncertain_requests": float(
                        sum(c.status in {"started", "uncertain"} for c in measured)
                    ),
                },
                denominators={
                    "document_citation_links": citation_audit["document_links"],
                    "current_claims": len(claims),
                    "source_references": len(references),
                    "challenges": len(criticisms),
                    "claim_versions": len(versions),
                    "requests": len(calls),
                    "requests_with_input_usage": sum(
                        c.usage.input_tokens is not None for c in measured
                    ),
                    "requests_with_output_usage": sum(
                        c.usage.output_tokens is not None for c in measured
                    ),
                },
                usage=Usage(
                    input_tokens=sum(c.usage.input_tokens or 0 for c in measured)
                    if measured and all(c.usage.input_tokens is not None for c in measured)
                    else None,
                    output_tokens=sum(c.usage.output_tokens or 0 for c in measured)
                    if measured and all(c.usage.output_tokens is not None for c in measured)
                    else None,
                    latency_seconds=sum(c.usage.latency_seconds or 0 for c in measured)
                    if measured and all(c.usage.latency_seconds is not None for c in measured)
                    else None,
                    billed_usd=sum(
                        (c.usage.billed_usd for c in measured if c.usage.billed_usd is not None),
                        Decimal("0"),
                    )
                    if measured and all(c.usage.billed_usd is not None for c in measured)
                    else None,
                ),
            )
            return self.event(EventType.EVALUATION_RECORDED, (evaluation,))
        raise ValueError("Unsupported text review operation")

    def snapshot(self) -> TextSnapshot:
        history = self.store.put(
            json.dumps([e.model_dump(mode="json") for e in self.visible], sort_keys=True).encode(),
            "application/json",
        )
        assert self.experiment.task is not None
        return TextSnapshot(
            event_cursor=self.cursor.id,
            history=history,
            configuration=self.store.put(
                self.experiment.model_dump_json().encode(), "application/json"
            ),
            task=self.store.put(
                self.experiment.task.model_dump_json().encode(), "application/json"
            ),
        )

    def fork(self, command: ReviewFork) -> Event:
        checkpoint = self.get(command.checkpoint_id, Checkpoint)
        if checkpoint.trajectory_id != self.branch.id or checkpoint.manifest is None:
            raise ValueError("Checkpoint must be owned by the selected parent branch")
        manifest = TextSnapshot.model_validate_json(self.store.get(checkpoint.manifest))
        assert self.experiment.task is not None
        expected = json.dumps(
            [
                e.model_dump(mode="json")
                for e in branch_events(self.events, self.branch.id, checkpoint.event_cursor)
            ],
            sort_keys=True,
        ).encode()
        if (
            manifest.event_cursor != checkpoint.event_cursor
            or manifest.history != checkpoint.workspace
            or manifest.task != checkpoint.environment_config
            or checkpoint.fixture_hash != manifest.task.sha256
            or [Event.model_validate(e) for e in json.loads(self.store.get(manifest.history))]
            != [Event.model_validate(e) for e in json.loads(expected)]
            or Experiment.model_validate_json(self.store.get(manifest.configuration))
            != self.experiment
            or type(self.experiment.task).model_validate_json(self.store.get(manifest.task))
            != self.experiment.task
        ):
            raise ValueError("Text checkpoint integrity mismatch")
        child = Trajectory(
            id=self.identity("branch"),
            run_id=self.run.id,
            parent_id=self.branch.id,
            checkpoint_id=checkpoint.id,
            intervention=command.intervention,
        )
        proof = Evidence(
            **self.scope(Provenance.DETERMINISTIC_VERIFIER),
            id=self.identity("restore-proof"),
            source="text-snapshot-integrity-v1",
            description="Canonical serialized history hashes match. "
            "Human analysis fork only; no argument truth, model replay "
            "or external effect restoration.",
            artifacts=(manifest.history, manifest.task, manifest.configuration),
        )
        child_scope = dict(trajectory_id=child.id)
        proof = proof.model_copy(update=child_scope)
        created = self.event(EventType.BRANCH_CREATED, (child, proof)).model_copy(
            update={
                "trajectory_id": child.id,
                "expected_cursor": self.cursor.id,
                "expected_trajectory_id": self.branch.id,
            }
        )
        restored = Event(
            **self.scope(Provenance.DETERMINISTIC_VERIFIER),
            id=self.identity("restored"),
            sequence=1,
            type=EventType.CHECKPOINT_RESTORED,
            idempotency_key=self.key + ":restore",
            parent_event_ids=(created.id,),
            payload=(),
        )
        restored = restored.model_copy(update=child_scope)
        return self.ledger.append_batch((created, restored))[0]
