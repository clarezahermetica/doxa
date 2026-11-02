import asyncio
import json
import time
from uuid import UUID

import httpx
from support_api_server import LocalApiServer
from typer.testing import CliRunner

from doxa.cli.main import app
from doxa.core.models import Claim, Experiment, Trajectory
from doxa.core.text_research import ReviewAnnotation, ReviewCheckpoint
from doxa.core.workbench_demo import demonstrate


def test_completed_run_stream_follows_later_review_and_shutdown(controller):
    result = asyncio.run(demonstrate(controller))
    run_id = UUID(str(result["run_id"]))
    bundle = controller.inspect(run_id)
    branch = next(p.id for e in bundle.events for p in e.payload if isinstance(p, Trajectory))
    server = LocalApiServer(controller.settings.data_dir)
    server.start()
    try:
        with httpx.Client(follow_redirects=True, trust_env=False, timeout=5) as client:
            with client.stream(
                "GET",
                server.url + f"/api/runs/{run_id}/events",
                params={"after": str(bundle.events[-1].id)},
            ) as response:
                assert response.status_code == 200
                event = controller.review_command(
                    run_id, branch, ReviewCheckpoint(idempotency_key="stream-review")
                )
                lines = response.iter_lines()
                assert any(line == f"id: {event.id}" for line in lines)
                started = time.monotonic()
                server.stop()
                assert time.monotonic() - started < 4
                assert not server.thread.is_alive()
    finally:
        server.stop()


def test_pairwise_review_is_human_and_preserves_history(controller):
    from doxa.core.text_research import ReviewFork

    result = asyncio.run(demonstrate(controller))
    run_id = UUID(str(result["run_id"]))
    original = controller.inspect(run_id).events
    branch = next(p.id for e in original for p in e.payload if isinstance(p, Trajectory))
    checkpoint = controller.review_command(
        run_id, branch, ReviewCheckpoint(idempotency_key="pair-checkpoint")
    ).payload[0]
    fork = controller.review_command(
        run_id,
        branch,
        ReviewFork(
            checkpoint_id=checkpoint.id,
            intervention="Human analysis comparison",
            idempotency_key="pair-fork",
        ),
    )
    child = next(p.id for p in fork.payload if isinstance(p, Trajectory))
    event = controller.review_command(
        run_id,
        branch,
        ReviewAnnotation(
            subject_id=branch,
            other_trajectory_id=child,
            preference="tie",
            reviewer_id="fixture-reviewer",
            dimensions={"uncertainty": 3},
            notes="Test-only human rating.",
            idempotency_key="pair",
        ),
    )
    assert event.provenance == "human_annotation"
    assert event.payload[0].preferred_over_id == child
    assert controller.inspect(run_id).events[: len(original)] == original


def test_common_cli_commands_default_to_readable_output_and_offer_json(controller):
    result = asyncio.run(demonstrate(controller))
    runner = CliRunner()
    for command in ("doctor", "agents", "profiles", "runs", "models"):
        arguments = [command, "--data-dir", str(controller.settings.data_dir)]
        readable = runner.invoke(app, arguments)
        assert readable.exit_code == 0, readable.output
        assert readable.output.strip() and not readable.output.lstrip().startswith(("{", "["))
        machine = runner.invoke(app, arguments + ["--json"])
        assert machine.exit_code == 0, machine.output
        json.loads(machine.output)
    assert (
        runner.invoke(
            app, ["inspect", str(result["run_id"]), "--data-dir", str(controller.settings.data_dir)]
        ).exit_code
        == 0
    )
    records = [p for e in controller.inspect(UUID(str(result["run_id"]))).events for p in e.payload]
    assert any(isinstance(p, Experiment) for p in records)
    assert any(isinstance(p, Claim) for p in records)
