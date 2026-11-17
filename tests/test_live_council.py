"""Exercise Live Council through real offline ledger records and Textual widgets."""

import asyncio
from uuid import uuid4

import pytest
from textual.widgets import Button, Checkbox, Input, Select, Static, TextArea

from doxa.cli.console import ResearchConsole
from doxa.cli.council_branch import CouncilBranch
from doxa.cli.council_feed import CouncilFeed
from doxa.cli.live_council import PAGE, FeedScroll, LiveCouncil
from doxa.core.models import (
    Challenge,
    Checkpoint,
    Claim,
    Event,
    EventType,
    Role,
    RunState,
    TaskSpecification,
    Trajectory,
)
from doxa.core.text_research import (
    ReviewAssessment,
    ReviewChallenge,
    ReviewCheckpoint,
    ReviewClaim,
    ReviewDecision,
    ReviewResponse,
)
from doxa.core.workbench import (
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)
from doxa.systems.research import branch_events


@pytest.fixture
def dialogue(controller):
    people = (
        ("Researcher", Role.RESEARCHER),
        ("Executor", Role.EXECUTOR),
        ("First Skeptic", Role.SKEPTIC),
        ("Second Skeptic", Role.SKEPTIC),
        ("Archivist", Role.ARCHIVIST),
    )
    templates = [
        add_agent(
            controller, NewAgent(display_name=name, role=role, instructions="Read the paper.")
        )
        for name, role in people
    ]
    run = create_experiment(
        controller,
        NewExperiment(
            name="Council fixture",
            task=TaskSpecification(question="What follows from the evidence?"),
            participants=tuple(ParticipantGroup(agent_id=t.id) for t in templates),
            idempotency_key="prepare",
        ),
    )
    exp = controller.ledger.get(run.experiment_id)
    who = {a.display_name.rsplit("-", 1)[0]: a.id for a in exp.agents}
    branch = controller.inspect(run.id).events[0].trajectory_id
    source = import_source(
        controller,
        run.id,
        ImportSource(
            title="Evidence", text="The method works in a small sample.", idempotency_key="source"
        ),
    )

    def append(command):
        return controller.review_command(run.id, branch, command)

    proposal = ("The result is general. " * 33) + "End of argument."
    first = append(
        ReviewClaim(
            author_id=who["Researcher"],
            proposition=proposal,
            idempotency_key="first",
            source_ids=(source.id,),
            citation_spans={source.id: (0, 10)},
        )
    )
    root = next(p for p in first.payload if isinstance(p, Claim))
    other = append(
        ReviewClaim(
            author_id=who["Executor"],
            proposition=proposal,
            idempotency_key="other",
        )
    )
    challenged = append(
        ReviewChallenge(
            claim_id=root.id,
            critic_id=who["First Skeptic"],
            objection="Sampling was limited.",
            idempotency_key="criticism",
        )
    )
    objection = next(p for p in challenged.payload if isinstance(p, Challenge))
    response = append(
        ReviewResponse(
            author_id=who["Researcher"],
            challenge_id=objection.id,
            response="qualify",
            reason="The study cannot establish external validity.",
            revised_proposition="The result holds in a small sample.",
            idempotency_key="response",
        )
    )
    revision = next(p for p in response.payload if isinstance(p, Claim))
    followup = append(
        ReviewChallenge(
            claim_id=revision.id,
            critic_id=who["Second Skeptic"],
            objection="Which sample?",
            idempotency_key="further-criticism",
        )
    )
    append(
        ReviewAssessment(
            claim_id=revision.id,
            author_id=who["First Skeptic"],
            stance="dispute",
            reason="A sampling protocol is missing.",
            idempotency_key="reassess",
        )
    )
    judged = append(
        ReviewDecision(
            reviewer_agent_id=who["Archivist"],
            claim_id=revision.id,
            outcome="qualify",
            reason="Retain only the sample-level result.",
            idempotency_key="judge",
        )
    )
    snap = append(ReviewCheckpoint(idempotency_key="snapshot"))
    checkpoint = next(p for p in snap.payload if isinstance(p, Checkpoint))
    return run, branch, exp, append, first, other, response, followup, judged, checkpoint


