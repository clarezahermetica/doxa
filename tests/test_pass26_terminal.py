import asyncio

import pytest
from textual.widgets import Button

from doxa.cli.console import ResearchConsole
from doxa.cli.onboarding import GettingStarted


async def click(pilot, selector):
    from textual.css.query import NoMatches

    # A pushed screen can become active before its composed children finish mounting.
    for _ in range(200):
        await pilot.pause(0.05)
        try:
            widget = pilot.app.screen.query_one(selector)
        except NoMatches:
            continue
        if widget.is_mounted:
            break
    else:
        raise AssertionError(f"Control did not mount: {selector}")
    widget.scroll_visible(immediate=True, animate=False, force=True)
    await pilot.pause()
    assert await pilot.click(selector)
    await pilot.pause(0.35)


def test_guided_child_cancel_returns_to_origin(controller, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await click(pilot, "#guide-offline")
            await click(pilot, "#guide-next")
            guide = app.screen
            assert guide.step == 1
            await click(pilot, "#guide-do")
            await click(pilot, "#setup-cancel")
            assert app.screen is guide
            assert isinstance(app.screen, GettingStarted)
            assert app.screen.step == 1
            assert not app.screen.query_one("#guide-do", Button).disabled
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_child_save_escape_reopen_and_preferences(controller, tmp_path, monkeypatch):
    from textual.widgets import Checkbox, Input, Label, TextArea

    from doxa.cli.onboarding import guide_preferences

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await click(pilot, "#guide-offline")
            guide = app.screen
            await click(pilot, "#guide-do")
            await pilot.press("escape")
            assert app.screen is guide and guide.step == 0
            assert not guide_preferences()
            await click(pilot, "#guide-next")
            for _ in range(2):
                await click(pilot, "#guide-do")
                await pilot.press("escape")
                assert app.screen is guide and guide.step == 1
            await click(pilot, "#guide-do")
            app.screen.query_one("#setup-name", Input).value = "New guide participant"
            app.screen.query_one("#setup-text", TextArea).load_text("Inspect evidence.")
            await click(pilot, "#setup-save")
            assert app.screen is guide and guide.step == 1
            assert app.screen.focused.id == "guide-do"
            await click(pilot, "#guide-next")
            assert not app.screen.query_one("#guide-do", Button).disabled
            assert "Next:" in str(app.screen.query_one("#guide-reason", Label).render())
            guide.query_one("#guide-show", Checkbox).value = True
            await pilot.press("escape")
            await pilot.press("f1")
            await click(pilot, "#reference-guide")
            assert isinstance(app.screen, GettingStarted)
            assert app.screen.step == 2 and app.screen.offline
            assert guide_preferences()["show_getting_started"] is True
            await click(pilot, "#guide-back")
            assert app.screen.flow is None
            await click(pilot, "#guide-offline")
            await click(pilot, "#guide-previous")
            assert app.screen.flow is None
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_completed_selection_new_experiment_import_returns_to_intended_guide(
    controller, tmp_path, monkeypatch
):
    from textual.widgets import Input, TextArea

    from doxa.core.workbench_demo import demonstrate

    old = asyncio.run(demonstrate(controller))["run_id"]
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))
    document = tmp_path / "paper.md"
    document.write_text("Supplied evidence only.")

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await click(pilot, "#guide-offline")
            guide = app.screen
            guide.step = 3
            guide.update_step()
            assert guide.query_one("#guide-do", Button).disabled
            assert guide.query_one("#guide-alternative", Button).display
            await click(pilot, "#guide-alternative")
            assert app.screen.execution_kind == "synthetic"
            app.screen.query_one("#setup-name", Input).value = "Intended new experiment"
            app.screen.query_one("#setup-text", TextArea).load_text("What is supported?")
            name = controller.configuration().agents[0].display_name
            app.screen.query_one("#setup-members", Input).value = name + ":2"
            await click(pilot, "#setup-save")
            assert app.screen is guide and guide.step == 3
            assert app.selected != old
            assert controller.inspect(app.selected).run.status == "configured"
            assert not guide.query_one("#guide-do", Button).disabled
            await click(pilot, "#guide-do")
            app.screen.query_one("#file", Input).value = str(document)
            await click(pilot, "#import-save")
            assert app.screen is guide and guide.step == 3
            assert controller.inspect(old).run.status == "completed"
            assert not controller.ledger.records("model_call")
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_general_research_mode_is_explicit_and_never_converts_live(
    controller, tmp_path, monkeypatch
):
    from textual.widgets import Input, Label, Select, TextArea

    from doxa.core.models import Role
    from doxa.core.workbench import NewAgent, add_agent

    add_agent(
        controller, NewAgent(display_name="Unassigned", role=Role.RESEARCHER, instructions="Read.")
    )
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await click(pilot, "#guide-research")
            guide = app.screen
            await click(pilot, "#guide-next")
            assert guide.query_one("#guide-mode").display
            assert guide.query_one("#guide-next", Button).disabled
            assert guide.query_one("#guide-do", Button).disabled
            guide.query_one("#guide-mode", Select).value = "live"
            await pilot.pause()
            await click(pilot, "#guide-do")
            assert app.screen.__class__.__name__ == "ModelScreen"
            await pilot.press("escape")
            assert app.screen is guide and guide.execution == "live" and guide.step == 1
            guide.query_one("#guide-mode", Select).value = Select.NULL
            await pilot.pause()
            assert guide.query_one("#guide-next", Button).disabled
            guide.query_one("#guide-mode", Select).value = "live"
            await pilot.pause()
            await click(pilot, "#guide-next")
            await click(pilot, "#guide-next")
            await click(pilot, "#guide-do")
            assert app.screen.query_one("#setup-execution", Select).value == "live"
            app.screen.query_one("#setup-name", Input).value = "Model-backed configuration"
            app.screen.query_one("#setup-text", TextArea).load_text("Question")
            app.screen.query_one("#setup-members", Input).value = "Unassigned:1"
            await click(pilot, "#setup-save")
            assert app.screen is guide
            assert controller.inspect(app.selected).run.execution_kind == "live"
            guide.step = 6
            guide.update_step()
            assert guide.query_one("#guide-do", Button).disabled
            assert "Model assignment missing" in str(
                guide.query_one("#guide-reason", Label).render()
            )
            assert not controller.ledger.records("model_call")
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_direct_experiment_form_requires_execution_choice(controller):
    from textual.widgets import Input, Label, Select, TextArea

    from doxa.core.models import Role
    from doxa.core.workbench import NewAgent, add_agent

    add_agent(
        controller, NewAgent(display_name="Reader", role=Role.RESEARCHER, instructions="Read.")
    )

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.action_new()
            await pilot.pause()
            screen = app.screen
            assert screen.query_one("#setup-execution", Select).value is Select.NULL
            screen.query_one("#setup-name", Input).value = "No implicit simulation"
            screen.query_one("#setup-text", TextArea).load_text("Question")
            screen.query_one("#setup-members", Input).value = "Reader:1"
            await click(pilot, "#setup-save")
            assert app.screen is screen and not controller.list_runs()
            assert "execution mode" in str(screen.query_one("#setup-error", Label).render())
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_controller_can_create_another_attempt_of_immutable_experiment(controller):
    from doxa.core.controller import ConfigureRun
    from doxa.core.workbench_demo import demonstrate

    original = controller.inspect(asyncio.run(demonstrate(controller))["run_id"])
    experiment = controller.ledger.get(original.run.experiment_id)
    old_bytes = experiment.model_dump_json()
    another = controller.configure_run(
        ConfigureRun(
            experiment=experiment,
            mode=original.run.mode,
            execution_kind="synthetic",
            idempotency_key="separate-attempt-existing-configuration",
        )
    )
    assert another.id != original.run.id and another.experiment_id == original.run.experiment_id
    assert controller.ledger.get(experiment.id).model_dump_json() == old_bytes
    assert controller.inspect(original.run.id).run.status == "completed"
    assert controller.inspect(another.id).run.status == "configured"


