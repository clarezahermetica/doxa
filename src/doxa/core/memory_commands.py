"""Memory Tribunal commands: bounded validation, immutable promotion and revocation."""

from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid5

from pydantic import Field

from doxa.core.models import (
    Contract,
    Event,
    EventType,
    Evidence,
    Experiment,
    Memory,
    Provenance,
    Verification,
)
from doxa.environments.cache_policy import CacheFixture, Candidate, verify
from doxa.storage.artifacts import ArtifactStore
from doxa.systems.memory import latest_memories

if TYPE_CHECKING:
    from doxa.core.controller import Controller


class ProposeMemory(Contract):
    text: str = Field(min_length=1, max_length=4000)
    scope: Literal["private", "shared"] = "private"
    owner_agent_id: UUID | None = None
    eligibility: tuple[str, ...] = ()
    revises_id: UUID | None = None
    category: Literal["episodic", "semantic", "procedural", "reflective"] = "semantic"
    trajectory_id: UUID | None = None
    source_event_id: UUID | None = None
    branch_ids: tuple[UUID, ...] = ()
    idempotency_key: str = Field(min_length=1, max_length=200)


class TransitionMemory(Contract):
    trust: Literal["approved", "rejected", "revoked"]
    validation_ids: tuple[UUID, ...] = ()
    idempotency_key: str = Field(min_length=1, max_length=200)


def emit(
    controller: "Controller", run_id: UUID, key: str, event_type: EventType, memory: Memory
) -> Memory:
    previous = controller.ledger.events(run_id)[-1]
    saved = controller.ledger.append(
        Event(
            experiment_id=previous.experiment_id,
            run_id=run_id,
            trajectory_id=memory.trajectory_id,
            sequence=1,
            type=event_type,
            parent_event_ids=(previous.id,),
            idempotency_key=f"{run_id}:memory:{key}",
            payload=(memory,),
        )
    )
    result = saved.payload[0]
    assert isinstance(result, Memory)
    return result


def propose(controller: "Controller", run_id: UUID, command: ProposeMemory) -> Memory:
    bundle = controller.inspect(run_id)
    if command.scope == "private":
        if command.owner_agent_id is None:
            raise ValueError("Private memory requires an owner")
        controller.participant_records(run_id, command.owner_agent_id)
    previous = bundle.events[-1]
    branch = command.trajectory_id or previous.trajectory_id
    from doxa.systems.research import branch_events

    visible = branch_events(list(bundle.events), branch)
    source_id = command.source_event_id or visible[-1].id
    if source_id not in {e.id for e in visible}:
        raise ValueError("Memory source must be visible on its originating branch")
    for identity in command.branch_ids:
        target = controller.ledger.get(identity)
        if target.kind != "trajectory" or target.run_id != run_id:
            raise ValueError("Memory branch validity must reference this run")
    memory = Memory(
        id=uuid5(run_id, "memory:" + command.idempotency_key),
        experiment_id=previous.experiment_id,
        run_id=run_id,
        trajectory_id=branch,
        provenance=Provenance.IMPORTED_SOURCE,
        text=command.text,
        scope=command.scope,
        owner_agent_id=command.owner_agent_id,
        source_event_id=source_id,
        eligibility=command.eligibility,
        revises_id=command.revises_id,
        memory_id=uuid5(run_id, "memory:" + command.idempotency_key),
        category=command.category,
        branch_ids=command.branch_ids,
    )
    if command.revises_id:
        ancestor = controller.ledger.get(command.revises_id)
        if not isinstance(ancestor, Memory) or ancestor.run_id != run_id:
            raise ValueError("Memory ancestor must be in this run")
        memory = memory.model_copy(update={"memory_id": ancestor.memory_id or ancestor.id})
    # Stable source cursor for retries; reject changed proposals instead of silently overwriting.
    try:
        existing = controller.ledger.get(memory.id)
    except KeyError:
        existing = None
    if existing is not None:
        if not isinstance(existing, Memory) or (
            existing.model_dump(exclude={"source_event_id"})
            != memory.model_dump(exclude={"source_event_id"})
        ):
            raise ValueError("Memory proposal idempotency conflict")
        return existing
    return emit(controller, run_id, command.idempotency_key, EventType.MEMORY_PROPOSED, memory)


