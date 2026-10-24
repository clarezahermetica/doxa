import asyncio
import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from doxa.api.app import create_app
from doxa.cli.main import app
from doxa.core.controller import ConfigureRun, Controller
from doxa.core.memory_commands import ProposeMemory, TransitionMemory
from doxa.core.models import (
    Agent,
    BudgetPolicy,
    Claim,
    EventType,
    Experiment,
    Provenance,
    ReflectionDecision,
    Role,
    Trajectory,
    Verification,
)
from doxa.core.research import ResearchRuntime
from doxa.core.research_commands import (
    AdjudicateCommand,
    AnnotateCommand,
    ChallengeCommand,
    CheckpointCommand,
    ClaimCommand,
    CloseBranchCommand,
    DecisionCommand,
    EnvironmentCommand,
    EvaluateCommand,
    EvidenceCommand,
    ForkCommand,
    LifecycleCommand,
    ReflectCommand,
    RespondCommand,
    VerifyCommand,
)
from doxa.core.research_demo import experiment
from doxa.environments.cache_policy import CacheEnvironment, Candidate
from doxa.storage.artifacts import ArtifactStore
from doxa.storage.budget import BudgetStore
from doxa.storage.ledger import LedgerConflict
from doxa.systems.memory import eligible
from doxa.systems.research import Signals, commitment_diff, commitments, reflection_rule


def setup(controller, policy="stale_on_update", budget=None):
    agents = tuple(
        Agent(role=r, instructions="Synthetic test participant")
        for r in (Role.EXECUTOR, Role.SKEPTIC, Role.RESEARCHER)
    )
    run = controller.configure_run(
        ConfigureRun(
            idempotency_key=str(uuid4()),
            execution_kind="synthetic",
            experiment=Experiment(
                name="Research test",
                task_id="cache-policy",
                task_version="1",
                environment_version="1",
                policy_version="adaptive-v1",
                evaluator_version="research-gym-v1",
                agents=agents,
                budget=budget or BudgetPolicy(max_tool_calls=100, timeout_seconds=300),
            ),
        )
    )
    root = next(
        r.id
        for e in controller.inspect(run.id).events
        for r in e.payload
        if isinstance(r, Trajectory)
    )

    def apply(command, branch=root):
        return controller.research_command(run.id, branch, command)

    apply(LifecycleCommand(idempotency_key="start", status="running", reason_code="test"))
    candidate = Candidate(policy=policy)
    apply(EnvironmentCommand(idempotency_key="init", action="initialize", candidate=candidate))
    claim = apply(
        ClaimCommand(
            idempotency_key="claim", author_id=agents[0].id, proposition=candidate.model_dump_json()
        )
    ).payload[0]
    return run, root, agents, claim, apply


def checkpoint(apply):
    return apply(CheckpointCommand(idempotency_key="checkpoint")).payload[0]


def fork(apply, point, name):
    event = apply(ForkCommand(idempotency_key=name, checkpoint_id=point.id, intervention=name))
    return next(r.id for r in event.payload if isinstance(r, Trajectory))


def test_epistemic_versions_dependency_impact_and_restart(controller):
    run, root, agents, v1, apply = setup(controller)
    dependent = apply(
        ClaimCommand(
            idempotency_key="dependent",
            author_id=agents[0].id,
            proposition="Rely on the initial policy",
            dependency_ids=(v1.id,),
        )
    )
    decision = apply(
        DecisionCommand(
            idempotency_key="decision",
            claim_id=dependent.payload[0].id,
            dependency_ids=(dependent.payload[0].id,),
            reason="Use policy",
        )
    )
    contrary = apply(
        EvidenceCommand(
            idempotency_key="contrary",
            source="synthetic-observation",
            description="An objection, not certified truth",
        )
    ).payload[0]
    v2 = apply(
        ClaimCommand(
            idempotency_key="revise",
            author_id=agents[0].id,
            proposition=v1.proposition,
            revises_id=v1.id,
            status="retracted",
            contradicting_evidence_ids=(contrary.id,),
        )
    ).payload[0]
    assert controller.ledger.get(v1.id) == v1
    assert v2.commitment_id == v1.commitment_id
    assert decision.payload[0].id in v2.reconsider_ids
    assert dependent.payload[0].id in v2.reconsider_ids
    assert controller.ledger.get(dependent.payload[0].id).status == "proposed"
    reloaded = Controller(controller.settings)
    assert reloaded.inspect(run.id) == controller.inspect(run.id)
    assert {c.id for c in commitments(reloaded.ledger.events(run.id), root)} == {
        dependent.payload[0].id,
        v2.id,
    }
    with pytest.raises(ValueError, match="stale"):
        apply(
            ClaimCommand(
                idempotency_key="stale",
                author_id=agents[0].id,
                proposition="stale write",
                revises_id=v1.id,
            )
        )


