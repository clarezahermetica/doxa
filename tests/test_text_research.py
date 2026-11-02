"""Text research acceptance: history and human judgments never impersonate an oracle."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from doxa.api.app import create_app
from doxa.core.models import (
    Annotation,
    Challenge,
    Checkpoint,
    Claim,
    Decision,
    Evidence,
    Provenance,
    Trajectory,
)
from doxa.core.text_research import (
    ReviewAnnotation,
    ReviewChallenge,
    ReviewCheckpoint,
    ReviewClaim,
    ReviewDecision,
    ReviewEvaluate,
    ReviewFork,
    ReviewResponse,
    TextResearch,
)
from doxa.core.workbench import ContextAssembler
from doxa.core.workbench_demo import demonstrate
from doxa.storage.artifacts import ArtifactStore


def fixture(controller):
    result = asyncio.run(demonstrate(controller))
    from uuid import UUID

    run_id = UUID(str(result["run_id"]))
    events = controller.inspect(run_id).events
    root = next(p for e in events for p in e.payload if isinstance(p, Trajectory))
    claim = next(p for e in events for p in e.payload if isinstance(p, Claim))
    return run_id, root.id, claim


def test_challenge_response_adjudication_and_rubric_are_human(controller):
    run, branch, claim = fixture(controller)
    reviewer = TextResearch(controller, run, branch)
    actor = reviewer.experiment.agents[0]
    command = ReviewChallenge(
        claim_id=claim.id,
        critic_id=actor.id,
        objection="Evidence is insufficient.",
        idempotency_key="challenge",
    )
    event = controller.review_command(run, branch, command)
    challenge = next(p for p in event.payload if isinstance(p, Challenge))
    assert controller.review_command(run, branch, command) == event
    reply = controller.review_command(
        run,
        branch,
        ReviewResponse(
            challenge_id=challenge.id,
            author_id=claim.author_id,
            response="accept",
            reason="Human review accepts this objection.",
            revised_proposition="Revised but unverified claim.",
            idempotency_key="respond",
        ),
    )
    revision = next(p for p in reply.payload if isinstance(p, Claim))
    assert revision.revises_id == claim.id and revision.status == "proposed"
    assert controller.ledger.get(claim.id) == claim
    decision = controller.review_command(
        run,
        branch,
        ReviewDecision(
            challenge_id=challenge.id,
            outcome="investigate",
            reason="Needs more evidence.",
            idempotency_key="judge",
        ),
    )
    assert all(p.provenance == Provenance.HUMAN_ANNOTATION for p in decision.payload)
    assert next(p for p in decision.payload if isinstance(p, Decision)).verification_ids == ()
    score = controller.review_command(
        run,
        branch,
        ReviewAnnotation(
            subject_id=revision.id,
            dimensions={"source_traceability": 2, "uncertainty": 4},
            notes="Explicitly human rubric.",
            idempotency_key="rate",
        ),
    )
    annotation = next(
        p
        for p in score.payload
        if isinstance(p, Annotation) and p.rubric_version == "research-review-v1"
    )
    assert annotation.dimensions["uncertainty"] == 4
    assert not controller.review_workspace(run, branch).unresolved_challenges
    with pytest.raises(ValueError, match="already has a response"):
        controller.review_command(
            run,
            branch,
            ReviewResponse(
                challenge_id=challenge.id,
                author_id=claim.author_id,
                response="reject",
                reason="Duplicate response",
                idempotency_key="repeat",
            ),
        )


def test_text_checkpoint_fork_pins_history_and_rejects_future_parent_records(controller):
    run, branch, claim = fixture(controller)
    event = controller.review_command(run, branch, ReviewCheckpoint(idempotency_key="checkpoint"))
    checkpoint = next(p for p in event.payload if isinstance(p, Checkpoint))
    parent_revision = controller.review_command(
        run,
        branch,
        ReviewClaim(
            author_id=claim.author_id,
            proposition="LATER PARENT SECRET",
            revises_id=claim.id,
            idempotency_key="parent-revise",
        ),
    )
    fork = controller.review_command(
        run,
        branch,
        ReviewFork(
            checkpoint_id=checkpoint.id,
            intervention="Explore another interpretation",
            idempotency_key="fork",
        ),
    )
    child = next(p for p in fork.payload if isinstance(p, Trajectory))
    view = controller.review_workspace(run, child.id)
    assert parent_revision.id not in {e.id for e in view.events}
    assert claim.id in {c.id for c in view.current_claims}
    assert (
        controller.review_command(
            run,
            branch,
            ReviewFork(
                checkpoint_id=checkpoint.id,
                intervention="Explore another interpretation",
                idempotency_key="fork",
            ),
        )
        == fork
    )
    child_revision = controller.review_command(
        run,
        child.id,
        ReviewClaim(
            author_id=claim.author_id,
            proposition="Independent child proposal",
            revises_id=claim.id,
            idempotency_key="child-revise",
        ),
    )
    assert child_revision.id not in {e.id for e in controller.review_workspace(run, branch).events}
    with pytest.raises(ValueError, match="not visible"):
        controller.review_command(
            run,
            branch,
            ReviewChallenge(
                claim_id=child_revision.payload[0].id,
                critic_id=claim.author_id,
                objection="Cannot see sibling",
                idempotency_key="leak",
            ),
        )
    actor = TextResearch(controller, run, child.id).experiment.agents[0]
    context = ContextAssembler(controller, run, child.id).assemble(actor, "child-inspection")
    assert b"LATER PARENT SECRET" not in ArtifactStore(
        controller.settings.data_dir / "artifacts"
    ).get(context.messages)
    proof = next(p for p in fork.payload if isinstance(p, Evidence))
    assert proof.source == "text-snapshot-integrity-v1"


def test_corrupt_snapshot_fails_without_creating_a_branch(controller):
    run, branch, _ = fixture(controller)
    event = controller.review_command(run, branch, ReviewCheckpoint(idempotency_key="cp"))
    checkpoint = next(p for p in event.payload if isinstance(p, Checkpoint))
    target = controller.settings.data_dir / "artifacts" / checkpoint.workspace.relative_path
    target.write_bytes(b"corrupt")
    before = len(controller.inspect(run).events)
    with pytest.raises(ValueError, match="integrity"):
        controller.review_command(
            run,
            branch,
            ReviewFork(
                checkpoint_id=checkpoint.id, intervention="No restore", idempotency_key="bad"
            ),
        )
    assert len(controller.inspect(run).events) == before


def test_review_rejects_stale_revision_foreign_run_and_idempotency_conflict(controller):
    run, branch, claim = fixture(controller)
    command = ReviewClaim(
        author_id=claim.author_id,
        proposition="First revision",
        revises_id=claim.id,
        idempotency_key="revision",
    )
    controller.review_command(run, branch, command)
    with pytest.raises(ValueError, match="current claim"):
        controller.review_command(
            run, branch, command.model_copy(update={"idempotency_key": "stale"})
        )
    with pytest.raises(ValueError, match="idempotency"):
        controller.review_command(
            run, branch, command.model_copy(update={"proposition": "Different"})
        )
    other, other_branch, _ = fixture(controller)
    with pytest.raises(ValueError, match="selected run"):
        controller.review_workspace(other, branch)
    with pytest.raises(ValueError, match="visible"):
        controller.review_command(
            other,
            other_branch,
            ReviewChallenge(
                claim_id=claim.id,
                critic_id=claim.author_id,
                objection="Foreign",
                idempotency_key="cross",
            ),
        )


def test_evaluation_is_descriptive_not_a_truth_verdict(controller):
    run, branch, _ = fixture(controller)
    event = controller.review_command(run, branch, ReviewEvaluate(idempotency_key="evaluate"))
    assert event.payload[0].metrics["objective_correctness"] is None
    assert event.payload[0].metrics["known_source_reference_rate"] is None
    assert event.payload[0].denominators["source_references"] == 0


def test_review_http_matches_controller_and_rejects_unknown_operation(controller):
    run, branch, claim = fixture(controller)
    with TestClient(create_app(controller.settings)) as client:
        url = f"/api/workbench/runs/{run}/branches/{branch}"
        assert client.get(url).json() == controller.review_workspace(run, branch).model_dump(
            mode="json"
        )
        response = client.post(
            url + "/commands",
            json={
                "operation": "challenge",
                "claim_id": str(claim.id),
                "critic_id": str(claim.author_id),
                "objection": "Check this assertion",
                "idempotency_key": "http",
            },
        )
        assert response.status_code == 200, response.text
        assert (
            client.post(
                url + "/commands", json={"operation": "certify_truth", "idempotency_key": "invalid"}
            ).status_code
            == 422
        )


def test_terminal_setup_and_review_forms_append_through_controller(controller):
    from textual.widgets import Input, Select, TextArea

    from doxa.cli.console import ResearchConsole

    run, branch, _ = fixture(controller)

    async def interact():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            app.screen.query_one("#setup-name", Input).value = "Terminal researcher"
            app.screen.query_one("#setup-text", TextArea).load_text("Follow source provenance.")
            await pilot.click("#setup-save")
            await pilot.pause()
            assert any(
                a.display_name == "Terminal researcher" for a in controller.configuration().agents
            )
            await pilot.press("n")
            await pilot.pause()
            app.screen.query_one("#setup-name", Input).value = "Terminal experiment"
            app.screen.query_one("#setup-text", TextArea).load_text("What does the paper support?")
            app.screen.query_one("#setup-members", Input).value = "Terminal researcher:2"
            app.screen.query_one("#setup-execution", Select).value = "synthetic"
            await pilot.click("#setup-save")
            await pilot.pause()
            assert len(controller.list_runs()) == 2
            app.selected = run
            app.branch_id = branch
            app.action_review()
            await pilot.pause()
            app.screen.query_one("#review-action", Select).value = "checkpoint"
            await pilot.click("#review-save")
            await pilot.pause()
            assert controller.review_workspace(run, branch).checkpoints
            await pilot.press("q")

    asyncio.run(interact())


def test_terminal_background_worker_survives_viewer_and_records_run(controller):
    from doxa.cli.operations import start_offline
    from doxa.core.models import TaskSpecification
    from doxa.core.workbench import NewExperiment, ParticipantGroup, create_experiment

    fixture(controller)
    template = controller.configuration().agents[0]
    run = create_experiment(
        controller,
        NewExperiment(
            name="Detached worker",
            task=TaskSpecification(question="Inspect evidence"),
            participants=(ParticipantGroup(agent_id=template.id),),
            idempotency_key="detached",
        ),
    )
    process = start_offline(controller, run.id)
    assert process.wait(timeout=30) == 0
    assert controller.inspect(run.id).run.status == "completed"
    with pytest.raises(ValueError):
        start_offline(controller, run.id)
