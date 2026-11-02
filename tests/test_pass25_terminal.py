"""Focused Pass 2.5 interaction coverage; no external services."""

import asyncio

import pytest
from textual.widgets import Button, Input, Label, Select, TextArea

from doxa.cli.console import ResearchConsole
from doxa.cli.onboarding import GettingStarted
from doxa.cli.reference import REFERENCE_CATEGORIES, CommandReference
from doxa.cli.workspace_screen import WorkspaceScreen
from doxa.core.workbench_demo import demonstrate


async def click(pilot, selector):
    widget = pilot.app.screen.query_one(selector)
    widget.scroll_visible(immediate=True, animate=False, force=True)
    await pilot.pause()
    assert await pilot.click(selector)
    await pilot.pause()


def test_compact_home_choices_and_task_reference(controller, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, GettingStarted)
            assert app.screen.query_one("#guide-dialog").region.height < 20
            assert not app.screen.query_one("#guide-do").display
            for key in ("explore", "offline", "help"):
                assert app.screen.query_one("#guide-" + key, Button).display
            await click(pilot, "#guide-help")
            assert isinstance(app.screen, CommandReference)
            assert len(app.screen.matches) < 25
            assert all(e.action or e.callback for e in app.screen.matches)
            picker = app.screen.query_one("#reference-category", Select)
            for category in REFERENCE_CATEGORIES[1:-1]:
                picker.value = category
                await pilot.pause()
                assert app.screen.matches
                assert all(e.category == category for e in app.screen.matches)
            app.screen.query_one("#reference-search", Input).value = "doxa run start"
            await pilot.pause()
            assert any(e.title == "doxa run start" for e in app.screen.matches)
            assert app.screen.query_one("#reference-run", Button).disabled
            await pilot.press("escape", "q")

    asyncio.run(interaction())


@pytest.mark.parametrize("state", ["configured", "running", "completed", "failed"])
def test_guide_start_explains_state_and_missing_templates(controller, tmp_path, monkeypatch, state):
    from doxa.core.models import Event, EventType, RunState

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))
    result = asyncio.run(demonstrate(controller))
    # Use a fresh configured text experiment; transition through real ledger records.
    from doxa.core.models import TaskSpecification
    from doxa.core.workbench import NewExperiment, ParticipantGroup, create_experiment

    agent = controller.configuration().agents[0]
    run = create_experiment(
        controller,
        NewExperiment(
            name="Guide state",
            idempotency_key="guide-state",
            task=TaskSpecification(question="Offline question"),
            participants=(ParticipantGroup(agent_id=agent.id, count=1),),
        ),
    )
    previous = controller.inspect(run.id).events[-1]
    if state != "configured":
        for status in ["running"] if state == "running" else ["running", state]:
            record = RunState(
                experiment_id=run.experiment_id,
                run_id=run.id,
                trajectory_id=previous.trajectory_id,
                status=status,
                reason_code="fixture",
                provenance="system_inference",
            )
            previous = controller.ledger.append(
                Event(
                    experiment_id=run.experiment_id,
                    run_id=run.id,
                    trajectory_id=previous.trajectory_id,
                    sequence=1,
                    type={
                        "running": EventType.RUN_STARTED,
                        "completed": EventType.RUN_CLOSED,
                        "failed": EventType.RUN_FAILED,
                    }[status],
                    payload=(record,),
                    idempotency_key="pass25-" + status,
                )
            )
    assert result

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.selected = run.id
            app.poll()
            for _ in range(8):
                await pilot.pause()
            app.action_guide()
            await pilot.pause()
            await click(pilot, "#guide-offline")
            app.screen.step = 4
            app.screen.update_step()
            button = app.screen.query_one("#guide-do", Button)
            reason = str(app.screen.query_one("#guide-reason", Label).render())
            assert button.disabled == (state != "configured")
            assert state in reason if state != "configured" else "Next:" in reason
            text = app.screen.query_one(TextArea).text
            assert "Responses are simulated" in text and "not live inference" in text
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_workspace_sync_precautions_follow_edited_path(controller, tmp_path):
    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.push_screen(WorkspaceScreen(tmp_path / "OneDrive - Research" / "workspace"))
            await pilot.pause()
            assert "not a database backup" in str(
                app.screen.query_one("#workspace-sync", Label).render()
            )
            app.screen.query_one("#workspace-path", Input).value = str(tmp_path / "local")
            await pilot.pause()
            assert not str(app.screen.query_one("#workspace-sync", Label).render())
            await click(pilot, "#workspace-close")
            await pilot.press("q")

    asyncio.run(interaction())


def test_guide_explains_missing_agent_before_creation(controller, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await click(pilot, "#guide-offline")
            app.screen.step = 2
            app.screen.update_step()
            assert app.screen.query_one("#guide-do", Button).disabled
            assert "agent template first" in str(
                app.screen.query_one("#guide-reason", Label).render()
            )
            await click(pilot, "#guide-previous")
            assert not app.screen.query_one("#guide-do", Button).disabled
            await click(pilot, "#guide-do")
            assert app.screen.kind == "agent"
            await click(pilot, "#setup-cancel")
            await pilot.press("q")

    asyncio.run(interaction())
