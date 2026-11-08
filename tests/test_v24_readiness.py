"""Bounded offline research criteria, citation checks and terminal packaging contracts."""

import asyncio
import json
from uuid import uuid4

import pytest
from test_investigation_protocol import prepare

from doxa.core.models import Claim, Evaluation, Provenance, ResearchOutcome, Role
from doxa.core.research_criteria import REVIEW_DISPUTES, assess_cycle, validate_criteria
from doxa.core.workbench import (
    DebateExecution,
    DebateRuntime,
    ImportSource,
    NewExperiment,
    ParticipantGroup,
    create_experiment,
    import_source,
)


def strict_run(controller, rounds=2, calls=12, plateau=2):
    base = prepare(controller, calls=calls, rounds=rounds)
    experiment = controller.ledger.get(base.experiment_id)
    task = experiment.task.model_copy(
        update={
            "evaluation_criteria": (*experiment.task.evaluation_criteria, REVIEW_DISPUTES),
            "plateau_cycles": plateau,
        }
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="OFFLINE dispute review fixture",
            task=task,
            participants=tuple(ParticipantGroup(agent_id=a.template_id) for a in experiment.agents),
            budget=experiment.budget,
            idempotency_key=str(uuid4()),
        ),
    )
    import_source(
        controller,
        run.id,
        ImportSource(
            title="Offline source",
            text="This fixture tests controller behavior, not research truth.",
            idempotency_key="source",
        ),
    )
    return run


def test_disputed_reassessment_cannot_be_closed_by_retain_judgment(controller):
    run = strict_run(controller, calls=10)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def disputed(actor, phase, manifest):
        body = json.loads(default(actor, phase, manifest))
        if phase.endswith("stage:reassessment"):
            body["research_action"]["stance"] = "dispute"
        if actor.role == Role.ARCHIVIST:
            body["research_action"]["outcome"] = "retain"
        return json.dumps(body)

    runtime.synthetic_answer = disputed
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    outcome = next(p for p in records if isinstance(p, ResearchOutcome))
    assert outcome.execution_status == "stopped" and outcome.epistemic_outcome == "unresolved"
    assert outcome.cycles == 2 and outcome.turns == 7
    checks = [
        p
        for p in records
        if isinstance(p, Evaluation) and p.evaluator_version == "investigation-criteria-v1"
    ]
    assert len(checks) == 2 and all(p.metrics["pending_reviewers"] == 1 for p in checks)
    assert all(p.metrics["objective_correctness"] is None for p in checks)


def test_accepted_claim_can_conclude_without_forced_argument(controller):
    run = strict_run(controller, calls=3)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def accepted(actor, phase, manifest):
        body = json.loads(default(actor, phase, manifest))
        action = body["research_action"]
        if action["operation"] == "challenge":
            body["research_action"] = {
                "operation": "assess",
                "claim_id": action["claim_id"],
                "stance": "accept",
                "reason": "Offline acceptance fixture",
                "source_ids": action["source_ids"],
            }
        if actor.role == Role.ARCHIVIST:
            body["research_action"]["outcome"] = "retain"
        return json.dumps(body)

    runtime.synthetic_answer = accepted
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    outcome = next(p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome))
    assert outcome.turns == 3 and outcome.epistemic_outcome == "supported"
    assert outcome.judgment_basis == "unverified_model_judgments"


def test_criterion_rejected_for_fixed_rounds_without_writing(controller):
    run = prepare(controller)
    experiment = controller.ledger.get(run.experiment_id)
    before = len(controller.list_runs())
    task = experiment.task.model_copy(
        update={"research_protocol": "fixed_rounds", "evaluation_criteria": (REVIEW_DISPUTES,)}
    )
    with pytest.raises(ValueError, match="Investigation"):
        validate_criteria(task)
    with pytest.raises(ValueError, match="Investigation"):
        create_experiment(
            controller,
            NewExperiment(
                name="Invalid criterion",
                task=task,
                participants=tuple(
                    ParticipantGroup(agent_id=a.template_id) for a in experiment.agents
                ),
                idempotency_key=str(uuid4()),
            ),
        )
    assert len(controller.list_runs()) == before


def test_old_claim_judgment_cannot_resolve_current_revision(controller):
    from doxa.core.investigation import claim_threads

    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    asyncio.run(runtime.execute_debate(DebateExecution()))
    thread = claim_threads(controller, run.id, runtime.branch)[0]
    assert len(thread.versions) == 2
    thread.decisions = [
        d.model_copy(update={"claim_id": thread.versions[0].id}) for d in thread.decisions
    ]
    actors = runtime.experiment.agents
    records = [p for e in controller.ledger.events(run.id) for p in e.payload]
    result = assess_cycle(
        [thread],
        records,
        {a.id for a in actors if a.role == Role.SKEPTIC},
        {a.id for a in actors if a.role == Role.ARCHIVIST},
        True,
    )
    assert result.missing_judgments == 1 and result.conclusion is None


