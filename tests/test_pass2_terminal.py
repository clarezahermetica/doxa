import asyncio
import json
from uuid import uuid4

import pytest
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Select,
    TextArea,
)

from doxa.cli.console import ResearchConsole
from doxa.cli.onboarding import GettingStarted, guide_preferences
from doxa.cli.reference import (
    ACTIONS,
    CommandReference,
    bindings_for,
    cli_reference,
    command_reference,
)
from doxa.core.workbench_demo import demonstrate


async def click(pilot, selector):
    widget = pilot.app.screen.query_one(selector)
    widget.scroll_visible(immediate=True, animate=False, force=True)
    await pilot.pause()
    assert await pilot.click(selector)
    await pilot.pause()


async def settle(pilot):
    for _ in range(8):
        await pilot.pause()
        if not pilot.app._loading:
            break


def test_first_guide_skip_reopen_and_preference(controller, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GettingStarted)
            await pilot.press("escape")
            await pilot.pause()
            assert guide_preferences()["show_getting_started"] is False
            await pilot.press("f1")
            await pilot.pause()
            assert isinstance(app.screen, CommandReference)
            await click(pilot, "#reference-guide")
            assert isinstance(app.screen, GettingStarted)
            app.screen.query_one("#guide-show", Checkbox).focus()
            await pilot.press("space")
            await pilot.press("escape")
            assert guide_preferences()["show_getting_started"] is True
            await pilot.press("q")
        app = ResearchConsole(controller.settings.data_dir)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GettingStarted)
            await pilot.press("escape")
            await pilot.press("q")

    asyncio.run(interaction())


def test_reference_covers_real_registries_and_search_does_not_print(
    controller, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))
    from typer.core import TyperGroup
    from typer.main import get_command

    from doxa.cli.main import app as cli

    expected = []

    def visit(c, p):
        expected.append(p)
        if isinstance(c, TyperGroup):
            for k, v in c.commands.items():
                visit(v, p + " " + k)

    visit(get_command(cli), "doxa")
    assert {r.title for r in cli_reference()} == set(expected)
    assert not capsys.readouterr().out

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            entries = command_reference(app)
            assert {b for b in bindings_for(type(app))} <= {e.title for e in entries}
            assert {a.title for a in ACTIONS} <= {e.title for e in entries}
            await pilot.press("f1")
            await pilot.pause()
            app.screen.query_one("#reference-search", Input).value = "doxa run cancel"
            await pilot.pause()
            assert any(e.title == "doxa run cancel" for e in app.screen.matches)
            assert app.screen.query_one("#reference-run", Button).disabled
            table = app.screen.query_one(DataTable)
            table.focus()
            await pilot.press("down", "enter")
            assert app.screen.focused.id == "reference-text"
            await pilot.press("escape")
            await pilot.press("ctrl+p")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.press("q")

    asyncio.run(interaction())


def test_activity_full_history_search_expansion_and_paging(controller, command):
    from doxa.core.models import Event, EventType, Evidence, Provenance

    run = controller.configure_run(command)
    previous = controller.inspect(run.id).events[-1]
    events = []
    for i in range(620):
        evidence = Evidence(
            experiment_id=run.experiment_id,
            run_id=run.id,
            trajectory_id=previous.trajectory_id,
            provenance=Provenance.IMPORTED_SOURCE,
            source="fixture",
            description=f"history-marker-{i}: " + "Long minority objection. " * 50,
        )
        event = Event(
            experiment_id=run.experiment_id,
            run_id=run.id,
            trajectory_id=previous.trajectory_id,
            sequence=1,
            type=EventType.CHALLENGE_SUBMITTED,
            payload=(evidence,),
            parent_event_ids=(previous.id,),
            idempotency_key=f"activity-{i}",
        )
        events.append(event)
        previous = event
    controller.ledger.append_batch(tuple(events))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            assert len(app.activity_rows) == 621
            assert app.query_one("#activity-operations", DataTable).row_count <= 100
            await click(pilot, "#activity-earlier")
            assert app.activity_page >= 0
            app.query_one("#activity-search", Input).value = "history-marker-0:"
            # A queued search can follow an in-flight read on the next polling tick.
            # Wait for the visible result, not merely a momentarily idle worker.
            for _ in range(200):
                await pilot.pause()
                if len(app.activity_rows) == 1:
                    break
                await asyncio.sleep(0.05)
            assert len(app.activity_rows) == 1
            table = app.query_one("#activity-operations", DataTable)
            table.focus()
            await pilot.press("enter")
            await pilot.pause()
            assert "Causal parents" in app.screen.query_one(TextArea).text
            await click(pilot, "#operation-raw")
            body = json.loads(app.screen.query_one(TextArea).text)
            assert body[0]["id"] == str(events[0].id)
            await pilot.press("escape")
            await pilot.resize_terminal(120, 40)
            await pilot.resize_terminal(160, 50)
            await pilot.press("q")

    asyncio.run(interaction())


