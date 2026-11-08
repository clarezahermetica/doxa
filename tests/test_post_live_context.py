"""Offline regressions for the real third-turn context failure; no live calls."""

import json
from uuid import uuid4

import pytest

from doxa.core.context_planning import ContextBudget, cli_prompt, input_size
from doxa.core.cycle_preflight import cycle_preflight
from doxa.core.models import BudgetPolicy, CouncilLimits, ModelCall, Role, TaskSpecification
from doxa.core.profiles import CouncilConfig
from doxa.core.runtime_identity import runtime_identity
from doxa.core.workbench import (
    ContextAssembler,
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)
from doxa.providers.cli_session import CodexCliProvider, research_schema
from doxa.providers.contracts import ModelMessage
from tests.test_cli_session import fake_cli as fake_cli
from tests.test_cli_session import profile


def test_shared_accounting_includes_unicode_envelope_schema_and_output():
    messages = (ModelMessage(role="user", content='中文 "quotation" \\ test'),)
    schema = research_schema()
    assert input_size(messages, schema, True) == len(cli_prompt(messages)) + len(
        json.dumps(schema).encode()
    )
    p = profile()
    assert CodexCliProvider(p).capabilities(None).text_generation == "available"
    budget = ContextBudget(100, 100, 50, schema=schema, cli=True)
    with pytest.raises(ValueError, match="schema=.*reserved_output=50"):
        budget.require("instructions", "question", "active objection")


def test_six_turn_rehearsal_fits_large_sources_without_touching_real_ledger(controller, fake_cli):
    p = profile(max_context_tokens=67584, max_input_bytes=131072)
    controller.save_configuration(CouncilConfig(profiles=(p,)))
    groups = []
    for role in (Role.RESEARCHER, Role.SKEPTIC, Role.ARCHIVIST):
        actor = add_agent(
            controller,
            NewAgent(
                display_name=role.value,
                role=role,
                instructions="Use evidence and preserve uncertainty.",
                profile_id=p.id,
                profile_version=1,
                remote_inference=True,
            ),
        )
        groups.append(ParticipantGroup(agent_id=actor.id))
    run = create_experiment(
        controller,
        NewExperiment(
            name="Bounded original failure regression",
            execution_kind="live",
            task=TaskSpecification(
                question="intrinsic feedback reliability",
                structured_actions=True,
                council=CouncilLimits(
                    rounds=2, max_calls=6, per_agent_tokens=131072, total_tokens=393216
                ),
            ),
            participants=tuple(groups),
            budget=BudgetPolicy(
                max_model_calls=6, max_context_tokens=67584, max_output_tokens=2048
            ),
            idempotency_key=str(uuid4()),
        ),
    )
    source = import_source(
        controller,
        run.id,
        ImportSource(
            title="Long paper",
            text="[Page 1]\n" + "intrinsic feedback evidence 中文 " * 3000,
            idempotency_key="long-paper",
        ),
    )
    before = controller.inspect(run.id).model_dump_json()
    result = cycle_preflight(controller, run.id)
    assert result["passed"], result
    assert result["turns_exercised"] == 6 and result["model_calls"] == 0
    assert controller.inspect(run.id).model_dump_json() == before
    assert not fake_cli.calls
    assert not any(
        isinstance(p, ModelCall) for e in controller.inspect(run.id).events for p in e.payload
    )
    assembler = ContextAssembler(controller, run.id)
    manifest = assembler.assemble(assembler.runtime.experiment.agents[0], "bounded")
    assert "partial_source" in manifest.omitted[str(source.id)]
    assert manifest.input_token_upper_bound < 20000


def test_required_context_fails_before_source_or_provider_dispatch(controller, fake_cli):
    actor = add_agent(
        controller,
        NewAgent(
            display_name="Reader",
            role=Role.RESEARCHER,
            instructions="Required instructions " * 200,
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Tiny context",
            task=TaskSpecification(question="Evidence", council=CouncilLimits(rounds=1)),
            participants=(ParticipantGroup(agent_id=actor.id),),
            budget=BudgetPolicy(max_context_tokens=1024),
            idempotency_key=str(uuid4()),
        ),
    )
    assembler = ContextAssembler(controller, run.id)
    before = len(controller.inspect(run.id).events)
    with pytest.raises(ValueError, match="task, instructions and response schema"):
        assembler.assemble(assembler.runtime.experiment.agents[0], "too-small")
    assert len(controller.inspect(run.id).events) == before and not fake_cli.calls


def test_runtime_identity_reads_installed_target_without_switching_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    launcher = tmp_path / "Programs/DOXA/bin/doxa.cmd"
    launcher.parent.mkdir(parents=True)
    launcher.write_text('"%~dp0..\\versions\\v17\\DOXA\\doxa.exe" %*')
    workspace = tmp_path / "selected workspace"
    result = runtime_identity(workspace)
    assert result["installed_build"] == "v17" and result["warning"]
    assert result["workspace"] == str(workspace.resolve()) and not workspace.exists()
