"""Create explicitly labeled, unstarted controls with matching source hashes/settings."""

import json
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID, uuid4

from doxa.core.models import Agent, Experiment, ProtocolMode, Role, SourceDocument
from doxa.core.workbench import (
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def requested_model_signature(actor: Agent) -> str | None:
    """Compare declared generation settings, never infer effective provider settings."""
    if actor.model is None:
        return None
    return json.dumps(
        {
            "provider": actor.model.provider,
            "model": actor.model.model_id,
            "settings": {
                k: v
                for k, v in actor.model.settings.items()
                if k not in {"profile_id", "profile_version"}
            },
        },
        sort_keys=True,
    )


def prepare_control(
    controller: "Controller",
    reference_run: UUID,
    condition: Literal["solo", "self_correction", "multi_agent"],
) -> UUID:
    bundle = controller.inspect(reference_run)
    experiment = controller.ledger.get(bundle.run.experiment_id)
    if not isinstance(experiment, Experiment) or experiment.task is None:
        raise ValueError("A research experiment is required")
    # Only shared sources can be a common information condition. Private sources
    # cannot silently be relabeled shared or moved to a new participant identity.
    sources = [p for e in bundle.events for p in e.payload if isinstance(p, SourceDocument)]
    superseded = {s.revises_id for s in sources}
    sources = [
        s
        for s in sources
        if s.id not in superseded
        and (not experiment.task.evidence_ids or s.id in experiment.task.evidence_ids)
    ]
    if any(s.visibility == "private" for s in sources):
        raise ValueError("Private evidence requires an explicit matched visibility design")
    authors = [a for a in experiment.agents if a.role in {Role.RESEARCHER, Role.EXECUTOR}]
    if not authors:
        raise ValueError("Select an experiment with a Researcher or Executor")
    author = authors[0]
    if condition == "multi_agent":
        selected = experiment.agents
        models = {requested_model_signature(a) for a in selected if a.model}
        if len(models) > 1:
            raise ValueError(
                "Matched control requires the same requested model/settings for all participants"
            )
    else:
        selected = (author,)
    groups = []
    for actor in selected:
        note = (
            "Control condition self_correction: round 0 propose a source-linked claim; "
            "round 1 criticize your own claim; round 2 respond, revise only if warranted. "
            if condition == "self_correction"
            else ""
        )
        template = add_agent(
            controller,
            NewAgent(
                display_name=condition + " " + actor.role.value,
                role=cast(
                    Literal[Role.RESEARCHER, Role.EXECUTOR, Role.SKEPTIC, Role.ARCHIVIST],
                    actor.role,
                ),
                instructions=actor.instructions + "\n" + note,
                profile_id=actor.model_profile_id,
                profile_version=actor.model_profile_version,
                remote_inference=actor.permissions.remote_inference,
                allowed_tools=cast(
                    tuple[Literal["web_search", "web_fetch"], ...], actor.permissions.allowed_tools
                ),
                memory_scope=actor.memory_scope,
            ),
        )
        groups.append(ParticipantGroup(agent_id=template.id))
    rounds = (
        1
        if condition == "solo"
        else 3
        if condition == "self_correction"
        else experiment.task.council.rounds
    )
    call_cap = (
        1
        if condition == "solo"
        else 3
        if condition == "self_correction"
        else max(5, experiment.budget.max_model_calls)
    )
    task = experiment.task.model_copy(
        update={
            "control_condition": condition,
            "staged_research": False,
            "research_protocol": "investigation" if condition == "multi_agent" else "fixed_rounds",
            "structured_actions": True,
            "council": experiment.task.council.model_copy(
                update={"rounds": rounds, "scheduling": "sequential", "max_calls": call_cap}
            ),
            "evidence_ids": (),
        }
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name=condition + " control · " + experiment.name[:140],
            task=task,
            mode=ProtocolMode.SOLO_DIRECT
            if condition == "solo"
            else ProtocolMode.SOLO_DELIBERATIVE
            if condition == "self_correction"
            else ProtocolMode.ADVERSARIAL,
            participants=tuple(groups),
            budget=experiment.budget.model_copy(update={"max_model_calls": call_cap}),
            execution_kind=bundle.run.execution_kind
            if bundle.run.execution_kind != "replay"
            else "synthetic",
            idempotency_key=str(uuid4()),
        ),
    )
    from doxa.storage.artifacts import ArtifactStore

    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    for source in sources:
        import_source(
            controller,
            run.id,
            ImportSource(
                title=source.title,
                text=store.get(source.content).decode(),
                original=source.original,
                source="matched control source",
                idempotency_key=str(source.id),
            ),
        )
    return run.id


def compare_controls(
    controller: "Controller", baseline: UUID, treatment: UUID
) -> dict[str, object]:
    from doxa.core.models import ModelCall
    from doxa.core.quality_labels import correction_metrics

    bundles = [controller.inspect(identity) for identity in (baseline, treatment)]
    experiments = [controller.ledger.get(b.run.experiment_id) for b in bundles]
    assert all(isinstance(e, Experiment) for e in experiments)
    configs = [Experiment.model_validate(e.model_dump()) for e in experiments]
    variables = []
    usage = []
    quality = []
    for bundle, experiment in zip(bundles, configs, strict=True):
        records = [p for e in bundle.events for p in e.payload]
        variables.append(
            {
                "question": experiment.task.question if experiment.task else None,
                "sources": sorted(
                    {p.content.sha256 for p in records if isinstance(p, SourceDocument)}
                ),
                "models": sorted(
                    {
                        signature
                        for a in experiment.agents
                        if (signature := requested_model_signature(a)) is not None
                    }
                ),
                "tools": sorted(
                    {name for a in experiment.agents for name in a.permissions.allowed_tools}
                ),
                "criteria": experiment.task.evaluation_criteria if experiment.task else (),
            }
        )
        calls = {p.call_id: p for p in records if isinstance(p, ModelCall)}
        usage.append(
            {
                "model_calls": len(calls),
                "call_ceiling": experiment.budget.max_model_calls,
                "tokens_reported": [p.usage.model_dump(mode="json") for p in calls.values()],
            }
        )
        quality.append(correction_metrics(records))
    return {
        "conditions": [e.task.control_condition if e.task else "unspecified" for e in configs],
        "matching_variables": {k: variables[0][k] == variables[1][k] for k in variables[0]},
        "resource_usage": usage,
        "human_labels": quality,
        "compute_matched": usage[0] == usage[1],
        "causal_effect": None,
        "caveat": "Descriptive comparison; matched inputs do not establish research-quality gains.",
    }
