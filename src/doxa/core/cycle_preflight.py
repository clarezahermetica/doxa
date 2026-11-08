"""Explicit offline stress rehearsal in a disposable synthetic workspace only."""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from doxa.core.config import Settings
from doxa.core.models import (
    ContextManifest,
    Experiment,
    ModelAssignment,
    ResearchOutcome,
    SourceDocument,
)
from doxa.core.profiles import CouncilConfig, ModelProfile
from doxa.core.workbench import (
    DebateExecution,
    DebateRuntime,
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)
from doxa.providers.contracts import ModelMessage, ModelRequest
from doxa.storage.configurations import ConfigurationStore

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def cycle_preflight(
    controller: "Controller", run_id: UUID, stress_bytes: int = 1400
) -> dict[str, Any]:
    from doxa.core.controller import Controller

    original = controller.inspect(run_id)
    experiment = controller.ledger.get(original.run.experiment_id)
    if not isinstance(experiment, Experiment) or experiment.task is None:
        raise ValueError("A configured research task is required")
    observed: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="doxa-offline-cycle-") as directory:
        clone = Controller(Settings(data_dir=Path(directory)))
        clone.initialize()
        artifacts = controller.settings.data_dir / "artifacts"
        if artifacts.exists():
            shutil.copytree(artifacts, Path(directory) / "artifacts", dirs_exist_ok=True)
        groups = []
        profiles: dict[UUID, ModelProfile] = {}
        for actor in experiment.agents:
            profile = None
            if actor.model_profile_id:
                value = ConfigurationStore(controller.settings.database_path).get(
                    "profile", actor.model_profile_id, actor.model_profile_version
                )
                assert isinstance(value, ModelProfile)
                profile = value
                clone.save_configuration(CouncilConfig(profiles=(value,)))
            template = add_agent(
                clone,
                NewAgent(
                    display_name=actor.display_name,
                    role=cast(Any, actor.role),
                    instructions=actor.instructions,
                    profile_id=profile.id if profile else None,
                    profile_version=profile.version if profile else None,
                    remote_inference=False,
                    allowed_tools=(),
                    memory_scope=actor.memory_scope,
                ),
            )
            groups.append(ParticipantGroup(agent_id=template.id))
        # Tools are not simulated as research observations; their extra calls remain
        # part of the ordinary static admission upper bound.
        task = experiment.task.model_copy(update={"max_tool_rounds": 0, "evidence_ids": ()})
        run = create_experiment(
            clone,
            NewExperiment(
                name="OFFLINE context stress rehearsal",
                task=task,
                mode=original.run.mode,
                participants=tuple(groups),
                budget=experiment.budget,
                execution_kind="synthetic",
                idempotency_key=str(uuid4()),
            ),
        )
        runtime = DebateRuntime(clone, run.id)
        for actor in runtime.experiment.agents:
            if actor.model_profile_id:
                pinned = ConfigurationStore(clone.settings.database_path).get(
                    "profile", actor.model_profile_id, actor.model_profile_version
                )
                assert isinstance(pinned, ModelProfile)
                profiles[actor.id] = pinned
        from doxa.systems.research import branch_events

        source_documents = [
            p
            for e in branch_events(list(original.events), original.events[0].trajectory_id)
            for p in e.payload
            if isinstance(p, SourceDocument)
        ]
        superseded = {p.revises_id for p in source_documents}
        source_documents = [
            p
            for p in source_documents
            if p.id not in superseded
            and (not experiment.task.evidence_ids or p.id in experiment.task.evidence_ids)
        ]
        owner_map = {
            old.id: new.id
            for old, new in zip(experiment.agents, runtime.experiment.agents, strict=True)
        }
        for source in source_documents:
            if source.visibility == "private" and source.owner_agent_id not in owner_map:
                continue
            import_source(
                clone,
                run.id,
                ImportSource(
                    title=source.title,
                    text=runtime.store.get(source.content).decode(),
                    source="offline rehearsal copy",
                    idempotency_key=str(source.id),
                    visibility=source.visibility,
                    owner_agent_id=owner_map.get(source.owner_agent_id)
                    if source.owner_agent_id
                    else None,
                ),
            )
        default = runtime.synthetic_answer

        def stress(actor: Any, phase: str, manifest: ContextManifest) -> str:
            messages = tuple(
                ModelMessage.model_validate(m)
                for m in json.loads(runtime.store.get(manifest.messages))
            )
            profile = profiles.get(actor.id)
            request = ModelRequest(
                call_id=uuid4(),
                run_id=run.id,
                trajectory_id=runtime.branch,
                agent_id=actor.id,
                assignment=actor.model
                or ModelAssignment(
                    provider="fixture", model_id="fixture", instruction_version="fixture"
                ),
                messages=messages,
                max_output_tokens=min(
                    profile.max_output_tokens, experiment.budget.max_output_tokens
                )
                if profile
                else experiment.budget.max_output_tokens,
                timeout_seconds=1,
                response_schema=runtime.cli_response_schema(profile) if profile else None,
            )
            if profile and profile.transport == "cli_session":
                from doxa.providers.cli_session import CodexCliProvider

                CodexCliProvider(profile).validate_request(request)  # Pure; never generate/probe.
            observed.append(
                {
                    "phase": phase,
                    "input_upper_bound": manifest.input_token_upper_bound,
                    "omitted_count": len(manifest.omitted),
                }
            )
            text = default(actor, phase, manifest)
            if task.structured_actions:
                body = json.loads(text)
                action = body["research_action"]
                observed[-1]["operation"] = action["operation"]
                field = next(
                    (k for k in ("proposition", "objection", "reason") if k in action), None
                )
                if field:
                    padding = max(0, min(stress_bytes, request.max_output_tokens - 512))
                    action[field] += ' OFFLINE STRESS punctuation \\" 中文 ' * (padding // 55)
                    action[field] = action[field][:3900]
                text = json.dumps(body)
            return text

        runtime.synthetic_answer = stress  # type: ignore[assignment, method-assign]
        error = None
        try:
            bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
            outcomes = [
                p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome)
            ]
            passed = bundle.run.status == "completed" and all(
                o.execution_status == "concluded" for o in outcomes
            )
            if outcomes and not passed:
                error = outcomes[-1].reason
        except (ValueError, PermissionError, KeyError) as exc:
            error = str(exc)
            passed = False
        return {
            "kind": "offline_synthetic_stress_rehearsal",
            "passed": passed,
            "turns_exercised": len(observed),
            "turns": observed,
            "error": error,
            "model_calls": 0,
            "workspace_history_modified": False,
            "limits": "Bounded adversarial growth, not a guarantee for arbitrary model output",
            "tool_followups_exercised": False,
        }
