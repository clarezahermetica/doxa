"""Ports consume persisted identifiers and return proposals for controller validation.

No system owns a second ledger or receives write access to another system's state.
Implementation must commit consequential proposals atomically through the controller.
"""

from typing import Protocol
from uuid import UUID

from doxa.core.models import (
    Challenge,
    Checkpoint,
    Claim,
    Contract,
    Evaluation,
    Event,
    Memory,
    ReflectionDecision,
    Trajectory,
    Verification,
)


class SystemContext(Contract):
    experiment_id: UUID
    run_id: UUID
    trajectory_id: UUID
    event_cursor: UUID


class ClaimDiff(Contract):
    added: tuple[UUID, ...]
    revised: tuple[UUID, ...]
    unchanged: tuple[UUID, ...]


class EpistemicGit(Protocol):
    def propose(self, context: SystemContext, claim: Claim) -> Claim: ...
    def compare(self, before: Checkpoint, after: Checkpoint) -> ClaimDiff: ...


class CounterfactualEngine(Protocol):
    async def fork(
        self,
        context: SystemContext,
        checkpoint: Checkpoint,
        intervention: str,
    ) -> Trajectory: ...


class FalseCritic(Protocol):
    async def adjudicate(self, context: SystemContext, challenge: Challenge) -> Verification: ...


class MemoryTribunal(Protocol):
    def propose(self, context: SystemContext, memory: Memory) -> Memory: ...
    def transition(
        self,
        context: SystemContext,
        memory_id: UUID,
        trust: str,
        validation_ids: tuple[UUID, ...],
    ) -> Memory: ...
    def retrieve(
        self,
        context: SystemContext,
        agent_id: UUID,
        eligibility: tuple[str, ...],
    ) -> tuple[Memory, ...]: ...


class SelfCorrectionGym(Protocol):
    async def evaluate(self, context: SystemContext, baseline_run_id: UUID) -> Evaluation: ...


class AdaptiveReflection(Protocol):
    def decide(self, context: SystemContext, trigger: Event) -> ReflectionDecision: ...
