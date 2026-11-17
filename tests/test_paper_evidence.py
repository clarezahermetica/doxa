"""Offline regression coverage for research evidence planning and inspection."""

import asyncio
import json
from uuid import uuid4

import pytest

from doxa.cli.turn_evidence import describe_turn_evidence
from doxa.core.models import Claim, ContextManifest, ResponseNormalization, Role, SourcePassage
from doxa.core.text_research import ReviewChallenge, ReviewClaim, TextResearch
from doxa.core.workbench import ContextAssembler, ImportSource, import_source
from doxa.retrieval.excerpts import paper_sections, select_passages
from tests.test_passage_continuity import arrangement

PARSER = "pypdf-text-fixture-v1"
PAPER = (
    "[Page 1]\nABSTRACT\n"
    + "temperature result temperature result. " * 95
    + "\n[Page 2]\n1 INTRODUCTION\n"
    + "temperature result. " * 100
    + "\n[Page 3]\n2 E XPERIMENTAL SETUP\n"
    "METHODS-MARKER: Sampling was predefined and excluded pilot measurements.\n"
    + "The laboratory grouped specimens by instrument and time. "
    * 32
    + "\n[Page 4]\n3 R ESULTS\n"
    "RESULTS-MARKER: Nine of ten replicate measurements fell within the margin.\n"
    + "Interval estimates were reported for each condition. "
    * 20
    + "\n[Page 5]\n4 LIMITATIONS\n"
    "LIMITS-MARKER: The design cannot establish performance outside the sample.\n"
    + "An external replication was not conducted. "
    * 16
)


def prepare(controller, *, cap=8192, body=PAPER, parser=PARSER):
    run, branch, actors, original = arrangement(controller, cap=cap)
    source = import_source(
        controller,
        run.id,
        ImportSource(
            title="Paper fixture",
            text=body,
            parser_version=parser,
            revises_id=original.id,
            idempotency_key="paper",
        ),
    )
    return run, branch, actors, source


def prompt_and_packet(assembler, manifest, source):
    messages = json.loads(assembler.runtime.store.get(manifest.messages))
    user = next(m["content"] for m in messages if m["role"] == "user")
    records = [json.loads(line) for line in user.splitlines()]
    packet = next((r for r in records if r.get("source_id") == str(source.id)), None)
    return user, packet


def test_initial_paper_prompt_covers_methods_results_and_limits_despite_abstract(controller):
    run, _, actors, source = prepare(controller, cap=3200)
    legacy = select_passages(
        controller.settings.database_path, source.id, PAPER, "What is the temperature result?", 3200
    )
    assert "METHODS-MARKER" not in legacy.text
    assembler = ContextAssembler(controller, run.id)
    manifest = assembler.assemble(actors[Role.RESEARCHER], "round:0")
    assert manifest.selection_strategy == "paper_sections_and_prior_citations_v5"
    _, packet = prompt_and_packet(assembler, manifest, source)
    for marker in ("METHODS-MARKER", "RESULTS-MARKER", "LIMITS-MARKER"):
        assert marker in packet["untrusted_content"]
    assert packet["source_ranges"] == [[p.start, p.end] for p in manifest.source_passages]


@pytest.mark.parametrize("cap", [8192, 256])
def test_long_review_supplies_targeted_citation_or_explains_why(controller, cap):
    run, branch, actors, source = prepare(controller, cap=cap)
    start = PAPER.index("RESULTS-MARKER")
    end = start + 310
    action = controller.review_command(
        run.id,
        branch,
        ReviewClaim(
            author_id=actors[Role.RESEARCHER].id,
            proposition="temperature result " * 175,
            source_ids=(source.id,),
            citation_ranges=(
                SourcePassage(
                    source_id=source.id,
                    start=start,
                    end=end,
                ),
            ),
            idempotency_key="claim",
        ),
    )
    claim = next(p for p in action.payload if isinstance(p, Claim))
    for i in range(5):
        controller.review_command(
            run.id,
            branch,
            ReviewChallenge(
                critic_id=actors[Role.ARCHIVIST].id,
                claim_id=claim.id,
                objection="Prior discussion is extensive and not direct evidence. " * 62,
                idempotency_key=f"long:{i}",
            ),
        )
    assembler = ContextAssembler(controller, run.id)
    manifest = assembler.assemble(actors[Role.SKEPTIC], f"round:4:target:{claim.id}")
    prompt, packet = prompt_and_packet(assembler, manifest, source)
    operator = describe_turn_evidence(manifest, assembler.runtime.store)
    assert "evidence_ids" in prompt
    assert "Earlier citation references" in operator
    assert len(manifest.history_ids) >= 5
    assert manifest.input_token_upper_bound + 1024 <= 16384
    if cap == 8192:
        assert PAPER[start:end] in packet["untrusted_content"] and PAPER[start:end] in operator
        assert manifest.required_passages[0].status == "supplied"
    else:
        assert manifest.required_passages[0].status == "omitted_budget"
        assert '"required_passage_gaps": {"omitted_budget": 1}' in prompt
        assert PAPER[start:end] not in prompt
        assert "not supplied: context budget" in operator


