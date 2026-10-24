import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from doxa.api.app import create_app
from doxa.core.controller import ConfigureRun
from doxa.core.execution import ExecuteTask, Runtime
from doxa.core.models import (
    Agent,
    Claim,
    Evaluation,
    EventType,
    Experiment,
    ProtocolMode,
    Role,
    Verification,
)
from doxa.environments.cache_policy import CacheEnvironment, Candidate


def setup_run(controller, mode=ProtocolMode.SOLO_DIRECT, execution_kind="synthetic"):
    agents = tuple(
        Agent(role=role, instructions="Bounded test instructions", display_name=role.value)
        for role in (Role.EXECUTOR, Role.SKEPTIC, Role.RESEARCHER)
    )
    command = ConfigureRun(
        idempotency_key=str(uuid4()),
        execution_kind=execution_kind,
        mode=mode,
        experiment=Experiment(
            name="Bounded fixture test",
            task_id="cache-policy",
            task_version="1",
            environment_version="1",
            policy_version="1",
            evaluator_version="1",
            agents=agents,
        ),
    )
    return controller.configure_run(command), agents


def execution(initial="stale_on_update", peer="invalidate_all"):
    return ExecuteTask(
        synthetic_answers={
            "executor": Candidate(policy=initial),
            "skeptic": Candidate(policy=peer),
            "researcher": Candidate(policy=peer),
            "defender": Candidate(policy=peer),
        }
    )


@pytest.mark.parametrize("mode", list(ProtocolMode))
def test_four_distinct_protocols_with_real_oracle_and_reload(controller, mode):
    run, agents = setup_run(controller, mode)
    command = execution()
    bundle = asyncio.run(controller.execute_task(run.id, command))
    assert bundle.run.status == "completed"
    records = [r for e in bundle.events for r in e.payload]
    evaluation = next(r for r in records if isinstance(r, Evaluation))
    assert evaluation.metrics["task_success"] == (0 if mode == ProtocolMode.SOLO_DIRECT else 1)
    assert all(r.provenance.value != "model_output" for r in records if isinstance(r, Claim))
    messages = [r for r in records if r.kind == "council_message"]
    assert (
        len(messages)
        == (
            {
                ProtocolMode.SOLO_DIRECT: 1,
                ProtocolMode.SOLO_DELIBERATIVE: 3,
                ProtocolMode.COLLABORATIVE: 2,
                ProtocolMode.ADVERSARIAL: 2,
            }[mode]
        )
    )
    assert sum(e.type == EventType.BRANCH_CREATED for e in bundle.events) == (
        0 if mode == ProtocolMode.SOLO_DIRECT else 1
    )
    assert asyncio.run(controller.execute_task(run.id, command)) == bundle
    controller.initialize()
    assert controller.inspect(run.id) == bundle
    if mode != ProtocolMode.SOLO_DIRECT:
        memories = asyncio.run(
            controller.retrieve_memory(
                run.id, agents[0].id, "cache", conditions=("cache-policy-v1",)
            )
        )
        assert len(memories) == 1


def test_false_criticism_does_not_regress_a_passing_result(controller):
    run, _ = setup_run(controller, ProtocolMode.ADVERSARIAL)
    bundle = asyncio.run(
        controller.execute_task(run.id, execution("invalidate_all", "stale_on_delete"))
    )
    assert not any(e.type == EventType.CLAIM_REVISED for e in bundle.events)
    challenge = next(r for e in bundle.events for r in e.payload if r.kind == "challenge")
    verdict = next(
        r
        for e in bundle.events
        for r in e.payload
        if isinstance(r, Verification) and r.subject_id == challenge.id
    )
    assert verdict.verdict == "invalid"


def test_missing_answer_records_failure_and_cannot_restart(controller):
    run, _ = setup_run(controller)
    with pytest.raises(ValueError, match="missing"):
        asyncio.run(controller.execute_task(run.id, ExecuteTask()))
    assert controller.inspect(run.id).run.status == "failed"
    assert asyncio.run(controller.execute_task(run.id, ExecuteTask())).run.status == "failed"


def test_cancellation_is_durable_and_terminal(controller, monkeypatch):
    run, _ = setup_run(controller)

    async def wait(self, *args):
        await asyncio.sleep(100)

    monkeypatch.setattr(Runtime, "propose", wait)

    async def scenario():
        task = asyncio.create_task(controller.execute_task(run.id, execution()))
        await asyncio.sleep(0.02)
        controller.cancel(run.id)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert controller.inspect(run.id).run.status == "cancelled"
    assert controller.cancel(run.id).run.status == "cancelled"


def test_checkpoint_restore_is_observably_real_and_checks_corruption():
    env = CacheEnvironment(Candidate(policy="invalidate_all"))
    env.read("x")
    snapshot = env.snapshot()
    env.update("x", 10)
    restored = CacheEnvironment.restore(snapshot)
    assert restored.read("x") == 1
    assert restored.snapshot() == snapshot
    with pytest.raises(ValueError):
        CacheEnvironment.restore(snapshot + b"corruption")


def test_new_api_execution_uses_same_controller_records(controller):
    run, _ = setup_run(controller)
    with TestClient(create_app(controller.settings)) as client:
        response = client.post(
            f"/api/runs/{run.id}/execute", json=execution().model_dump(mode="json")
        )
        assert response.status_code == 200, response.text
        assert response.json() == controller.inspect(run.id).model_dump(mode="json")
        assert client.post(f"/api/runs/{run.id}/cancel").status_code == 409


def test_zero_tool_budget_fails_before_verification(controller):
    from doxa.core.models import BudgetPolicy

    agents = (Agent(role=Role.EXECUTOR, instructions="test"),)
    run = controller.configure_run(
        ConfigureRun(
            idempotency_key="zero-tool-budget",
            execution_kind="synthetic",
            experiment=Experiment(
                name="Zero-budget test",
                task_id="cache-policy",
                task_version="1",
                environment_version="1",
                policy_version="1",
                evaluator_version="1",
                agents=agents,
                budget=BudgetPolicy(max_tool_calls=0),
            ),
        )
    )
    with pytest.raises(ValueError, match="tool-call"):
        asyncio.run(controller.execute_task(run.id, execution()))
    assert not any(
        e.type == EventType.VERIFICATION_RECORDED for e in controller.inspect(run.id).events
    )


def test_comparison_checks_versions_and_retains_failed_baseline(controller):
    from doxa.core.comparison import compare

    baseline, _ = setup_run(controller)
    treatment, _ = setup_run(controller, ProtocolMode.ADVERSARIAL)
    asyncio.run(controller.execute_task(baseline.id, execution()))
    asyncio.run(controller.execute_task(treatment.id, execution()))
    comparison = compare(controller, baseline.id, treatment.id)
    assert comparison.baseline_metrics["task_success"] == 0
    assert comparison.treatment_metrics["task_success"] == 1
    assert comparison.removed_commitments


def test_api_rejection_never_echoes_submitted_credentials(controller):
    secret = "moss_" + "x" * 32
    with TestClient(create_app(controller.settings)) as client:
        response = client.post("/api/configuration", json={"api_key": secret})
        assert response.status_code == 422
        assert secret not in response.text
        identity = str(uuid4())
        response = client.post(
            "/api/configuration",
            json={
                "agents": [
                    {
                        "id": identity,
                        "display_name": secret,
                        "agent": {"id": identity, "role": "executor", "instructions": "test"},
                    }
                ]
            },
        )
        assert response.status_code == 409
        assert secret not in response.text
