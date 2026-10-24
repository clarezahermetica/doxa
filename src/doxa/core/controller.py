from typing import TYPE_CHECKING, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from doxa.core.config import Settings
from doxa.core.models import (
    Agent,
    Contract,
    Event,
    EventType,
    Experiment,
    ModelAssignment,
    ProtocolMode,
    Record,
    Run,
    RunState,
    Trajectory,
)
from doxa.core.profiles import AgentDefinition, CouncilConfig, ModelProfile
from doxa.storage.configurations import ConfigurationStore
from doxa.storage.database import migrate
from doxa.storage.ledger import Ledger

if TYPE_CHECKING:
    from doxa.core.execution import ExecuteTask
    from doxa.core.memory_commands import ProposeMemory, TransitionMemory
    from doxa.core.models import Memory, Verification
    from doxa.core.research_commands import Command
    from doxa.retrieval.backends import RetrievalBackend


class CapabilityUnavailable(RuntimeError):
    pass


class ConfigureRun(Contract):
    experiment: Experiment
    mode: ProtocolMode = ProtocolMode.SOLO_DIRECT
    execution_kind: Literal["live", "synthetic", "replay"] = "live"
    idempotency_key: str = Field(min_length=1, max_length=200)
    agent_ids: tuple[UUID, ...] = ()


class RunBundle(Contract):
    run: Run
    events: tuple[Event, ...]
    accounting: tuple[dict[str, str | int | None], ...] = ()