@pytest.mark.parametrize("state", ["configured", "running", "completed", "failed", "cancelled"])
def test_state_actions_and_historical_running(controller, command, state):
    from doxa.core.models import Event, EventType, Provenance, RunState

    run = controller.configure_run(command)
    prev = controller.inspect(run.id).events[-1]
    if state != "configured":
        for status in ["running"] if state == "running" else ["running", state]:
            record = RunState(
                experiment_id=run.experiment_id,
                run_id=run.id,
                trajectory_id=prev.trajectory_id,
                provenance=Provenance.SYSTEM_INFERENCE,
                status=status,
                reason_code="fixture",
            )
            kind = {
                "running": EventType.RUN_STARTED,
                "completed": EventType.RUN_CLOSED,
                "failed": EventType.RUN_FAILED,
                "cancelled": EventType.RUN_CANCELLED,
            }[status]
            prev = controller.ledger.append(
                Event(
                    experiment_id=run.experiment_id,
                    run_id=run.id,
                    trajectory_id=prev.trajectory_id,
                    sequence=1,
                    type=kind,
                    payload=(record,),
                    idempotency_key=str(uuid4()),
                )
            )

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            if state == "running":
                assert "historical running" in app.state_label()
                assert "unverified" in app.state_label()
            if state in {"completed", "failed", "cancelled"}:
                assert app.unavailable_reason("start") and app.unavailable_reason("cancel")
            assert not app.unavailable_reason("export")
            await pilot.press("q")

    asyncio.run(interaction())


def test_grouping_preserves_criticism_failure_and_raw_ancestry(controller):
    from doxa.cli.activity import operations

    result = asyncio.run(demonstrate(controller))
    bundle = controller.inspect(result["run_id"])
    experiment = controller.ledger.get(bundle.run.experiment_id)
    rows = operations(list(bundle.events), experiment)
    assert [e.id for row in rows for e in row.events] == [e.id for e in bundle.events]
    assert len(rows) <= len(bundle.events)
    assert any("claim" in row.action for row in rows)


def test_new_user_completes_offline_workflow_using_guide(tmp_path, monkeypatch):
    from doxa.core.models import Claim

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))
    workspace = tmp_path / "fresh workspace"
    paper = tmp_path / "evidence.md"
    paper.write_text("Offline supplied evidence: use qualified conclusions.")

    async def interaction():
        app = ResearchConsole(workspace)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GettingStarted)
            await click(pilot, "#guide-offline")
            await click(pilot, "#guide-do")
            app.screen.query_one("#workspace-create", Checkbox).value = True
            await click(pilot, "#workspace-open")
            assert app.ready

            async def guide(step):
                if not isinstance(app.screen, GettingStarted):
                    await pilot.press("f1")
                    await pilot.pause()
                    await click(pilot, "#reference-guide")
                if app.screen.flow is not None:
                    await click(pilot, "#guide-back")
                await click(pilot, "#guide-offline")
                while app.screen.step < step:
                    await click(pilot, "#guide-next")
                while app.screen.step > step:
                    await click(pilot, "#guide-previous")

            await guide(1)
            await click(pilot, "#guide-do")  # New agent prerequisite is explained in step 2.
            app.screen.query_one("#setup-name", Input).value = "Offline reader"
            app.screen.query_one("#setup-text", TextArea).load_text(
                "Read supplied evidence; report uncertainty."
            )
            await click(pilot, "#setup-save")
            await guide(2)
            await click(pilot, "#guide-do")
            app.screen.query_one("#setup-name", Input).value = "A long offline experiment name " * 4
            app.screen.query_one("#setup-text", TextArea).load_text(
                "What does the supplied evidence support?"
            )
            app.screen.query_one("#setup-members", Input).value = "Offline reader:2"
            await click(pilot, "#setup-save")
            await settle(pilot)
            await guide(5)
            await click(pilot, "#guide-do")
            app.query_one("#record-kind", Select).value = "Agents"
            await settle(pilot)
            assert app.record_map
            await guide(3)
            await click(pilot, "#guide-do")
            app.screen.query_one("#file", Input).value = str(paper)
            await click(pilot, "#import-save")
            await guide(4)
            await click(pilot, "#guide-do")
            await click(pilot, "#start-save")
            for _ in range(600):
                await asyncio.sleep(0.05)
                if app.controller.inspect(app.selected).run.status == "completed":
                    break
            await settle(pilot)
            assert app.controller.inspect(app.selected).run.status == "completed"
            assert not app.controller.ledger.records("model_call")
            assert not app.controller.ledger.records("tool_audit")
            assert not app.controller.inspect(app.selected).accounting
            await guide(5)
            await click(pilot, "#guide-do")
            app.query_one("#record-kind", Select).value = "Claims"
            await settle(pilot)
            assert any(isinstance(r, Claim) for r in app.record_map.values())
            app.query_one("#records", DataTable).focus()
            await pilot.press("enter")
            assert "Synthetic" in app.query_one("#inspector", TextArea).text
            await guide(6)
            await click(pilot, "#guide-do")
            destination = tmp_path / "guided-export.json"
            app.screen.query_one("#export-path", Input).value = str(destination)
            await click(pilot, "#export-save")
            assert json.loads(destination.read_text())["run"]["status"] == "completed"
            await click(pilot, "#export-close")
            await pilot.resize_terminal(120, 40)
            await pilot.press("q")

    asyncio.run(interaction())