@pytest.mark.parametrize("size", [(80, 24), (120, 40), (160, 50)])
def test_agent_labels_keyboard_defaults_and_persisted_permissions(
    controller, tmp_path, monkeypatch, size
):
    from textual.widgets import Checkbox, Input, Label, Select, SelectionList, TextArea

    from doxa.cli.screens import SetupScreen

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await click(pilot, "#guide-offline")
            await click(pilot, "#guide-next")
            guide = app.screen
            await click(pilot, "#guide-do")
            form = app.screen
            labels = " ".join(str(label.render()) for label in form.query(Label))
            for phrase in (
                "Agent name",
                "Instructions",
                "Role",
                "Model assignment",
                "Enabled status",
                "Memory scope",
                "Tool permissions",
            ):
                assert phrase in labels
            assert form.can_view_entire(form.query_one("#setup-save"))
            assert form.can_view_entire(form.query_one("#setup-cancel"))
            assert form.query_one("#setup-tools", SelectionList).selected == []
            assert form.query_one("#setup-memory", Select).value == "private"
            assert form.query_one("#setup-profile", Select).value == ""
            assert form.query_one("#setup-enabled", Checkbox).value
            name = form.query_one("#setup-name", Input)
            name.focus()
            await pilot.press("tab")
            assert form.focused.id == "setup-text"
            await pilot.press("tab")
            assert form.focused.id == "setup-role"
            await pilot.press("space", "escape")
            assert app.screen is form  # Escape closes the dropdown first.
            name.value = "Offline template"
            form.query_one("#setup-text", TextArea).load_text("Use supplied evidence only.")
            await click(pilot, "#setup-save")
            assert app.screen is guide
            definition = controller.configuration().agents[0]
            assert not definition.agent.permissions.allowed_tools
            # A guide Add action creates a template even if Inspect held an existing one.
            app.selected_record = definition
            await click(pilot, "#guide-do")
            assert app.screen.definition is None
            await pilot.press("escape")
            assert app.screen is guide
            # Existing settings are displayed unchanged; opt-in is a configuration write only.
            app.push_screen(SetupScreen(controller, "agent", definition))
            await pilot.pause()
            tools = app.screen.query_one("#setup-tools", SelectionList)
            tools.scroll_visible(immediate=True, animate=False, force=True)
            tools.focus()
            await pilot.press("space")
            assert tools.selected == ["web_search"]
            await click(pilot, "#setup-save")
            assert app.screen is guide
            updated = controller.configuration().agents[0]
            assert updated.version == definition.version + 1
            assert updated.agent.permissions.allowed_tools == ("web_search",)
            assert definition.agent.permissions.allowed_tools == ()
            app.push_screen(SetupScreen(controller, "agent", updated))
            await pilot.pause()
            assert app.screen.query_one("#setup-tools", SelectionList).selected == ["web_search"]
            await pilot.press("escape")
            assert app.screen is guide
            assert not controller.list_runs()
            assert not controller.ledger.records("model_call")
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_existing_research_picker_and_nested_help_return(controller, tmp_path, monkeypatch):
    from textual.widgets import DataTable

    from doxa.cli.onboarding import ExperimentPicker
    from doxa.cli.reference import CommandReference
    from doxa.core.workbench_demo import demonstrate

    result = asyncio.run(demonstrate(controller))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            guide = app.screen
            await click(pilot, "#guide-explore")
            assert isinstance(app.screen, ExperimentPicker)
            await pilot.press("escape")
            assert app.screen is guide and guide.flow is None
            await click(pilot, "#guide-offline")
            await click(pilot, "#guide-next")
            await click(pilot, "#guide-do")
            form = app.screen
            await pilot.press("f1")
            assert isinstance(app.screen, CommandReference)
            await pilot.press("f1")
            assert len(app.screen_stack) == 4
            await pilot.press("escape")
            assert app.screen is form
            await pilot.press("f1")
            await click(pilot, "#reference-guide")
            for _ in range(8):
                await pilot.pause()
            assert app.screen is guide and guide.step == 1
            await click(pilot, "#guide-back")
            await click(pilot, "#guide-explore")
            app.screen.query_one(DataTable).focus()
            await pilot.press("enter")
            for _ in range(8):
                await pilot.pause()
            assert len(app.screen_stack) == 1
            assert str(app.selected) == str(result["run_id"])
            await pilot.press("q")

    asyncio.run(interaction())