def test_conflicting_branches_pin_ancestor_prefix_and_diff(controller):
    run, root, agents, claim, apply = setup(controller)
    point = checkpoint(apply)
    a, b = fork(apply, point, "a"), fork(apply, point, "b")
    va = apply(
        ClaimCommand(
            idempotency_key="revise", author_id=agents[0].id, proposition="A", revises_id=claim.id
        ),
        a,
    ).payload[0]
    vb = apply(
        ClaimCommand(
            idempotency_key="revise", author_id=agents[0].id, proposition="B", revises_id=claim.id
        ),
        b,
    ).payload[0]
    apply(
        ClaimCommand(
            idempotency_key="parent-future",
            author_id=agents[0].id,
            proposition="Future parent position",
        )
    )
    events = Controller(controller.settings).ledger.events(run.id)
    assert [c.proposition for c in commitments(events, a)] == ["A"]
    assert [c.proposition for c in commitments(events, b)] == ["B"]
    diff = commitment_diff(events, a, b)
    assert diff[0].before_id == va.id and diff[0].after_id == vb.id
    assert diff[0].author_id == agents[0].id
    with pytest.raises(ValueError, match="visible"):
        apply(VerifyCommand(idempotency_key="sibling-read", claim_id=va.id), b)


def test_actual_state_restore_independent_continuations_and_parent_preservation(controller):
    run, root, _, _, apply = setup(controller)
    apply(EnvironmentCommand(idempotency_key="read", action="read"))
    point = checkpoint(apply)
    apply(EnvironmentCommand(idempotency_key="change", action="update", value=9))
    before = tuple(controller.ledger.events(run.id))
    a, b = fork(apply, point, "a"), fork(apply, point, "b")
    assert ResearchRuntime(controller, run.id, a).state().state.values["x"] == 1
    apply(EnvironmentCommand(idempotency_key="new", action="update", value=3), a)
    apply(EnvironmentCommand(idempotency_key="new", action="delete"), b)
    reloaded = Controller(controller.settings)
    assert ResearchRuntime(reloaded, run.id, root).state().state.values["x"] == 9
    assert ResearchRuntime(reloaded, run.id, a).state().state.values["x"] == 3
    assert "x" not in ResearchRuntime(reloaded, run.id, b).state().state.values
    assert tuple(reloaded.ledger.events(run.id)[: len(before)]) == before
    assert sum(e.type == EventType.CHECKPOINT_RESTORED for e in reloaded.ledger.events(run.id)) == 2


@pytest.mark.parametrize("damage", ["corrupt", "missing", "incomplete"])
def test_failed_restore_never_creates_child_and_failure_is_inspectable(
    controller, monkeypatch, damage
):
    run, _, _, _, apply = setup(controller)
    point = checkpoint(apply)
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    if damage in {"corrupt", "missing"}:
        path = store.root / point.workspace.relative_path
        if damage == "corrupt":
            path.write_bytes(b"bad hash")
        else:
            path.unlink()
    else:
        original = CacheEnvironment.restore

        def incomplete(data):
            result = original(data)
            result.update("x", 100)
            return result

        monkeypatch.setattr(CacheEnvironment, "restore", incomplete)
    with pytest.raises((ValueError, OSError)):
        fork(apply, point, damage)
    events = controller.ledger.events(run.id)
    assert not any(e.type == EventType.BRANCH_CREATED for e in events)
    assert events[-1].payload[0].source == "research-command-rejected"