def test_uncertain_operation_and_worker_ownership_are_not_hidden(controller, command):
    from doxa.core.models import Event, EventType, ModelAssignment, ModelCall, Provenance, RunState
    from doxa.storage.workers import worker_lease

    run = controller.configure_run(command)
    prev = controller.inspect(run.id).events[-1]
    started = RunState(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=prev.trajectory_id,
        provenance=Provenance.SYSTEM_INFERENCE,
        status="running",
        reason_code="fixture",
    )
    controller.ledger.append(
        Event(
            experiment_id=run.experiment_id,
            run_id=run.id,
            trajectory_id=prev.trajectory_id,
            sequence=1,
            type=EventType.RUN_STARTED,
            payload=(started,),
            idempotency_key="running",
        )
    )
    call = ModelCall(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=prev.trajectory_id,
        provenance=Provenance.SYSTEM_INFERENCE,
        call_id=uuid4(),
        agent_id=uuid4(),
        assignment=ModelAssignment(provider="mock", model_id="fixture", instruction_version="1"),
        status="uncertain",
    )

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        with worker_lease(controller.settings.data_dir, run.id):
            async with app.run_test(size=(120, 40)) as pilot:
                await settle(pilot)
                assert "local worker owned" in app.state_label()
                controller.ledger.append(
                    Event(
                        experiment_id=run.experiment_id,
                        run_id=run.id,
                        trajectory_id=prev.trajectory_id,
                        sequence=1,
                        type=EventType.MODEL_CALL_RECORDED,
                        payload=(call,),
                        idempotency_key="uncertain",
                    )
                )
                app.poll()
                await settle(pilot)
                assert "uncertain" in app.state_label()
                app.action_recovery()
                await pilot.pause()
                assert (
                    "No reservation is automatically released"
                    in app.screen.query_one(TextArea).text
                )
                await click(pilot, "#detail-close")
                await pilot.press("q")

    asyncio.run(interaction())


def test_missing_model_state_offers_inspection_not_live_execution(controller):
    from doxa.core.models import Role, TaskSpecification
    from doxa.core.workbench import (
        NewAgent,
        NewExperiment,
        ParticipantGroup,
        add_agent,
        create_experiment,
    )

    agent = add_agent(
        controller,
        NewAgent(display_name="Unassigned", role=Role.RESEARCHER, instructions="Fixture"),
    )
    create_experiment(
        controller,
        NewExperiment(
            name="No assigned runtime",
            task=TaskSpecification(question="Fixture"),
            participants=(ParticipantGroup(agent_id=agent.id, count=1),),
            execution_kind="live",
            idempotency_key="unassigned",
        ),
    )

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            assert "setup unavailable" in app.state_label()
            assert app.unavailable_reason("start")
            assert not app.unavailable_reason("inspect")
            assert not app.can_guide_start()
            await pilot.press("q")

    asyncio.run(interaction())


def test_minority_responses_and_uncertainty_keep_separate_operations(controller):
    from doxa.cli.activity import operations
    from doxa.core.models import CouncilMessage, Event, EventType, Provenance

    result = asyncio.run(demonstrate(controller))
    bundle = controller.inspect(result["run_id"])
    exp = controller.ledger.get(bundle.run.experiment_id)
    base = bundle.events[-1]
    events = []
    for kind, text in [
        ("CLAIM", "Majority conclusion"),
        ("CHALLENGE", "Minority objection retained"),
        ("RESPONSE", "Response retains uncertainty"),
    ]:
        message = CouncilMessage(
            experiment_id=exp.id,
            run_id=bundle.run.id,
            trajectory_id=base.trajectory_id,
            provenance=Provenance.MODEL_OUTPUT,
            message_type=kind,
            sender_id=exp.agents[0].id,
            visibility="shared",
            content=text,
        )
        events.append(
            Event(
                experiment_id=exp.id,
                run_id=bundle.run.id,
                trajectory_id=base.trajectory_id,
                sequence=1,
                type=EventType.OBSERVATION_RECEIVED,
                payload=(message,),
                idempotency_key=str(uuid4()),
            )
        )
    rows = operations(events, exp)
    assert len(rows) == 3
    assert [row.result for row in rows] == [
        "Majority conclusion",
        "Minority objection retained",
        "Response retains uncertainty",
    ]
