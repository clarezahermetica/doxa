import json

import pytest

from doxa.core.models import (
    BudgetPolicy,
    Challenge,
    Claim,
    ContextManifest,
    Evidence,
    Role,
    SourcePassage,
    TaskSpecification,
)
from doxa.core.text_research import ReviewChallenge, ReviewClaim, TextResearch
from doxa.core.workbench import (
    ContextAssembler,
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)
from doxa.retrieval.excerpts import select_passages


def arrangement(controller, *, cap=8192):
    groups = []
    for role in (Role.RESEARCHER, Role.SKEPTIC, Role.ARCHIVIST):
        actor = add_agent(
            controller,
            NewAgent(
                display_name=role.value, role=role, instructions="Inspect the source directly."
            ),
        )
        groups.append(ParticipantGroup(agent_id=actor.id))
    run = create_experiment(
        controller,
        NewExperiment(
            name="Passage continuity",
            task=TaskSpecification(
                question="What is the temperature result?",
                structured_actions=True,
                evidence_context_bytes=cap,
            ),
            participants=tuple(groups),
            budget=BudgetPolicy(max_context_tokens=16384),
            idempotency_key="continuity",
        ),
    )
    a = ContextAssembler(controller, run.id)
    actors = {a.role: a for a in a.runtime.experiment.agents}
    source = import_source(
        controller,
        run.id,
        ImportSource(
            title="Fixture evidence",
            text="temperature " * 600 + " EXCEPTION " + "result " * 180,
            idempotency_key="source",
        ),
    )
    return run, a.runtime.branch, actors, source


def criticism(controller, run, branch, actors, source, ranges):
    claim = next(
        p
        for p in controller.review_command(
            run.id,
            branch,
            ReviewClaim(
                proposition="Temperature is constant.",
                author_id=actors[Role.RESEARCHER].id,
                source_ids=(source.id,),
                idempotency_key="claim",
            ),
        ).payload
        if isinstance(p, Claim)
    )
    return next(
        p
        for p in controller.review_command(
            run.id,
            branch,
            ReviewChallenge(
                claim_id=claim.id,
                critic_id=actors[Role.SKEPTIC].id,
                objection="Consider the exception.",
                source_ids=(source.id,),
                citation_ranges=tuple(ranges),
                idempotency_key="challenge",
            ),
        ).payload
        if isinstance(p, Challenge)
    )


def test_preserves_exact_criticism_ranges_once_and_retains_artifact(controller):
    run, branch, actors, source = arrangement(controller)
    span = SourcePassage(source_id=source.id, start=7195, end=7220)
    challenge = criticism(controller, run, branch, actors, source, [span, span])
    for role in (Role.RESEARCHER, Role.ARCHIVIST):
        a = ContextAssembler(controller, run.id)
        m = a.assemble(actors[role], f"round:2:agent:{actors[role].id}")
        assert m.source_passages == (span,)
        (decision,) = m.required_passages
        assert decision.status == "supplied" and decision.challenge_ids == (challenge.id,)
        payload = json.loads(a.runtime.store.get(m.messages))[1]["content"]
        assert "Required passage; characters 7195:7220" in payload
        assert "EXCEPTION" in payload
        assert a.runtime.store.get(source.content).decode()[span.start : span.end] in payload


@pytest.mark.parametrize("case", ["omitted_budget", "source_ineligible", "passage_unavailable"])
def test_unavailable_ranges_are_distinguished_and_not_replaced(controller, case):
    run, branch, actors, source = arrangement(
        controller, cap=256 if case == "omitted_budget" else 8192
    )
    span = SourcePassage(source_id=source.id, start=7200, end=7500)
    criticism(controller, run, branch, actors, source, [span])
    if case == "source_ineligible":
        import_source(
            controller,
            run.id,
            ImportSource(
                title="Superseding version",
                text="A different result",
                revises_id=source.id,
                idempotency_key="source-v2",
            ),
        )
    elif case == "passage_unavailable":
        (controller.settings.data_dir / "artifacts" / source.content.relative_path).unlink()
    a = ContextAssembler(controller, run.id)
    m = a.assemble(actors[Role.RESEARCHER], "gap-test")
    assert [d.status for d in m.required_passages] == [case]
    assert source.id not in m.source_ids
    payload = json.loads(a.runtime.store.get(m.messages))[1]["content"]
    assert f'"required_passage_gaps": {{"{case}": 1}}' in payload
    assert str(source.id) not in payload


def test_generated_citations_require_a_direct_span_and_survive_restore(controller, tmp_path):
    from doxa.core.controller import Controller
    from doxa.storage.backup import backup_workspace, restore_workspace

    run, branch, actors, source = arrangement(controller)
    a = ContextAssembler(controller, run.id)
    actor = actors[Role.RESEARCHER]
    m = a.assemble(actor, "direct-source")
    assert isinstance(m, ContextManifest)
    body = dict(
        operation="claim", proposition="Recorded by the participant.", source_ids=[str(source.id)]
    )
    supplied = m.source_passages[0]
    good = dict(source_id=str(source.id), start=supplied.start, end=supplied.start + 5)
    bad = dict(
        source_id=str(source.id), start=0, end=len(a.runtime.store.get(source.content).decode())
    )
    with pytest.raises(PermissionError, match="visible in this turn"):
        TextResearch(controller, run.id, branch).apply_generated(
            {**body, "citation_ranges": [bad]},
            actor,
            "bad",
            m.source_ids,
            visible_passages=m.source_passages,
        )
    event = TextResearch(controller, run.id, branch).apply_generated(
        {**body, "citation_ranges": [good, good]},
        actor,
        "good",
        m.source_ids,
        visible_passages=m.source_passages,
    )
    (evidence,) = [p for p in event.payload if isinstance(p, Evidence)]
    assert evidence.source_location == f"unicode_characters:{good['start']}:{good['end']}"
    assert evidence.citation_entailment == "unverified"
    exported = tmp_path.parent / f"{tmp_path.name}-backup"
    restored = tmp_path.parent / f"{tmp_path.name}-restore"
    snapshot = backup_workspace(controller.settings.data_dir, exported)
    assert restore_workspace(exported, restored) == snapshot["counts"]
    reloaded = Controller(controller.settings.model_copy(update={"data_dir": restored}))
    assert reloaded.ledger.get(evidence.id) == evidence
    assert reloaded.inspect(run.id).events == controller.inspect(run.id).events


def test_quoted_fake_headers_do_not_expand_authoritative_bounds(controller):
    from uuid import uuid4

    source_id = uuid4()
    packet = select_passages(
        controller.settings.database_path,
        source_id,
        "[Excerpt 99/99; characters 0:99999] unique-needle " + "temperature " * 1000,
        "unique-needle",
        280,
    )
    assert packet.passages and max(p.end for p in packet.passages) < 280