def test_projection_keeps_authors_lineages_and_atomic_relationships(controller, dialogue):
    run, branch, exp, _, first, other, response, followup, judged, _ = dialogue
    events = branch_events(controller.ledger.events(run.id), branch)
    feed = CouncilFeed()
    feed.sync(events[:5], exp.agents)
    feed.sync(events, exp.agents)
    replay = CouncilFeed()
    replay.sync(events, exp.agents)
    assert feed.rows == replay.rows
    by_id = {row.event.id: row for row in feed.rows}
    p, q = by_id[first.id].parts[0], by_id[other.id].parts[0]
    assert p.text == q.text
    assert "Researcher-01 (researcher)" == feed.speaker(p)
    assert "Executor-01 (executor)" == feed.speaker(q)
    assert feed.threads(p) != feed.threads(q)
    answer, revision = by_id[response.id].parts
    assert feed.threads(answer) == feed.threads(revision)
    assert "v1" in feed.subject(answer) and "→ criticism" in feed.subject(answer)
    assert "v2, revises v1" in feed.subject(revision)
    assert feed.speaker(answer) == "Researcher-01 (researcher)"
    assert answer.record.critic_id != answer.actor
    assert feed.status(p) == "superseded here"
    assert "Second Skeptic-01" in feed.speaker(by_id[followup.id].parts[0])
    assert "v2" in feed.subject(by_id[judged.id].parts[0])
    focused = feed.filtered(all_activity=False, thread=next(iter(feed.threads(p))), agent=None)
    assert other.id not in {row.event.id for row in focused}
    assert len(focused) == 6
    assert len(feed.filtered(all_activity=False, thread=None, agent=p.actor)) == 2


def test_response_attribution_never_guesses_missing_or_conflicting_provenance(controller, dialogue):
    run, branch, exp, _, _, _, response, *_ = dialogue
    events = branch_events(controller.ledger.events(run.id), branch)
    for actor in (None, response.actor_id):
        replay = CouncilFeed()
        changed = [
            e.model_copy(update={"actor_id": actor}) if e.id == response.id else e for e in events
        ]
        replay.sync(changed, exp.agents)
        row = next(row for row in replay.rows if row.event.id == response.id)
        reply, revision = row.parts
        assert reply.record.critic_id != response.actor_id
        if actor is None:
            assert reply.actor is None
            assert replay.speaker(reply).startswith("Unknown responder")
        else:
            assert reply.actor == revision.actor == actor
            own = replay.filtered(all_activity=False, thread=None, agent=actor)
            assert next(r for r in own if r.event.id == response.id).parts == row.parts
            critic = replay.filtered(all_activity=False, thread=None, agent=reply.record.critic_id)
            assert response.id not in {r.event.id for r in critic}


def test_failure_classifications_and_recorded_disposition(controller, dialogue, monkeypatch):
    from doxa.core.run_overview import failure_disposition, run_overview
    from doxa.core.workbench import DebateExecution, DebateRuntime, debate_failure_reason

    run = dialogue[0]

    async def broken_turn(*args, **kwargs):
        raise ValueError("SECRET-provider-key PRIVATE-CONTENT C:/private/document")

    monkeypatch.setattr(DebateRuntime, "turn", broken_turn)
    with pytest.raises(ValueError, match="SECRET"):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    bundle = controller.inspect(run.id)
    assert bundle.run.status == "failed"
    assert not bundle.accounting
    assert "controller:validation_error" in bundle.model_dump_json()
    assert "SECRET" not in bundle.model_dump_json()
    text = run_overview(controller, run.id)
    assert "Completed work: 0 calls" in text and "new-attempt" in text
    assert "cannot resume in place" in text
    assert "Last committed research contribution" in text
    state_event = bundle.events[-1]
    historical = state_event.model_copy(
        update={
            "payload": tuple(
                p.model_copy(update={"reason_code": "debate_failed_inspect_operations"})
                if isinstance(p, RunState)
                else p
                for p in state_event.payload
            )
        }
    )
    old = bundle.model_copy(update={"events": (*bundle.events[:-1], historical)})
    assert "precise exception was never recorded" in failure_disposition(old)
    for exc in (RuntimeError("SECRET"), KeyError("SECRET"), OSError("SECRET"), Exception("SECRET")):
        assert debate_failure_reason(exc).startswith("controller:")
        assert "SECRET" not in debate_failure_reason(exc)