@pytest.mark.parametrize(
    "location,expected",
    [
        (None, "unlocated_links"),
        ("unicode_characters:0:5", "located_spans"),
        ("unicode_characters:0:999999", "invalid_spans"),
        ("page 999", "invalid_spans"),
    ],
)
def test_citation_span_validation_is_not_entailment(controller, location, expected):
    from doxa.core.citation_audit import citation_counts
    from doxa.core.models import Evidence, SourceDocument

    run = prepare(controller)
    bundle = controller.inspect(run.id)
    records = {p.id: p for e in bundle.events for p in e.payload}
    source = next(p for p in records.values() if isinstance(p, SourceDocument))
    scope = dict(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=bundle.events[-1].trajectory_id,
        provenance=Provenance.IMPORTED_SOURCE,
    )
    evidence = Evidence(
        **scope,
        description="Fixture citation",
        source=f"source-document:{source.id}",
        artifacts=(source.content,),
        source_location=location,
    )
    claim = Claim(
        **scope,
        proposition="This false claim also has a valid source link.",
        evidence_ids=(evidence.id,),
    )
    records[evidence.id] = evidence
    counts = citation_counts(controller, (claim,), records)
    assert counts[expected] == 1 and counts["document_links"] == 1


def test_evaluation_records_citation_denominators_and_keeps_truth_unknown(controller):
    run = prepare(controller)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    evaluation = next(
        p
        for e in reversed(bundle.events)
        for p in e.payload
        if isinstance(p, Evaluation) and p.evaluator_version == "text-descriptive-v3"
    )
    assert evaluation.denominators["document_citation_links"] > 0
    assert evaluation.metrics["citation_unlocated_links"] > 0
    assert evaluation.metrics["citation_entailment"] is None
    assert evaluation.metrics["objective_correctness"] is None


@pytest.mark.parametrize("failure", [TimeoutError, asyncio.CancelledError])
def test_strict_run_interruption_never_reports_supported(controller, failure):
    run = strict_run(controller)
    runtime = DebateRuntime(controller, run.id)

    async def interrupted(*args, **kwargs):
        raise failure()

    runtime.turn = interrupted
    if failure is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(runtime.execute_debate(DebateExecution()))
    else:
        asyncio.run(runtime.execute_debate(DebateExecution()))
    outcomes = [
        p
        for e in controller.inspect(run.id).events
        for p in e.payload
        if isinstance(p, ResearchOutcome)
    ]
    assert len(outcomes) == 1 and outcomes[0].epistemic_outcome == "unresolved"
    assert outcomes[0].execution_status == (
        "interrupted" if failure is asyncio.CancelledError else "stopped"
    )


def test_strict_run_hard_call_limit_still_wins(controller):
    run = strict_run(controller, calls=3)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    outcome = next(p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome))
    assert outcome.execution_status == "stopped" and outcome.reason == "model_call_limit"
    assert outcome.turns == 3 and outcome.epistemic_outcome == "unresolved"


@pytest.mark.parametrize("strict", [False, True])
def test_conflicting_archivists_never_establish_truth(controller, strict):
    from doxa.core.investigation import claim_threads

    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    thread = claim_threads(controller, run.id, runtime.branch)[0]
    first, second = uuid4(), uuid4()
    decision = thread.decisions[-1]
    thread.decisions = [
        decision.model_copy(update={"adjudicator_id": first, "outcome": "retain"}),
        decision.model_copy(update={"id": uuid4(), "adjudicator_id": second, "outcome": "reject"}),
    ]
    result = assess_cycle(
        [thread], [p for e in bundle.events for p in e.payload], set(), {first, second}, strict
    )
    assert result.reason == "conflicting_archivist_judgments"
    assert result.conclusion is None if strict else result.conclusion[1] == "unresolved"


def test_new_criticism_invalidates_older_acceptance(controller):
    from doxa.core.investigation import claim_threads
    from doxa.core.models import Challenge

    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    thread = claim_threads(controller, run.id, runtime.branch)[0]
    reviewer = next(a.id for a in runtime.experiment.agents if a.role == Role.SKEPTIC)
    assessment = thread.assessments[-1].model_copy(update={"stance": "accept"})
    thread.assessments = [assessment]
    new = Challenge(
        **runtime.scope(),
        claim_id=thread.current.id,
        critic_id=reviewer,
        objection="New offline fixture objection after earlier acceptance",
    )
    thread.criticisms.append(new)
    thread.decisions = [d.model_copy(update={"outcome": "retain"}) for d in thread.decisions]
    records = [assessment if p.id == assessment.id else p for e in bundle.events for p in e.payload]
    records.append(new)
    result = assess_cycle(
        [thread], records, {reviewer}, {d.adjudicator_id for d in thread.decisions}, True
    )
    assert result.conclusion is None and new.id in result.pending_challenges
    assert reviewer in result.pending_reviewers