@pytest.mark.parametrize(
    "policy,cases,verdict,response",
    [
        ("stale_on_update", ("update",), "valid", "accept"),
        ("invalidate_all", ("update",), "invalid", "reject"),
        ("stale_on_update", ("update", "delete"), "partially_valid", "qualify"),
        ("stale_on_update", ("delete",), "invalid", "reject"),
        ("stale_on_update", (), "unverified", "defer"),
    ],
)
def test_criticism_classes_and_separate_response_provenance(
    controller, policy, cases, verdict, response
):
    run, _, agents, original, apply = setup(controller, policy)
    challenge = apply(
        ChallengeCommand(
            idempotency_key="challenge",
            claim_id=original.id,
            critic_id=agents[1].id,
            objection="Persuasive test objection",
            alleged_cases=cases,
            confidence=0.99,
            proposed_revision=Candidate(policy="invalidate_all"),
        )
    ).payload[0]
    adjudication = apply(AdjudicateCommand(idempotency_key="judge", challenge_id=challenge.id))
    validation = next(r for r in adjudication.payload if isinstance(r, Verification))
    assert validation.verdict == verdict
    event = apply(
        RespondCommand(
            idempotency_key="response",
            author_id=agents[0].id,
            challenge_id=challenge.id,
            response=response,
        )
    )
    assert event.actor_id == agents[0].id
    assert event.payload[0].responds_to_id == challenge.id
    assert challenge.provenance == Provenance.IMPORTED_SOURCE
    assert validation.provenance == Provenance.DETERMINISTIC_VERIFIER
    assert controller.ledger.get(original.id) == original
    revisions = [r for r in event.payload if isinstance(r, Claim)]
    assert len(revisions) == (1 if response in {"accept", "qualify"} else 0)
    if response == "qualify":
        assert revisions[0].status == "qualified"
    if response == "reject" and policy == "stale_on_update":
        assert not any(
            isinstance(r, Claim) and r.status == "supported"
            for e in controller.ledger.events(run.id)
            for r in e.payload
        )
    if verdict != "valid":
        with pytest.raises(ValueError):
            apply(
                RespondCommand(
                    idempotency_key="unsafe-accept",
                    author_id=agents[0].id,
                    challenge_id=challenge.id,
                    response="accept",
                )
            )


def test_task_success_requires_actual_deployed_policy(controller):
    _, _, agents, _, apply = setup(controller)
    correct = apply(
        ClaimCommand(
            idempotency_key="assert-correct",
            author_id=agents[0].id,
            proposition=Candidate(policy="invalidate_all").model_dump_json(),
        )
    )
    with pytest.raises(ValueError, match="deployed"):
        apply(VerifyCommand(idempotency_key="verify", claim_id=correct.payload[0].id))


def test_annotation_references_and_objective_results_are_separate(controller, tmp_path):
    result = experiment(controller)
    run_id = UUID(result["run_id"])
    bundle = Controller(controller.settings).inspect(run_id)
    annotations = [r for e in bundle.events for r in e.payload if r.kind == "annotation"]
    assert annotations[0].preference == "A"
    assert annotations[0].rubric_version == "trajectory-quality-v1"
    assert annotations[0].provenance == Provenance.HUMAN_ANNOTATION
    assert result["metrics"][0]["metrics"]["recovery"] == 1
    assert result["metrics"][0]["denominators"]["recovery"] == 1
    assert result["metrics"][0]["metrics"]["regression"] is None
    assert result["metrics"][1]["metrics"]["task_success"] == 0
    assert all(
        m["usage"]["input_tokens"] is None and m["usage"]["billed_usd"] is None
        for m in result["metrics"]
    )
    assert result["retrieved_before_revocation"] and not result["retrieved_after_revocation"]
    output = tmp_path / "export.jsonl"
    response = CliRunner().invoke(
        app,
        ["export-jsonl", str(run_id), str(output), "--data-dir", str(controller.settings.data_dir)],
    )
    assert response.exit_code == 0, response.output
    exported = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(exported) == len(bundle.events) + 1
    assert any(
        r["kind"] == "trajectory" and r["parent_id"] for e in exported[1:] for r in e["payload"]
    )
    assert any(e["type"] == "HUMAN_ANNOTATION_ADDED" for e in exported[1:])