def test_response_turn_provenance_fallback_and_conflict(controller, dialogue):
    from doxa.core.models import ContextManifest, ResponseNormalization
    from doxa.storage.artifacts import ArtifactStore

    run, branch, exp, _, _, _, response, *_ = dialogue
    author = response.actor_id
    critic = next(p for p in response.payload if isinstance(p, Challenge)).critic_id
    messages = ArtifactStore(controller.settings.data_dir / "artifacts").put(b"[]")
    events = branch_events(controller.ledger.events(run.id), branch)
    for recorded_actor, expected in ((None, author), (critic, None)):
        manifest = ContextManifest(
            id=uuid4(),
            experiment_id=exp.id,
            run_id=run.id,
            trajectory_id=branch,
            provenance="system_inference",
            agent_id=author,
            phase="response-test",
            instruction_version="1",
            task_version=1,
            messages=messages,
            input_token_upper_bound=0,
        )
        audit = ResponseNormalization(
            id=uuid4(),
            experiment_id=exp.id,
            run_id=run.id,
            trajectory_id=branch,
            provenance="system_inference",
            agent_id=author,
            context_id=manifest.id,
            normalizer_version="test",
            input_sha256="0" * 64,
            execution_kind="synthetic",
            disposition="accepted",
            reason_code="validated",
        )
        feed = CouncilFeed()
        changed = [
            e.model_copy(
                update={"actor_id": recorded_actor, "payload": (*e.payload, manifest, audit)}
            )
            if e.id == response.id
            else e
            for e in events
        ]
        feed.sync(changed, exp.agents)
        row = next(row for row in feed.rows if row.event.id == response.id)
        assert row.parts[0].actor == expected
        replay = CouncilFeed()
        replay.sync(changed, exp.agents)
        assert feed.rows == replay.rows


def test_startup_enter_opens_picker_without_focus_patch(
    controller, dialogue, monkeypatch, tmp_path
):
    from doxa.cli.onboarding import ExperimentPicker, GettingStarted

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))

    async def check():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            for _ in range(100):
                await pilot.pause(0.05)
                if (
                    isinstance(app.screen, GettingStarted)
                    and getattr(app.focused, "id", None) == "guide-explore"
                ):
                    break
            assert isinstance(app.screen, GettingStarted)
            assert app.focused.id == "guide-explore"
            await pilot.press("enter")
            for _ in range(100):
                await pilot.pause(0.05)
                if (
                    isinstance(app.screen, ExperimentPicker)
                    and getattr(app.focused, "id", None) == "experiment-list"
                ):
                    break
            assert isinstance(app.screen, ExperimentPicker)
            assert app.focused.id == "experiment-list"
            await pilot.press("escape")
            for _ in range(100):
                await pilot.pause(0.05)
                if (
                    isinstance(app.screen, GettingStarted)
                    and getattr(app.focused, "id", None) == "guide-explore"
                ):
                    break
            assert isinstance(app.screen, GettingStarted)
            assert app.focused.id == "guide-explore"

    asyncio.run(check())


@pytest.mark.parametrize("size", [(80, 24), (160, 45)])
def test_latest_selects_visible_tail_and_inspector_focus_returns(
    controller, dialogue, monkeypatch, tmp_path, size
):
    run, _, _, _, first, _, response, *_ = dialogue
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))

    async def check():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.selected = run.id
        async with app.run_test(size=size) as pilot:
            app.action_live_council()
            view = await ready(pilot, app, response.id)
            await view.select((first.id, False))
            view.query_one(FeedScroll).focus()
            await pilot.press("l")
            last = view.rows[-1]
            assert view.selected == last.key
            await pilot.press("space")
            assert last.key in view.expanded
            await pilot.press("enter")
            assert f"Event #{last.event.sequence}" in view.details_text
            assert app.focused.id == "council-details"
            await pilot.press("ctrl+g")
            await pilot.pause()
            assert isinstance(app.focused, FeedScroll)
            assert not view.has_class("-inspecting")
            assert view.selected == last.key
            assert "Focus: Feed" in view.query_one("#council-status", Static).render().plain
            view.query_one("#council-agent", Select).focus()
            await pilot.press("ctrl+g")
            assert isinstance(app.focused, FeedScroll)
            app.query_one("#runs").focus()
            await pilot.press("ctrl+g")
            assert isinstance(app.focused, FeedScroll)
            await view.select((first.id, False))
            view.query_one("#council-latest", Button).focus()
            await pilot.press("enter")
            assert isinstance(app.focused, FeedScroll)
            assert view.selected == last.key
            await pilot.press("space", "enter")
            assert f"Event #{last.event.sequence}" in view.details_text

    asyncio.run(check())