def test_old_and_clipped_turn_inspect_the_saved_packet_without_expanding_it(controller):
    intro = PAPER[: PAPER.index("[Page 3]")]
    assert not paper_sections(intro, PARSER)
    assert not paper_sections(PAPER, "utf8-text-v1")
    run, _, actors, source = prepare(controller, cap=380, body=intro)
    assembler = ContextAssembler(controller, run.id)
    manifest = assembler.assemble(actors[Role.RESEARCHER], "round:0")
    assert manifest.selection_strategy == "required_criticism_passages_v4"
    _, packet = prompt_and_packet(assembler, manifest, source)
    (span,) = manifest.source_passages
    assert span.end - span.start < 1000
    operator = describe_turn_evidence(manifest, assembler.runtime.store)
    assert packet["untrusted_content"] in operator
    assert intro[span.start : span.end + 200] not in operator
    old = ContextManifest.model_validate(
        {
            **manifest.model_dump(),
            "source_passages": (),
        }
    )
    legacy_view = describe_turn_evidence(old, assembler.runtime.store)
    assert "exact passage ranges were not recorded" in legacy_view
    assert "ranges unverified" in legacy_view
    assert packet["untrusted_content"] in legacy_view


def test_non_paper_uses_unchanged_ranked_packets(controller):
    run, _, actors, source = prepare(controller, cap=2800, parser="utf8-text-v1")
    ordinary = select_passages(
        controller.settings.database_path,
        source.id,
        PAPER,
        "What is the temperature result? ",
        2800,
    )
    assembler = ContextAssembler(controller, run.id)
    manifest = assembler.assemble(actors[Role.RESEARCHER], "round:0")
    assert manifest.selection_strategy == "required_criticism_passages_v4"
    _, packet = prompt_and_packet(assembler, manifest, source)
    assert packet["untrusted_content"] == ordinary.text
    assert manifest.source_passages == ordinary.passages


def test_live_council_turn_input_renders_the_linked_clipped_packet(
    controller, monkeypatch, tmp_path
):
    from textual.widgets import TextArea

    from doxa.cli.console import ResearchConsole
    from doxa.cli.live_council import FeedScroll
    from tests.test_live_council import ready

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))
    run, branch, actors, source = prepare(controller, cap=380, parser="utf8-text-v1")
    assembler = ContextAssembler(controller, run.id)
    actor = actors[Role.RESEARCHER]
    manifest = assembler.assemble(actor, "round:0")
    _, packet = prompt_and_packet(assembler, manifest, source)
    audit = ResponseNormalization(
        id=uuid4(),
        normalizer_version="offline-fixture",
        agent_id=actor.id,
        context_id=manifest.id,
        input_sha256="a" * 64,
        execution_kind="synthetic",
        disposition="accepted",
        reason_code="validated",
        experiment_id=run.experiment_id,
        run_id=run.id,
        trajectory_id=branch,
        provenance=manifest.provenance,
    )
    event = TextResearch(controller, run.id, branch).apply_generated(
        {"operation": "claim", "proposition": "A bounded claim.", "source_ids": [str(source.id)]},
        actor,
        "fixture-reply",
        manifest.source_ids,
        synthetic=True,
        normalization=audit,
        visible_passages=manifest.source_passages,
    )

    async def inspect():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.selected = run.id
        async with app.run_test(size=(80, 24)) as pilot:
            app.action_live_council()
            view = await ready(pilot, app, event.id)
            await view.select((event.id, False))
            view.query_one(FeedScroll).focus()
            await pilot.press("u")
            shown = view.query_one("#council-details", TextArea).text
            assert packet["untrusted_content"] in shown
            span = manifest.source_passages[0]
            assert PAPER[span.start : span.end + 200] not in shown

    asyncio.run(inspect())
