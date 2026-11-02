"""Research data must remain text rather than application-action markup."""

import asyncio

import pytest
from rich.text import Text
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Select, TabbedContent

from doxa.cli.console import ResearchConsole
from doxa.core.workbench import ImportSource, import_source

PAYLOAD = "[@click=app.cancel]inspect[/]"


@pytest.mark.parametrize("surface", ["runs", "activity", "inspect"])
def test_persisted_research_text_cannot_cancel_run_when_its_cell_is_clicked(
    controller, command, tmp_path, monkeypatch, surface
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))
    experiment = command.experiment.model_copy(
        update={"name": PAYLOAD if surface == "runs" else "Literal evidence test"}
    )
    run = controller.configure_run(command.model_copy(update={"experiment": experiment}))
    if surface != "runs":
        import_source(
            controller,
            run.id,
            ImportSource(title=PAYLOAD, text="Ordinary source", idempotency_key="literal-title"),
        )

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.select_experiment(run.id)
            await pilot.pause()
            if surface == "runs":
                table = app.query_one("#runs", DataTable)
                row, column = 0, 0
            elif surface == "inspect":
                app.query_one(TabbedContent).active = "inspect"
                app.query_one("#record-kind", Select).value = "Sources"
                await pilot.pause()
                table = app.query_one("#records", DataTable)
                row, column = 0, 0
            else:
                table = app.query_one("#activity-operations", DataTable)
                row, column = 1, 3
            cell = table.get_cell_at(Coordinate(row, column))
            assert isinstance(cell, Text), "Untrusted table values must be literal Rich Text"
            assert "[@click=app.cancel]" in cell.plain and not cell.spans
            table.focus()
            table.move_cursor(row=row, column=column)
            region = table._get_cell_region(Coordinate(row, column))
            assert await pilot.click(table, offset=(region.x + 1, region.y))
            await pilot.pause()
            assert controller.inspect(run.id).run.status == "configured"
            # The legitimate command remains available and functional.
            app.action_cancel()
            assert controller.inspect(run.id).run.status == "cancelled"
            await pilot.press("escape", "q")

    asyncio.run(interaction())


@pytest.mark.parametrize(
    "payload", [PAYLOAD, "[link=https://example.invalid]source[/link]", "[unfinished [brackets ☃"]
)
def test_review_options_preserve_literal_text_and_original_identities(
    controller, tmp_path, monkeypatch, payload
):
    from textual.widgets import SelectionList

    from doxa.cli.screens import ReviewScreen
    from doxa.core.models import Experiment, Role, TaskSpecification, Trajectory
    from doxa.core.text_research import ReviewClaim
    from doxa.core.workbench import (
        NewAgent,
        NewExperiment,
        ParticipantGroup,
        add_agent,
        create_experiment,
    )

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))
    template = add_agent(
        controller,
        NewAgent(
            display_name=payload, role=Role.RESEARCHER, instructions="Read the supplied source."
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Literal options",
            task=TaskSpecification(question="Inspect literal text"),
            participants=(ParticipantGroup(agent_id=template.id),),
            idempotency_key="literal-options",
        ),
    )
    experiment = controller.ledger.get(run.experiment_id)
    assert isinstance(experiment, Experiment)
    branch = next(
        p.id
        for e in controller.inspect(run.id).events
        for p in e.payload
        if isinstance(p, Trajectory) and p.parent_id is None
    )
    source = import_source(
        controller,
        run.id,
        ImportSource(title=payload, text="Source text", idempotency_key="option-source"),
    )
    event = controller.review_command(
        run.id,
        branch,
        ReviewClaim(
            proposition=payload,
            author_id=experiment.agents[0].id,
            source_ids=(source.id,),
            idempotency_key="option-claim",
        ),
    )
    claim = next(p for p in event.payload if p.kind == "claim")

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.push_screen(ReviewScreen(controller, run.id, branch))
            await pilot.pause()
            targets = app.screen.query_one("#review-target", Select)
            targets.value = str(claim.id)
            label = next(label for label, value in targets._options if value == str(claim.id))
            assert isinstance(label, Text) and label.plain == payload and not label.spans
            actors = app.screen.query_one("#review-actor", Select)
            label = next(
                label for label, value in actors._options if value == str(experiment.agents[0].id)
            )
            assert isinstance(label, Text) and label.plain == experiment.agents[0].display_name
            assert not label.spans
            sources = app.screen.query_one("#review-sources", SelectionList)
            assert str(sources.get_option_at_index(0).prompt) == payload
            sources.select(str(source.id))
            assert sources.selected == [str(source.id)] and targets.value == str(claim.id)
            await pilot.press("escape", "q")

    asyncio.run(interaction())