@pytest.mark.parametrize("size", [(80, 24), (160, 45)])
def test_paced_commits_preserve_reader_and_inspector_then_latest(
    controller, dialogue, monkeypatch, tmp_path, size
):
    run, _, exp, append, first, _, response, *_ = dialogue
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))

    async def check():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.selected = run.id
        async with app.run_test(size=size) as pilot:
            app.action_live_council()
            view = await ready(pilot, app, response.id)
            await view.select((first.id, False))
            stream = view.query_one(FeedScroll)
            stream.focus()
            stream.scroll_home(animate=False, force=True)
            await pilot.pause()
            y, count = stream.scroll_y, len(view.rows)

            async def emit():
                for i in range(3):
                    await asyncio.sleep(0.3)
                    event = append(
                        ReviewClaim(
                            idempotency_key=f"paced-{i}",
                            author_id=exp.agents[0].id,
                            proposition=f"Offline paced contribution {i}; not a model result.",
                        )
                    )
                    app.poll()
                    await ready(pilot, app, event.id, visible=False)

            producer = asyncio.create_task(emit())
            await pilot.press("enter")
            await producer
            assert view.selected == (first.id, False)
            assert len(view.rows) == count + 3 and view.unseen == 3
            assert len({row.key for row in view.rows}) == len(view.rows)
            assert "Event #" + str(first.sequence) in view.details_text
            await pilot.press("ctrl+g")
            await pilot.pause()
            assert abs(stream.scroll_y - y) <= 1
            assert view.unseen == 3
            await pilot.press("l")
            await pilot.pause()
            assert view.selected == view.rows[-1].key and view.unseen == 0
            await pilot.press("enter")
            assert "Offline paced contribution 2" in view.details_text

    asyncio.run(check())


async def ready(pilot, app, event_id, *, visible=True):
    view = app.query_one(LiveCouncil)
    for _ in range(60):
        await pilot.pause(0.05)
        if (
            event_id in {row.event.id for row in view.rows}
            and (not visible or (event_id, False) in view.cards)
            and not app._loading
        ):
            return view
    raise AssertionError("Live Council did not load its committed contributions")


@pytest.mark.parametrize(
    ("size", "theme", "wide"),
    [
        ((80, 24), "textual-dark", False),
        ((120, 40), "textual-light", False),
        ((160, 42), "rose-pine-dawn", True),
    ],
)
def test_view_filters_expand_scroll_replay_and_resize(
    controller,
    dialogue,
    monkeypatch,
    tmp_path,
    size,
    theme,
    wide,
):
    run, branch, _, append, first, other, response, _, _, _ = dialogue
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))

    async def navigate():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.selected = run.id
        app.theme = theme
        async with app.run_test(size=size) as pilot:
            app.action_live_council()
            view = await ready(pilot, app, response.id)
            assert view.has_class("-wide") is wide
            await view.select((first.id, False))
            stream = view.query_one(FeedScroll)
            stream.focus()
            stream.scroll_home(animate=False, force=True)
            await pilot.pause()
            y = stream.scroll_y
            before = view.cards[(first.id, False)]
            assert "… more" in before.render().plain
            await pilot.press("space")
            assert "End of argument." in before.render().plain
            assert (first.id, False) in view.expanded
            y = stream.scroll_y
            await pilot.press("enter")
            assert view.has_class("-inspecting")
            assert "Researcher-01" in view.query_one("#council-details", TextArea).text
            view.query_one("#council-back", Button).focus()
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert not view.has_class("-inspecting")
            assert abs(stream.scroll_y - y) <= 1
            await pilot.press("f")
            assert view.followed and other.id not in {row.event.id for row in view.rows}
            await pilot.press("escape")
            await pilot.pause()
            assert view.selected == (first.id, False) and view.followed is None
            assert abs(stream.scroll_y - y) <= 1
            added = append(
                ReviewClaim(
                    idempotency_key="new",
                    author_id=view.row().parts[0].actor,
                    proposition="New persisted contribution.",
                )
            )
            app.poll()
            await ready(pilot, app, added.id, visible=False)
            assert view.selected == (first.id, False) and view.unseen == 1
            assert len({p.key for p in view.rows}) == len(view.rows)
            stream.focus()
            await pilot.press("l")
            assert view.unseen == 0 and view.end == len(view.rows)
            await pilot.resize_terminal(148, 39)
            # The driver posts Resize before the widget processes its new layout.
            for _ in range(40):
                if view.has_class("-wide"):
                    break
                await pilot.pause(0.05)
            assert view.has_class("-wide")

    asyncio.run(navigate())
    assert controller.inspect(run.id).run.status == "configured"
    assert len([r for r in controller.ledger.records("trajectory") if r.run_id == run.id]) == 1
    assert branch == controller.inspect(run.id).events[0].trajectory_id