class Controller:
    """Single application boundary used by both clients. No inference side effects."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.ledger = Ledger(settings.database_path)

    def initialize(self) -> None:
        migrate(self.settings.database_path)

    def research_command(self, run_id: UUID, branch_id: UUID, command: "Command") -> Event:
        from doxa.core.research import ResearchRuntime

        return ResearchRuntime(self, run_id, branch_id).apply(command)

    def save_configuration(self, config: CouncilConfig) -> None:
        ConfigurationStore(self.settings.database_path).save(config)

    def configuration(self) -> CouncilConfig:
        return ConfigurationStore(self.settings.database_path).list()

    def configure_run(self, command: ConfigureRun) -> Run:
        if command.agent_ids:
            store = ConfigurationStore(self.settings.database_path)
            agents: list[Agent] = []
            for identity in command.agent_ids:
                definition = store.get("agent", str(identity))
                assert isinstance(definition, AgentDefinition)
                if not definition.enabled:
                    raise ValueError("Agent is disabled")
                assignment = None
                if definition.model_profile_id:
                    profile = store.get(
                        "profile", definition.model_profile_id, definition.model_profile_version
                    )
                    assert isinstance(profile, ModelProfile)
                    assignment = ModelAssignment(
                        provider=profile.provider,
                        model_id=profile.model_id,
                        settings={"temperature": profile.temperature},
                        instruction_version=definition.instruction_version,
                    )
                agents.append(
                    definition.agent.model_copy(
                        update={
                            "display_name": definition.display_name,
                            "enabled": definition.enabled,
                            "instruction_version": definition.instruction_version,
                            "model": assignment,
                            "model_profile_id": definition.model_profile_id,
                            "model_profile_version": definition.model_profile_version,
                        }
                    )
                )
            command = command.model_copy(
                update={
                    "experiment": command.experiment.model_copy(update={"agents": tuple(agents)})
                }
            )
        namespace = uuid5(NAMESPACE_URL, "doxa:configure:" + command.idempotency_key)
        run = Run(
            id=uuid5(namespace, "run"),
            experiment_id=command.experiment.id,
            mode=command.mode,
            execution_kind=command.execution_kind,
        )
        trajectory = Trajectory(id=uuid5(namespace, "root"), run_id=run.id)
        # Ledger compares/reuses immutable experiment configuration in the same transaction.
        payload = (command.experiment, run, trajectory)
        self.ledger.append(
            Event(
                experiment_id=command.experiment.id,
                run_id=run.id,
                trajectory_id=trajectory.id,
                sequence=1,
                type=EventType.RUN_CREATED,
                idempotency_key="configure:" + command.idempotency_key,
                payload=payload,
            )
        )
        return run

    def list_runs(self) -> list[Run]:
        return [self.inspect(r.id).run for r in self.ledger.records("run") if isinstance(r, Run)]

    def inspect(self, run_id: UUID) -> RunBundle:
        run = self.ledger.get(run_id)
        if not isinstance(run, Run):
            raise KeyError(str(run_id))
        events = tuple(self.ledger.events(run_id))
        states = [r for e in events for r in e.payload if isinstance(r, RunState)]
        if states:
            run = run.model_copy(update={"status": states[-1].status})
        from doxa.storage.budget import BudgetStore

        accounting = tuple(
            op
            for op in BudgetStore(self.settings.database_path).operations()
            if op["run_id"] == str(run_id)
        )
        return RunBundle(run=run, events=events, accounting=accounting)

    def cancel(self, run_id: UUID) -> RunBundle:
        from doxa.core.models import Provenance

        bundle = self.inspect(run_id)
        if bundle.run.status == "cancelled":
            return bundle
        previous = bundle.events[-1]
        state = RunState(
            id=uuid5(run_id, "operator-cancel"),
            experiment_id=previous.experiment_id,
            run_id=run_id,
            trajectory_id=previous.trajectory_id,
            provenance=Provenance.SYSTEM_INFERENCE,
            status="cancelled",
            reason_code="operator_request",
        )
        self.ledger.append(
            Event(
                experiment_id=previous.experiment_id,
                run_id=run_id,
                trajectory_id=previous.trajectory_id,
                sequence=1,
                type=EventType.RUN_CANCELLED,
                payload=(state,),
                parent_event_ids=(previous.id,),
                idempotency_key=f"{run_id}:cancel",
            )
        )
        return self.inspect(run_id)

    async def execute_task(self, run_id: UUID, command: "ExecuteTask") -> RunBundle:
        from doxa.core.execution import Runtime

        return await Runtime(self, run_id).execute(command)

    def propose_memory(self, run_id: UUID, command: "ProposeMemory") -> "Memory":
        from doxa.core.memory_commands import propose

        return propose(self, run_id, command)

    def transition_memory(
        self, run_id: UUID, memory_id: UUID, command: "TransitionMemory"
    ) -> "Memory":
        from doxa.core.memory_commands import transition

        return transition(self, run_id, memory_id, command)

    def validate_memory(self, run_id: UUID, memory_id: UUID) -> "Verification":
        from doxa.core.memory_commands import validate

        return validate(self, run_id, memory_id)

    async def retrieve_memory(
        self,
        run_id: UUID,
        agent_id: UUID,
        query: str,
        backend: "RetrievalBackend | None" = None,
        conditions: tuple[str, ...] = (),
        rebuild: bool = True,
    ) -> tuple["Memory", ...]:
        from doxa.core.models import Provenance
        from doxa.systems.memory import retrieve

        self.participant_records(run_id, agent_id)
        memories, audit = await retrieve(
            self.ledger, run_id, agent_id, query, backend, conditions, rebuild=rebuild
        )
        previous = self.ledger.events(run_id)[-1]
        self.ledger.append(
            Event(
                experiment_id=previous.experiment_id,
                run_id=run_id,
                trajectory_id=audit.trajectory_id,
                sequence=1,
                type=EventType.RETRIEVAL_RECORDED,
                provenance=Provenance.SYSTEM_INFERENCE,
                parent_event_ids=(previous.id,),
                payload=(audit,),
                idempotency_key=f"retrieval:{audit.id}",
            )
        )
        return memories

    def participant_records(self, run_id: UUID, agent_id: UUID) -> tuple[Record, ...]:
        from doxa.core.models import CouncilMessage

        bundle = self.inspect(run_id)
        experiment = self.ledger.get(bundle.run.experiment_id)
        assert isinstance(experiment, Experiment)
        if not any(a.id == agent_id and a.enabled for a in experiment.agents):
            raise PermissionError("Unknown or disabled run participant")
        # Allowlist: never return raw event payloads, configuration or another role's context.
        records: list[Record] = []
        from doxa.systems.memory import eligible

        records.extend(eligible(self.ledger, run_id, agent_id))
        records.extend(
            r
            for e in bundle.events
            for r in e.payload
            if isinstance(r, CouncilMessage)
            and (r.visibility == "shared" or r.sender_id == agent_id or r.target_id == agent_id)
        )
        return tuple(records)

    def execute(self, run_id: UUID) -> None:
        self.inspect(run_id)
        raise CapabilityUnavailable(
            "Protocol execution is not implemented in the foundation. No model or tool was called."
        )