def transition(
    controller: "Controller", run_id: UUID, memory_id: UUID, command: TransitionMemory
) -> Memory:
    memory = controller.ledger.get(memory_id)
    if not isinstance(memory, Memory) or memory.run_id != run_id:
        raise ValueError("Memory not in run")
    identity = uuid5(run_id, "memory-transition:" + command.idempotency_key)
    expected = memory.model_copy(
        update={
            "id": identity,
            "trust": command.trust,
            "revises_id": memory.id,
            "validation_ids": command.validation_ids or memory.validation_ids,
        }
    )
    expected = Memory.model_validate(expected.model_dump())
    try:
        existing = controller.ledger.get(identity)
    except KeyError:
        existing = None
    if existing is not None:
        if existing != expected:
            raise ValueError("Memory transition idempotency conflict")
        assert isinstance(existing, Memory)
        return existing
    if memory.id not in {m.id for m in latest_memories(controller.ledger, run_id)}:
        raise ValueError("Memory has already been superseded")
    return emit(
        controller, run_id, command.idempotency_key, EventType.MEMORY_STATUS_CHANGED, expected
    )


LESSONS = {
    "Invalidate cache entries after update and delete.": "invalidate_all",
    "Repeated reads without writes return the same cached value.": "invalidate_all",
    "A cache-policy v1 verifier checks update and delete behavior.": "invalidate_all",
}


def validate(controller: "Controller", run_id: UUID, memory_id: UUID) -> Verification:
    memory = controller.ledger.get(memory_id)
    if not isinstance(memory, Memory) or memory.run_id != run_id:
        raise ValueError("Memory not in run")
    try:
        existing = controller.ledger.get(uuid5(memory.id, "validation"))
    except KeyError:
        existing = None
    if isinstance(existing, Verification):
        return existing
    experiment = controller.ledger.get(memory.experiment_id)
    assert isinstance(experiment, Experiment)
    if experiment.task_id != "cache-policy" or experiment.task_version != "1":
        raise ValueError("Only cache-policy v1 memory predicates are registered")
    if sum(e.type == EventType.VERIFICATION_RECORDED for e in controller.ledger.events(run_id)) >= (
        experiment.budget.max_tool_calls
    ):
        raise ValueError("Verifier tool-call limit reached")
    # Only explicit task-specific predicates are implemented, never generic LLM truth judgments.
    results = verify(CacheFixture(), Candidate(policy="invalidate_all"))
    verdict: Literal["valid", "invalid", "unverified"] = (
        "valid" if memory.text in LESSONS and all(results.values()) else "unverified"
    )
    previous = controller.ledger.events(run_id)[-1]
    evidence = Evidence(
        id=uuid5(memory.id, "validation-evidence"),
        experiment_id=memory.experiment_id,
        run_id=run_id,
        trajectory_id=memory.trajectory_id,
        provenance=Provenance.DETERMINISTIC_VERIFIER,
        description=f"Bounded cache-policy lesson predicate: {verdict}; tests={results}",
        source="cache-policy-lesson-oracle-v1",
        artifacts=(
            ArtifactStore(controller.settings.data_dir / "artifacts").put(str(results).encode()),
        ),
    )
    verification = Verification(
        id=uuid5(memory.id, "validation"),
        experiment_id=memory.experiment_id,
        run_id=run_id,
        trajectory_id=memory.trajectory_id,
        provenance=Provenance.DETERMINISTIC_VERIFIER,
        subject_id=memory.id,
        evaluator_id="cache-policy-lesson-oracle",
        evaluator_version="1",
        verdict=verdict,
        evidence_ids=(evidence.id,),
    )
    try:
        existing = controller.ledger.get(verification.id)
    except KeyError:
        existing = None
    if existing is None:
        controller.ledger.append(
            Event(
                experiment_id=memory.experiment_id,
                run_id=run_id,
                trajectory_id=memory.trajectory_id,
                sequence=1,
                type=EventType.VERIFICATION_RECORDED,
                provenance=verification.provenance,
                parent_event_ids=(previous.id,),
                idempotency_key=f"{memory_id}:lesson-validation",
                payload=(evidence, verification),
            )
        )
    return verification