def test_checkpoint_preparation_and_explicit_fork(controller, dialogue, monkeypatch, tmp_path):
    run, branch, _, append, first, _, response, _, _, valid = dialogue
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))
    corrupted = append(ReviewCheckpoint(idempotency_key="corrupt-next"))
    invalid = next(p for p in corrupted.payload if isinstance(p, Checkpoint))
    # Two identical snapshots can legitimately share artifact bytes. This second
    # checkpoint is after a prior checkpoint, so its cursor/manifest differ.
    (controller.settings.data_dir / "artifacts" / invalid.manifest.relative_path).unlink()

    async def branch_view():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.selected = run.id
        async with app.run_test(size=(120, 40)) as pilot:
            app.action_live_council()
            view = await ready(pilot, app, response.id)
            await view.select((first.id, False))
            view.prepare_branch()
            for _ in range(50):
                await pilot.pause(0.05)
                if isinstance(app.screen, CouncilBranch) and app.screen.options:
                    break
            screen = app.screen
            assert isinstance(screen, CouncilBranch)
            assert set(screen.options) == {str(valid.id)}
            assert "after selected event" in screen.options[str(valid.id)]
            create = screen.query_one("#council-fork-create", Button)
            assert create.disabled
            screen.query_one("#council-fork-check", Select).value = str(valid.id)
            message = screen.query_one("#council-fork-intervention", Input)
            message.focus()
            await pilot.press("f", "d", "v", "b", "l", "t")
            assert message.value == "fdvblt" and create.disabled
            screen.query_one("#council-fork-confirm", Checkbox).value = True
            await pilot.pause()
            assert not create.disabled
            create.press()
            for _ in range(50):
                await pilot.pause(0.05)
                if app.branch_id and app.branch_id != branch:
                    break
            assert app.branch_id != branch
            assert (
                controller.review_workspace(run.id, app.branch_id).branch.intervention == "fdvblt"
            )

    asyncio.run(branch_view())
    assert not controller.inspect(run.id).accounting
    events = controller.ledger.events(run.id)
    fork = [p for e in events for p in e.payload if isinstance(p, Trajectory) and p.parent_id]
    assert len(fork) == 1 and fork[0].checkpoint_id == valid.id


def test_all_activity_is_recorded_and_large_feed_window_is_bounded(controller, dialogue):
    run, branch, exp, _, first, _, _, _, _, _ = dialogue
    state = RunState(
        id=uuid4(),
        run_id=run.id,
        trajectory_id=branch,
        experiment_id=run.experiment_id,
        provenance=first.provenance,
        status="running",
        reason_code="explicit_start",
    )
    events = [
        Event(
            experiment_id=run.experiment_id,
            run_id=run.id,
            trajectory_id=branch,
            sequence=i + 1,
            type=EventType.RUN_STARTED,
            payload=(state,),
            idempotency_key=f"perf:{i}",
        )
        for i in range(2000)
    ]
    feed = CouncilFeed()
    feed.sync(events, exp.agents)
    assert not feed.filtered(all_activity=False, agent=None, thread=None)
    assert len(feed.filtered(all_activity=True, agent=None, thread=None)) == 2000

    async def verify():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.selected = run.id
        async with app.run_test(size=(150, 40)) as pilot:
            await pilot.pause()
            view = app.query_one(LiveCouncil)
            view.mode = True
            await view.load(controller, branch, events, exp, "running", "fixture")
            assert len(view.cards) == PAGE
            assert "Run: running" in next(iter(view.cards.values())).render().plain
            assert view.query_one("#council-status", Static).render().plain
            assert view.end == 2000

    asyncio.run(verify())
