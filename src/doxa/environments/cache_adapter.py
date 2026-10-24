"""TaskEnvironment implementation for trusted, built-in finite cache actions.

This transient adapter returns typed observations/checkpoints for controller commits.
It owns no history and cannot run Python source, shell commands or generated patches.
"""

from uuid import UUID

from doxa.core.models import Checkpoint, Contract, Evidence, Provenance
from doxa.environments.cache_policy import CacheEnvironment, CacheFixture, Candidate, fixture_hash
from doxa.environments.contracts import Action, Observation, TaskSpec
from doxa.storage.artifacts import ArtifactStore


class CacheActionArguments(Contract):
    key: str = "x"
    value: int | None = None
    candidate: Candidate | None = None


class CacheTaskAdapter:
    tools = frozenset({"read", "update", "delete", "select_policy"})

    def __init__(
        self,
        store: ArtifactStore,
        experiment_id: UUID,
        run_id: UUID,
        event_cursor: UUID,
        candidate: Candidate,
    ):
        self.store = store
        self.experiment_id = experiment_id
        self.run_id = run_id
        self.event_cursor = event_cursor
        self.candidate = candidate
        self.env: CacheEnvironment | None = None
        self.task: TaskSpec | None = None
        self.trajectory_id: UUID | None = None
        self.terminated = False

    def active(self) -> CacheEnvironment:
        if self.terminated or self.env is None:
            raise ValueError("Environment is not initialized or was terminated")
        return self.env

    async def initialize(self, task: TaskSpec, trajectory_id: UUID) -> Observation:
        if self.env is not None or self.terminated:
            raise ValueError("Environment session cannot be initialized twice")
        if (task.id, task.version, task.environment) != ("cache-policy", "1", "1"):
            raise ValueError("Only the versioned cache-policy fixture is supported")
        CacheFixture.model_validate_json(self.store.get(task.fixture))
        self.env = CacheEnvironment(self.candidate)
        self.task, self.trajectory_id = task, trajectory_id
        return await self.observe()

    async def observe(self) -> Observation:
        env = self.active()
        assert self.trajectory_id is not None
        evidence = Evidence(
            experiment_id=self.experiment_id,
            run_id=self.run_id,
            trajectory_id=self.trajectory_id,
            provenance=Provenance.TOOL_OBSERVATION,
            source="cache-environment-v1",
            description="Canonical finite cache state; task/cache-policy/1; environment/1",
            artifacts=(self.store.put(env.snapshot(), "application/json"),),
        )
        return Observation(evidence=(evidence,))

    def validate_action(self, action: Action) -> CacheActionArguments:
        self.active()
        if action.tool not in self.tools:
            raise ValueError("Tool is outside the finite environment allowlist")
        arguments = CacheActionArguments.model_validate_json(
            self.store.get(action.arguments_artifact)
        )
        if action.tool == "update" and arguments.value is None:
            raise ValueError("Update requires an integer value")
        if action.tool == "select_policy" and arguments.candidate is None:
            raise ValueError("Policy selection requires a typed finite candidate")
        return arguments

    async def act(self, action: Action) -> Observation:
        arguments = self.validate_action(action)
        env = self.active()
        if action.tool == "read":
            env.read(arguments.key)
        elif action.tool == "update":
            assert arguments.value is not None
            env.update(arguments.key, arguments.value)
        elif action.tool == "delete":
            env.delete(arguments.key)
        else:
            env.state = env.state.model_copy(update={"policy": arguments.candidate})
        return await self.observe()

    async def snapshot(self) -> Checkpoint:
        env = self.active()
        assert self.task is not None and self.trajectory_id is not None
        return Checkpoint(
            experiment_id=self.experiment_id,
            run_id=self.run_id,
            trajectory_id=self.trajectory_id,
            provenance=Provenance.TOOL_OBSERVATION,
            task_version=self.task.version,
            fixture_hash=fixture_hash(CacheFixture()),
            workspace=self.store.put(env.snapshot()),
            environment_config=self.task.fixture,
            event_cursor=self.event_cursor,
        )

    async def restore(self, checkpoint: Checkpoint, new_trajectory_id: UUID) -> Observation:
        self.active()
        if (checkpoint.experiment_id, checkpoint.run_id, checkpoint.task_version) != (
            self.experiment_id,
            self.run_id,
            "1",
        ):
            raise ValueError("Checkpoint scope or version differs from this environment")
        fixture = CacheFixture.model_validate_json(self.store.get(checkpoint.environment_config))
        if fixture_hash(fixture) != checkpoint.fixture_hash:
            raise ValueError("Checkpoint fixture hash differs")
        raw = self.store.get(checkpoint.workspace)
        restored = CacheEnvironment.restore(raw)
        if restored.snapshot() != raw:
            raise ValueError("Restored state differs from the pinned state")
        # No external effects exist; restore is confined to this finite state object.
        self.env, self.trajectory_id = restored, new_trajectory_id
        return await self.observe()

    async def terminate(self) -> None:
        self.env = None
        self.terminated = True
