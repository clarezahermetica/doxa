"""Real Textual widgets with explicitly synthetic offline research records."""

import asyncio
import json
import sys

import pytest
from textual.widgets import Input, TabbedContent, TextArea

from doxa.cli.console import ResearchConsole
from doxa.cli.inspectors import describe_record
from doxa.cli.research_view import CitationScreen, ThreadScreen
from doxa.core.controls import compare_controls, prepare_control, requested_model_signature
from doxa.core.models import Agent, Annotation, Claim, ModelAssignment, ProcedureManifest, Role
from doxa.core.quality_labels import correction_metrics, label_correction
from doxa.core.research_manifest import public_summary
from doxa.core.workbench import DebateExecution, DebateRuntime
from tests.test_cli_session import REAL_RUN
from tests.test_investigation_protocol import prepare


def test_matching_model_settings_include_temperature_and_wire_protocol():
    actor = Agent(
        role=Role.RESEARCHER,
        instructions="Offline matching test.",
        model=ModelAssignment(
            provider="custom",
            model_id="unknown-model",
            instruction_version="1",
            settings={"temperature": 0, "request_protocol": "default", "profile_id": "a"},
        ),
    )
    assert actor.model is not None

    def with_settings(**changes):
        return actor.model_copy(
            update={
                "model": actor.model.model_copy(
                    update={"settings": {**actor.model.settings, **changes}}
                )
            }
        )

    assert requested_model_signature(actor) == requested_model_signature(
        with_settings(profile_id="b")
    )
    assert requested_model_signature(actor) != requested_model_signature(
        with_settings(temperature=1)
    )
    assert requested_model_signature(actor) != requested_model_signature(
        with_settings(request_protocol="responses")
    )


def test_controls_preserve_sources_and_settings_but_disclose_different_resources(controller):
    original = prepare(controller)
    before = controller.inspect(original.id).model_dump_json()
    solo = prepare_control(controller, original.id, "solo")
    self_correct = prepare_control(controller, original.id, "self_correction")
    comparison = compare_controls(controller, solo, self_correct)
    assert all(comparison["matching_variables"].values())
    assert not comparison["compute_matched"] and comparison["causal_effect"] is None
    assert controller.inspect(solo).run.status == "configured"
    assert controller.inspect(original.id).model_dump_json() == before
    runtime = DebateRuntime(controller, self_correct)
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    assert bundle.run.status == "completed"
    assert any(isinstance(p, Claim) and p.revises_id for e in bundle.events for p in e.payload)


def test_human_labels_are_required_for_correction_metrics_and_manifest_has_no_local_paths(
    controller,
):
    run = prepare(controller)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    assert correction_metrics(records)["net_justified_correction"] is None
    revision = next(p for p in records if isinstance(p, Claim) and p.revises_id)
    label_correction(
        controller,
        run.id,
        revision.trajectory_id,
        revision.id,
        False,
        True,
        True,
        "Explicit human fixture label, not scientific ground truth.",
        "test-reviewer",
    )
    records = [p for e in controller.inspect(run.id).events for p in e.payload]
    metrics = correction_metrics(records)
    assert metrics["net_justified_correction"] == 1 and metrics["fully_labeled_revisions"] == 1
    assert any(isinstance(p, Annotation) for p in records)
    assert any(isinstance(p, ProcedureManifest) for p in records)
    summary = json.dumps(public_summary(controller, run.id))
    assert str(controller.settings.data_dir) not in summary
    assert "test-reviewer" not in summary and "instructions" not in summary


def test_actual_fixture_stream_emits_only_safe_observable_milestones(tmp_path):
    observed = []
    events = [
        {"type": "thread.started"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "reasoning", "text": "PRIVATE REASONING"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "fixture output"}},
        {"type": "turn.completed"},
    ]
    program = (
        "import json;events=" + repr(events) + ";[print(json.dumps(e),flush=True) for e in events]"
    )
    result = asyncio.run(
        REAL_RUN([sys.executable, "-c", program], tmp_path, events=20, on_event=observed.append)
    )
    assert result.code == 0
    assert observed == ["session_started", "turn_started", "output_available", "turn_finished"]
    assert "PRIVATE" not in json.dumps(observed)


@pytest.mark.parametrize(
    "size,theme",
    [
        ((80, 24), "textual-dark"),
        ((100, 30), "textual-light"),
        ((120, 40), "textual-dark"),
        ((160, 50), "textual-light"),
    ],
)
def test_exchange_citation_expansion_and_read_only_replay(
    controller, monkeypatch, tmp_path, size, theme
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))
    run = prepare(controller, text="[Page 1]\nIRRELEVANT_PAGE_ONE\n[Page 4]\nCITED_PASSAGE_FOUR")
    asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    before = controller.inspect(run.id).model_dump_json()

    async def view():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.selected = run.id
        app.theme = theme
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "activity"
            assert app.query_one("#activity-inspector").display == (size[0] >= 100)
            app.action_exchanges()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ThreadScreen)
            text = app.screen.query_one("#thread-text", TextArea).text
            assert (
                "OBJECTION" in text and "AUTHOR RESPONSE" in text and "VERSION COMPARISON" in text
            )
            assert "IRRELEVANT_PAGE_ONE" not in text
            thread = app.screen.thread
            assert "IRRELEVANT_PAGE_ONE" not in describe_record(controller, thread.current)
            app.screen.query_one("#thread-sources").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, CitationScreen)
            field = app.screen.query_one("#citation-page", Input)
            field.value = "4"
            field.focus()
            await pilot.press("enter")
            await pilot.pause()
            passage = app.screen.query_one("#citation-text", TextArea).text
            assert "CITED_PASSAGE_FOUR" in passage and "IRRELEVANT_PAGE_ONE" not in passage
            app.screen.query_one("#citation-full").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert "IRRELEVANT_PAGE_ONE" in app.screen.query_one("#citation-text", TextArea).text
            await pilot.press("escape", "escape")
            app.action_replay()
            await pilot.pause()
            assert "REPLAY" in app.screen.heading

    asyncio.run(view())
    assert controller.inspect(run.id).model_dump_json() == before
