from typing import Protocol
from uuid import UUID

from doxa.core.models import ArtifactRef, Checkpoint, Contract, Evidence, Verification


class TaskSpec(Contract):
    id: str
    version: str
    environment: str
    fixture: ArtifactRef


class Action(Contract):
    id: UUID
    tool: str
    arguments_artifact: ArtifactRef


class Observation(Contract):
    evidence: tuple[Evidence, ...]


class TaskEnvironment(Protocol):
    async def initialize(self, task: TaskSpec, trajectory_id: UUID) -> Observation: ...
    async def observe(self) -> Observation: ...
    async def act(self, action: Action) -> Observation: ...
    async def snapshot(self) -> Checkpoint: ...
    async def restore(self, checkpoint: Checkpoint, new_trajectory_id: UUID) -> Observation: ...
    async def terminate(self) -> None: ...


class IndependentVerifier(Protocol):
    async def verify(self, task: TaskSpec, artifact: ArtifactRef) -> Verification: ...