def test_invalid_source_reference_counts_as_invalid_not_as_support(controller):
    from doxa.core.citation_audit import citation_counts
    from doxa.core.models import Evidence

    run = prepare(controller)
    scope = dict(
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=controller.inspect(run.id).events[0].trajectory_id,
        provenance=Provenance.IMPORTED_SOURCE,
    )
    evidence = Evidence(**scope, description="Invalid legacy fixture", source="source-document:bad")
    claim = Claim(**scope, proposition="An unsupported fixture claim", evidence_ids=(evidence.id,))
    counts = citation_counts(controller, (claim,), {evidence.id: evidence})
    assert counts["document_links"] == 1 and counts["invalid_links"] == 1
    assert counts["located_spans"] == 0


def test_plateau_stops_strict_review_without_forcing_agreement(controller):
    run = strict_run(controller, rounds=3, plateau=1)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def maintained(actor, phase, manifest):
        body = json.loads(default(actor, phase, manifest))
        action = body["research_action"]
        if action["operation"] == "respond":
            action.update(response="reject", revised_proposition=None)
        if actor.role == Role.ARCHIVIST:
            action["outcome"] = "retain"
        return json.dumps(body)

    runtime.synthetic_answer = maintained
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    outcome = next(p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome))
    assert outcome.execution_status == "stopped" and outcome.cycles == 2
    assert outcome.reason == "structural_plateau_no_new_claim_or_evidence"


def test_cli_can_configure_dispute_review_without_inference(controller):
    from typer.testing import CliRunner

    from doxa.cli.main import app

    prepare(controller)
    command = [
        "experiment",
        "new",
        "--name",
        "CLI criteria fixture",
        "--question",
        "A question",
        "--investigation",
        "--review-disputes",
        "--data-dir",
        str(controller.settings.data_dir),
    ]
    for role in (Role.RESEARCHER, Role.SKEPTIC, Role.ARCHIVIST):
        command.extend(["--member", role.value + ":1"])
    result = CliRunner().invoke(app, command)
    assert result.exit_code == 0, result.output
    run = next(
        r
        for r in controller.list_runs()
        if controller.ledger.get(r.experiment_id).name == "CLI criteria fixture"
    )
    task = controller.ledger.get(run.experiment_id).task
    assert task.research_protocol == "investigation" and REVIEW_DISPUTES in task.evaluation_criteria
    assert run.execution_kind == "synthetic" and run.status == "configured"
    assert not controller.ledger.records("model_call")


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_terminal_can_save_optional_review_criterion(controller, monkeypatch, tmp_path, size):
    from textual.widgets import Checkbox, Input, Select, TextArea

    from doxa.cli.console import ResearchConsole
    from doxa.cli.screens import SetupScreen

    prepare(controller)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=size) as pilot:
            app.push_screen(SetupScreen(controller, "experiment", execution_kind="synthetic"))
            await pilot.pause()
            form = app.screen
            form.query_one("#setup-name", Input).value = "Terminal review fixture"
            form.query_one("#setup-text", TextArea).load_text(
                "Offline question with explicit criteria"
            )
            form.query_one("#setup-members", Input).value = "researcher:1; skeptic:1; archivist:1"
            form.query_one("#setup-research-protocol", Select).value = "investigation"
            form.query_one("#setup-structured", Checkbox).value = True
            form.query_one("#setup-review-disputes", Checkbox).value = True
            button = form.query_one("#setup-save")
            button.focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is not form
            await pilot.press("q")

    asyncio.run(interaction())
    experiment = next(
        controller.ledger.get(r.experiment_id)
        for r in controller.list_runs()
        if controller.ledger.get(r.experiment_id).name == "Terminal review fixture"
    )
    assert REVIEW_DISPUTES in experiment.task.evaluation_criteria


def test_criteria_and_citation_results_survive_export_and_restore(
    controller, tmp_path, tmp_path_factory
):
    from doxa.core.controller import Controller
    from doxa.core.exports import export_archive
    from doxa.storage.backup import backup_workspace, restore_workspace
    from scripts.inspect_research_archive import inspect_archive

    run = strict_run(controller)
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    path = tmp_path / "criteria.zip"
    export_archive(controller, run.id, path)
    assert inspect_archive(path)["files_verified"] > 0
    external = tmp_path_factory.mktemp("criteria-roundtrip")
    backup_workspace(controller.settings.data_dir, external / "backup")
    restore_workspace(external / "backup", external / "restored")
    restored = Controller(
        controller.settings.model_copy(update={"data_dir": external / "restored"})
    )
    restored.initialize()
    assert restored.inspect(run.id).model_dump() == bundle.model_dump()