def test_private_shared_scoped_narrowing_and_abandoned_branch_memory(controller):
    run, root, agents, _, apply = setup(controller)
    point = checkpoint(apply)
    child = fork(apply, point, "abandoned")
    proposal = controller.propose_memory(
        run.id,
        ProposeMemory(
            idempotency_key="broad",
            text="Every cache is always safe",
            owner_agent_id=agents[0].id,
            category="reflective",
            trajectory_id=child,
        ),
    )
    assert controller.validate_memory(run.id, proposal.id).verdict == "unverified"
    narrow = controller.propose_memory(
        run.id,
        ProposeMemory(
            idempotency_key="narrow",
            text="Invalidate cache entries after update and delete.",
            owner_agent_id=agents[0].id,
            trajectory_id=child,
            revises_id=proposal.id,
            category="procedural",
            eligibility=("cache-policy-v1",),
            branch_ids=(child,),
        ),
    )
    check = controller.validate_memory(run.id, narrow.id)
    approved = controller.transition_memory(
        run.id,
        narrow.id,
        TransitionMemory(
            idempotency_key="approve",
            trust="approved",
            validation_ids=(check.id,),
        ),
    )
    conditions = ("cache-policy-v1",)
    reloaded = Controller(controller.settings)
    assert eligible(reloaded.ledger, run.id, agents[0].id, conditions, child) == (approved,)
    assert not eligible(reloaded.ledger, run.id, agents[1].id, conditions, child)
    assert not eligible(reloaded.ledger, run.id, agents[0].id, conditions, root)
    assert approved.trajectory_id == child and approved.memory_id == proposal.memory_id
    controller.transition_memory(
        run.id, approved.id, TransitionMemory(idempotency_key="revoke", trust="revoked")
    )
    assert not eligible(reloaded.ledger, run.id, agents[0].id, conditions, child)


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({}, "continue"),
        ({"failed": True}, "verify"),
        ({"success": True}, "stop"),
        ({"unsupported_criticism": True}, "continue"),
        ({"regression": True, "checkpoint": True}, "rollback"),
        ({"regression": True}, "continue"),
        ({"exhausted": True, "success": True}, "stop"),
        ({"uncertainty": True}, "retrieve"),
        ({"validated_criticism": True}, "reflect"),
        ({"repeated_failures": 3}, "escalate"),
        ({"contradiction": True}, "verify"),
    ],
)
def test_ordered_reflection_rules(fields, expected):
    assert reflection_rule(Signals(signal="test", **fields), (), 2)[0] == expected


def test_durable_reflection_loop_and_resource_stop(controller):
    run, root, _, claim, apply = setup(controller)
    trigger = apply(VerifyCommand(idempotency_key="test", claim_id=claim.id))
    first = apply(ReflectCommand(idempotency_key="first", trigger_event_id=trigger.id))
    assert first.payload[0].action == "verify"
    again = apply(ReflectCommand(idempotency_key="second", trigger_event_id=trigger.id))
    assert again.payload[0].action == "escalate"
    assert Controller(controller.settings).inspect(run.id).events[-1] == again
    budget = BudgetStore(controller.settings.database_path)
    budget.reserve(run.id, uuid4(), Decimal("1"))
    stop = apply(ReflectCommand(idempotency_key="budget", trigger_event_id=trigger.id)).payload[0]
    assert stop.action == "stop" and stop.budget_before["run_usd_remaining"] == 0


def test_reflection_intervention_cap_and_critique(controller):
    run, root, _, _, _ = setup(controller)
    prior = tuple(
        ReflectionDecision(
            experiment_id=run.experiment_id,
            run_id=run.id,
            trajectory_id=root,
            provenance=Provenance.SYSTEM_INFERENCE,
            action="reflect",
            trigger_event_id=uuid4(),
            signal=str(i),
            reason_code="test",
            policy_version="adaptive-v1",
        )
        for i in range(2)
    )
    assert (
        reflection_rule(Signals(signal="new", validated_criticism=True), prior, 2)[0] == "escalate"
    )
    verified = prior[0].model_copy(update={"action": "verify"})
    assert reflection_rule(Signals(signal="new", failed=True), (verified,), 2)[0] == "critique"


def test_idempotency_atomic_batch_and_stale_cursor(controller):
    run, root, agents, _, apply = setup(controller)
    command = ClaimCommand(idempotency_key="once", author_id=agents[0].id, proposition="Once")
    event = apply(command)
    assert apply(command) == event
    with pytest.raises(LedgerConflict):
        apply(command.model_copy(update={"proposition": "Changed"}))
    runtime = ResearchRuntime(controller, run.id, root)
    runtime.namespace, runtime.key, runtime.digest = uuid4(), "stale-cursor", "test"
    stale = runtime.event(EventType.OBSERVATION_RECEIVED, ())
    apply(EvidenceCommand(idempotency_key="advance", description="advance", source="test"))
    with pytest.raises(LedgerConflict, match="changed"):
        controller.ledger.append(stale)
    count = len(controller.ledger.events(run.id))
    current = controller.ledger.events(run.id)[-1]
    first = current.model_copy(
        update={
            "id": uuid4(),
            "idempotency_key": "batch-first",
            "payload": (),
            "expected_cursor": None,
        }
    )
    bad = first.model_copy(
        update={"id": uuid4(), "idempotency_key": "batch-bad", "parent_event_ids": (uuid4(),)}
    )
    with pytest.raises(LedgerConflict):
        controller.ledger.append_batch((first, bad))
    assert len(controller.ledger.events(run.id)) == count


