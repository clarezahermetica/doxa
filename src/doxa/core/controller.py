from decimal import Decimal
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
    from doxa.core.text_research import ReviewCommand, ReviewWorkspace
    from doxa.environments.cache_adapter import CacheTaskAdapter
    from doxa.providers.registry import ConfigurationReport, ProviderDescriptor
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
        from doxa.providers.registry import ProviderRegistry

        self.settings = settings
        self.ledger = Ledger(settings.database_path)
        self.providers = ProviderRegistry()

    def initialize(self, *, allow_create: bool = False) -> None:
        from doxa.core.workspaces import validate_workspace

        if self.settings.database_path.exists():
            validate_workspace(self.settings.data_dir)
        if not allow_create:
            from doxa.core.workspaces import refuse_missing_selection

            refuse_missing_selection(self.settings.data_dir)
        migrate(self.settings.database_path)

    def research_command(self, run_id: UUID, branch_id: UUID, command: "Command") -> Event:
        from doxa.core.research import ResearchRuntime

        return ResearchRuntime(self, run_id, branch_id).apply(command)

    def review_command(self, run_id: UUID, branch_id: UUID, command: "ReviewCommand") -> Event:
        from doxa.core.text_research import TextResearch

        return TextResearch(self, run_id, branch_id).apply(command)

    def review_workspace(self, run_id: UUID, branch_id: UUID) -> "ReviewWorkspace":
        from doxa.core.text_research import TextResearch

        return TextResearch(self, run_id, branch_id).workspace()

    def save_configuration(self, config: CouncilConfig) -> None:
        ConfigurationStore(self.settings.database_path).save(config)

    def configuration(self) -> CouncilConfig:
        return ConfigurationStore(self.settings.database_path).list()

    def provider_catalog(self) -> tuple["ProviderDescriptor", ...]:
        return self.providers.descriptors()

    def environment_session(self, run_id: UUID, branch_id: UUID) -> "CacheTaskAdapter":
        from doxa.environments.cache_adapter import CacheTaskAdapter
        from doxa.environments.cache_policy import Candidate
        from doxa.storage.artifacts import ArtifactStore

        bundle = self.inspect(run_id)
        experiment = self.ledger.get(bundle.run.experiment_id)
        branch = self.ledger.get(branch_id)
        if not isinstance(experiment, Experiment) or (
            experiment.task_id,
            experiment.task_version,
            experiment.environment_version,
        ) != ("cache-policy", "1", "1"):
            raise CapabilityUnavailable("Only the finite cache-policy environment is registered")
        if not isinstance(branch, Trajectory) or branch.run_id != run_id:
            raise ValueError("Environment branch must belong to this run")
        cursor = next(e.id for e in reversed(bundle.events) if e.trajectory_id == branch_id)
        # Finite fixture baseline; subsequent policies must be typed allowed actions.
        return CacheTaskAdapter(
            ArtifactStore(self.settings.data_dir / "artifacts"),
            experiment.id,
            run_id,
            cursor,
            Candidate(policy="stale_on_update"),
        )

    def validate_configuration(self, config: CouncilConfig | None = None) -> "ConfigurationReport":
        from doxa.core.secrets import workspace_env
        from doxa.providers.registry import validate_configuration

        config = config if config is not None else self.configuration()
        profiles = {(p.id, p.version): p for p in config.profiles}
        store = ConfigurationStore(self.settings.database_path)
        for agent in config.agents:
            key = (agent.model_profile_id, agent.model_profile_version)
            if agent.model_profile_id and key not in profiles:
                try:
                    pinned = store.get(
                        "profile", agent.model_profile_id, agent.model_profile_version
                    )
                except KeyError:
                    continue
                assert isinstance(pinned, ModelProfile)
                profiles[(pinned.id, pinned.version)] = pinned
        return validate_configuration(
            config.model_copy(update={"profiles": tuple(profiles.values())}),
            workspace_env(self.settings.data_dir),
        )

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
                        settings={
                            "temperature": None
                            if profile.provider == "openai"
                            else profile.temperature
                        },
                        instruction_version=definition.instruction_version,
                        pricing_version=profile.pricing.version if profile.pricing else None,
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

    def recover_run(self, run_id: UUID) -> RunBundle:
        from doxa.storage.budget import BudgetStore
        from doxa.storage.workers import worker_lease

        self.inspect(run_id)
        with worker_lease(self.settings.data_dir, run_id):
            BudgetStore(self.settings.database_path).recover_interrupted(run_id, self.ledger)
        return self.inspect(run_id)

    def reconcile_charge(self, operation_id: UUID, billed_usd: Decimal) -> None:
        from doxa.storage.budget import BudgetStore
        from doxa.storage.workers import worker_lease

        operation = next(
            (
                o
                for o in BudgetStore(self.settings.database_path).operations()
                if o["id"] == str(operation_id)
            ),
            None,
        )
        if operation is None:
            raise ValueError("Unknown provider operation")
        run_id = UUID(str(operation["run_id"]))
        with worker_lease(self.settings.data_dir, run_id):
            if self.inspect(run_id).run.status not in {"completed", "cancelled", "failed"}:
                raise ValueError("Cancel the interrupted run before billing reconciliation")
            self._reconcile_charge_owned(operation_id, billed_usd)

    def _reconcile_charge_owned(self, operation_id: UUID, billed_usd: Decimal) -> None:
        from doxa.core.models import Evidence, Provenance
        from doxa.storage.budget import BudgetStore

        budgets = BudgetStore(self.settings.database_path)
        operation = next((o for o in budgets.operations() if o["id"] == str(operation_id)), None)
        if operation is None:
            raise ValueError("Unknown provider operation")
        run_id = UUID(str(operation["run_id"]))
        bundle = self.inspect(run_id)
        previous = bundle.events[-1]
        prior = next(
            (e for e in bundle.events if e.idempotency_key == f"billing:{operation_id}"), None
        )
        evidence = Evidence(
            id=uuid5(operation_id, "bill-evidence"),
            experiment_id=previous.experiment_id,
            run_id=run_id,
            trajectory_id=previous.trajectory_id,
            provenance=Provenance.HUMAN_ANNOTATION,
            source="operator-reported-billing",
            description=f"Operation {operation_id}; operator-reported USD "
            f"{billed_usd.quantize(Decimal('0.000001')):f}",
        )
        if prior:
            if not isinstance(prior.payload[0], Evidence) or (
                prior.payload[0].description != evidence.description
            ):
                raise ValueError("Operator billing reconciliation is immutable")
            return
        event = Event(
            id=uuid5(operation_id, "bill-event"),
            experiment_id=previous.experiment_id,
            run_id=run_id,
            trajectory_id=previous.trajectory_id,
            sequence=1,
            provenance=Provenance.HUMAN_ANNOTATION,
            type=EventType.OBSERVATION_RECEIVED,
            parent_event_ids=(previous.id,),
            idempotency_key=f"billing:{operation_id}",
            payload=(evidence,),
        )
        budgets.reconcile(operation_id, billed_usd, ledger=self.ledger, event=event)

    def reconcile_local_call(
        self, call_id: UUID, *, evidence: str, confirmed_stopped: bool
    ) -> None:
        """Explicit operator attestation; never a model result or automatic replay."""
        from doxa.core.models import Evidence, ModelCall, Provenance
        from doxa.core.secrets import reject_secrets
        from doxa.storage.workers import worker_lease

        if not confirmed_stopped or not evidence.strip():
            raise ValueError("Confirm local execution stopped and provide supporting evidence")
        reject_secrets(evidence, directory=self.settings.data_dir)
        calls = [
            c
            for c in self.ledger.records("model_call")
            if isinstance(c, ModelCall) and c.call_id == call_id
        ]
        if not calls or not any(c.request_settings.get("location") == "loopback" for c in calls):
            raise ValueError("Unknown unbilled local call")
        call = calls[-1]
        with worker_lease(self.settings.data_dir, call.run_id):
            bundle = self.inspect(call.run_id)
            if bundle.run.status not in {"cancelled", "failed", "completed"}:
                raise ValueError("Cancel the run before reconciling local execution")
            key = f"local-reconciliation:{call_id}"
            prior = next((e for e in bundle.events if e.idempotency_key == key), None)
            if prior:
                if getattr(prior.payload[0], "description", None) != evidence.strip():
                    raise ValueError("Local reconciliation evidence is immutable")
                return
            if call.status not in {"started", "uncertain"}:
                raise ValueError("Only ambiguous local calls require reconciliation")
            proof = Evidence(
                id=uuid5(call_id, "local-stop-evidence"),
                experiment_id=call.experiment_id,
                run_id=call.run_id,
                trajectory_id=call.trajectory_id,
                provenance=Provenance.HUMAN_ANNOTATION,
                source="operator-confirmed-local-stop",
                description=evidence.strip(),
            )
            closed = call.model_copy(
                update={
                    "id": uuid5(call_id, "local-stop"),
                    "status": "failed",
                    "error_category": "operator_confirmed_stopped",
                    "provenance": Provenance.HUMAN_ANNOTATION,
                }
            )
            self.ledger.append(
                Event(
                    experiment_id=call.experiment_id,
                    run_id=call.run_id,
                    trajectory_id=call.trajectory_id,
                    sequence=1,
                    type=EventType.MODEL_CALL_RECORDED,
                    provenance=Provenance.HUMAN_ANNOTATION,
                    payload=(proof, closed),
                    parent_event_ids=(bundle.events[-1].id,),
                    idempotency_key=key,
                )
            )

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
        if bundle.run.status not in {"configured", "running"}:
            raise ValueError("Only active runs can be cancelled")
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
                expected_cursor=previous.id,
                expected_trajectory_id=previous.trajectory_id,
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