def test_http_and_cli_use_same_research_command_ledger(controller, tmp_path):
    run, root, agents, _, _ = setup(controller)
    command = ClaimCommand(
        idempotency_key="api-cli", author_id=agents[0].id, proposition="Persisted"
    )
    with TestClient(create_app(controller.settings)) as client:
        response = client.post(
            f"/api/runs/{run.id}/branches/{root}/commands", json=command.model_dump(mode="json")
        )
        assert response.status_code == 200, response.text
    path = tmp_path / "command.json"
    path.write_text(command.model_dump_json())
    result = CliRunner().invoke(
        app,
        [
            "research-command",
            str(run.id),
            str(root),
            str(path),
            "--data-dir",
            str(controller.settings.data_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == response.json()


def test_comparison_honors_restore_and_failed_outcomes(controller):
    from doxa.core.comparison import compare_branches

    result = experiment(controller)
    run = UUID(result["run_id"])
    a, b = map(UUID, result["children"])
    comparison = compare_branches(Controller(controller.settings), run, a, b)
    assert comparison.starting_state_equivalent
    assert comparison.final_state_hashes[0] != comparison.final_state_hashes[1]
    assert comparison.evaluations[0].metrics["task_success"] == 1
    assert comparison.evaluations[1].metrics["task_success"] == 0
    assert comparison.configuration.policy_version == "adaptive-v1"


def test_abandoned_branch_preserves_lessons_but_disallows_actions(controller):
    run, root, agents, _, apply = setup(controller)
    child = fork(apply, checkpoint(apply), "abandoned")
    apply(
        CloseBranchCommand(
            idempotency_key="abandon", status="abandoned", reason_code="unsupported_continuation"
        ),
        child,
    )
    with pytest.raises(ValueError, match="abandoned"):
        apply(
            EnvironmentCommand(idempotency_key="write-after-close", action="update", value=9), child
        )
    memory = controller.propose_memory(
        run.id,
        ProposeMemory(
            idempotency_key="abandoned-lesson",
            text="Candidate from abandoned attempt",
            owner_agent_id=agents[0].id,
            trajectory_id=child,
        ),
    )
    assert memory.trajectory_id == child and memory.trust == "quarantined"
    assert Controller(controller.settings).ledger.get(memory.id) == memory


def test_historical_replay_forbids_fresh_actions(controller):
    _, _, _, _, apply = setup(controller)
    point = checkpoint(apply)
    event = apply(
        ForkCommand(
            idempotency_key="replay",
            checkpoint_id=point.id,
            intervention="Read historical state",
            continuation="historical_replay",
        )
    )
    child = next(r.id for r in event.payload if isinstance(r, Trajectory))
    with pytest.raises(ValueError, match="read-only"):
        apply(EnvironmentCommand(idempotency_key="mutate-replay", action="delete"), child)


def test_gym_regression_and_invalid_annotations(controller):
    run, root, agents, claim, apply = setup(controller, "invalidate_all")
    apply(VerifyCommand(idempotency_key="initial", claim_id=claim.id))
    bad = Candidate(policy="stale_on_delete")
    apply(EnvironmentCommand(idempotency_key="regress", action="select_policy", candidate=bad))
    changed = apply(
        ClaimCommand(
            idempotency_key="new-claim",
            author_id=agents[0].id,
            proposition=bad.model_dump_json(),
            revises_id=claim.id,
        )
    ).payload[0]
    apply(VerifyCommand(idempotency_key="final", claim_id=changed.id))
    evaluation = apply(EvaluateCommand(idempotency_key="gym")).payload[0]
    assert evaluation.metrics["regression"] == 1
    assert evaluation.denominators["regression"] == 1
    assert evaluation.metrics["recovery"] is None and evaluation.denominators["recovery"] == 0
    assert evaluation.metrics["unjustified_revision"] == 1
    assert evaluation.usage.billed_usd is None
    with pytest.raises((ValueError, KeyError)):
        apply(
            AnnotateCommand(
                idempotency_key="fake-target",
                reviewer_id="test",
                preference="B",
                other_trajectory_id=uuid4(),
            )
        )
    with pytest.raises(ValueError):
        apply(
            AnnotateCommand(
                idempotency_key="bad-rating", reviewer_id="test", dimensions={"overall": 99}
            )
        )


def test_independent_verifier_port_produces_actual_evidence(controller):
    from doxa.environments.cache_policy import CacheFixture
    from doxa.environments.cache_verifier import CacheIndependentVerifier
    from doxa.environments.contracts import IndependentVerifier, TaskSpec

    run, root, _, claim, _ = setup(controller)
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    concrete = CacheIndependentVerifier(store, run.experiment_id, run.id, root, claim.id)
    verifier: IndependentVerifier = concrete
    task = TaskSpec(
        id="cache-policy",
        version="1",
        environment="1",
        fixture=store.put(CacheFixture().model_dump_json().encode()),
    )
    verdict = asyncio.run(verifier.verify(task, store.put(claim.proposition.encode())))
    assert verdict.verdict == "invalid" and verdict.evidence_ids == (concrete.evidence.id,)
    assert "false" in store.get(concrete.evidence.artifacts[0]).decode()


def test_solo_deliberative_four_contexts_still_require_independent_tests(controller):
    from test_runtime_stage import execution, setup_run

    from doxa.core.models import ProtocolMode

    run, _ = setup_run(controller, ProtocolMode.SOLO_DELIBERATIVE)
    command = execution().model_copy(
        update={
            "synthetic_answers": {
                **execution().synthetic_answers,
                "adjudicator": Candidate(policy="stale_on_delete"),
            }
        }
    )
    bundle = asyncio.run(controller.execute_task(run.id, command))
    messages = [r for e in bundle.events for r in e.payload if r.kind == "council_message"]
    assert len(messages) == 4
    assert not any(e.type == EventType.CLAIM_REVISED for e in bundle.events)
    score = next(r for e in bundle.events for r in e.payload if r.kind == "evaluation")
    assert score.metrics["task_success"] == 0


@pytest.mark.parametrize("corrupt", [False, True])
def test_controller_rollback_requires_actual_checkpoint_integrity(controller, corrupt):
    run, root, agents, claim, apply = setup(controller, "invalidate_all")
    apply(VerifyCommand(idempotency_key="passing", claim_id=claim.id))
    point = checkpoint(apply)
    bad = Candidate(policy="stale_on_delete")
    apply(EnvironmentCommand(idempotency_key="change", action="select_policy", candidate=bad))
    new = apply(
        ClaimCommand(
            idempotency_key="wrong", author_id=agents[0].id, proposition=bad.model_dump_json()
        )
    ).payload[0]
    failure = apply(VerifyCommand(idempotency_key="failure", claim_id=new.id))
    if corrupt:
        store = ArtifactStore(controller.settings.data_dir / "artifacts")
        (store.root / point.workspace.relative_path).write_bytes(b"broken checkpoint")
    decision = apply(ReflectCommand(idempotency_key="policy", trigger_event_id=failure.id)).payload[
        0
    ]
    assert decision.action == ("verify" if corrupt else "rollback")


def test_decision_challenges_keep_exact_version_and_conflicting_objections(controller):
    _, _, agents, claim, apply = setup(controller)
    decision = apply(
        DecisionCommand(idempotency_key="decision", claim_id=claim.id, reason="Use initial policy")
    ).payload[0]
    targets = []
    for name, cases in (("true", ("update",)), ("false", ("delete",))):
        challenge = apply(
            ChallengeCommand(
                idempotency_key=name,
                claim_id=claim.id,
                target_decision_id=decision.id,
                critic_id=agents[1].id,
                alleged_cases=cases,
                objection=name,
            )
        ).payload[0]
        verdict = apply(
            AdjudicateCommand(idempotency_key="judge-" + name, challenge_id=challenge.id)
        )
        targets.append((challenge, verdict.payload[-1]))
    assert [v.verdict for _, v in targets] == ["valid", "invalid"]
    assert all(c.claim_id == claim.id and c.target_decision_id == decision.id for c, _ in targets)
