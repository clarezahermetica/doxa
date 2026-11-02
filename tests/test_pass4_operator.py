"""A complete surface-driven operator session; no hidden research setup or paid inference."""

import asyncio
import zipfile
from pathlib import Path

import pytest
from textual.widgets import Checkbox, Collapsible, Input, Select, SelectionList, TextArea

from doxa.cli.console import ResearchConsole
from doxa.cli.onboarding import GettingStarted
from doxa.core.models import Challenge, Claim, Decision, ModelCall, Provenance
from scripts.canonical_research import BOUNDED, OPENING, QUESTION


@pytest.mark.parametrize("size,theme", [((80, 24), "textual-dark"), ((120, 40), "textual-light")])
def test_independent_operator_creates_reviews_branches_and_exports_without_internal_setup(
    tmp_path, monkeypatch, size, theme
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))
    monkeypatch.setenv("DOXA_MOSS_ENABLED", "false")
    workspace = tmp_path / "operator workspace"
    destination = tmp_path / "operator-research.zip"
    corpus = Path(__file__).resolve().parents[1] / "examples/canonical-research/sources"

    async def interaction():
        app = ResearchConsole(workspace, show_guide=True)
        app.theme = theme
        async with app.run_test(size=size) as pilot:

            async def activate(selector):
                control = app.screen.query_one(selector)
                control.scroll_visible(immediate=True, animate=False, force=True)
                control.focus()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

            async def command(title):
                await pilot.press("ctrl+p")
                await pilot.pause()
                app.screen.query_one(Input).value = title
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

            async def pick(selector, *keys):
                widget = app.screen.query_one(selector, Select)
                widget.scroll_visible(immediate=True, animate=False, force=True)
                widget.focus()
                await pilot.press("enter", *keys, "enter")
                await pilot.pause()

            async def expand():
                for panel in app.screen.query(Collapsible):
                    panel.collapsed = False
                await pilot.pause()

            async def review(operation, text="", target=False, actor=1, evidence=False):
                await command("Review branch and revise claims")
                app.screen.query_one("#review-action", Select).value = operation
                await pilot.pause()
                if target:
                    await pick("#review-target", "end")
                if operation in {"claim", "challenge", "respond"}:
                    await pick("#review-actor", "home", *("down",) * actor)
                app.screen.query_one("#review-text", TextArea).load_text(text)
                if evidence:
                    await expand()
                    choices = app.screen.query_one("#review-sources", SelectionList)
                    choices.scroll_visible(immediate=True, animate=False, force=True)
                    choices.focus()
                    await pilot.press("down", "space")  # S2, chosen by its visible list position.
                    assert choices.selected

            await pilot.pause()
            assert isinstance(app.screen, GettingStarted)
            await activate("#guide-offline")
            await activate("#guide-do")
            app.screen.query_one("#workspace-create", Checkbox).value = True
            await activate("#workspace-open")
            assert app.ready and (workspace / "ledger.sqlite3").is_file()
            await pilot.press("escape")
            await command("Choose model and connection")
            app.screen.query_one("#model-id", Input).value = "unverified/custom-operator-fixture"
            await activate("#model-next")
            app.screen.query_one("#model-name", Input).value = "operator-local"
            app.screen.query_one("#model-connection", Select).value = "vllm"
            await pilot.pause()
            await expand()
            for identity, value in {
                "model-url": "http://127.0.0.1:12345/v1",
                "model-input-bytes": "524288",
                "model-context": "65536",
                "model-output": "1024",
            }.items():
                app.screen.query_one("#" + identity, Input).value = value
            app.screen.query_one("#model-text-capability", Select).value = "available"
            app.screen.query_one("#model-structured-capability", Select).value = "prompted"
            await activate("#model-save")
            assert len(app.screen_stack) == 1
            for role in ("researcher", "skeptic", "archivist"):
                await command("Add agent template")
                app.screen.query_one("#setup-name", Input).value = "Operator " + role
                app.screen.query_one("#setup-role", Select).value = role
                app.screen.query_one("#setup-profile", Select).value = "operator-local"
                app.screen.query_one("#setup-text", TextArea).load_text(
                    "Use the fixed corpus; preserve finite scope and unknown performance."
                )
                await activate("#setup-save")
                assert len(app.screen_stack) == 1
            await command("Create experiment")
            app.screen.query_one("#setup-name", Input).value = "Canonical operator workflow"
            app.screen.query_one("#setup-execution", Select).value = "synthetic"
            app.screen.query_one("#setup-text", TextArea).load_text(QUESTION)
            app.screen.query_one(
                "#setup-members", Input
            ).value = "Operator researcher:2; Operator skeptic:2; Operator archivist:1"
            await expand()
            for identity, value in {
                "setup-rounds": "3",
                "setup-agent-tokens": "131072",
                "setup-total-tokens": "1048576",
                "setup-context": "32768",
                "setup-timeout": "300",
            }.items():
                app.screen.query_one("#" + identity, Input).value = value
            app.screen.query_one("#setup-structured", Checkbox).value = True
            app.screen.query_one("#setup-staged", Checkbox).value = True
            await activate("#setup-save")
            assert len(app.screen_stack) == 1 and app.selected is not None
            for source in sorted(corpus.glob("*.md")):
                await command("Import evidence")
                app.screen.query_one("#file", Input).value = str(source)
                await activate("#import-save")
                assert len(app.screen_stack) == 1
            await command("Inspect launch preflight")
            await activate("#tool-run")
            assert app.screen.query_one("#tool-result", TextArea).text
            await pilot.press("escape")
            await command("Start selected run")
            await activate("#start-save")
            for _ in range(900):
                await pilot.pause(0.1)
                if app.current_bundle and app.current_bundle.run.status in {"completed", "failed"}:
                    break
            assert app.current_bundle.run.status == "completed"
            # All domain-specific inputs below are visibly human review, not fake inference.
            await review("claim", OPENING, evidence=True)
            await activate("#review-save")
            await review(
                "challenge",
                "Human fixture objection: the fail cells in S2 contradict this claim.",
                target=True,
                actor=3,
                evidence=True,
            )
            await activate("#review-save")
            await review(
                "respond",
                "Human fixture response: qualify to the supplied finite oracle.",
                target=True,
            )
            app.screen.query_one("#review-outcome", Select).value = "qualify"
            await expand()
            app.screen.query_one("#review-replacement", TextArea).load_text(BOUNDED)
            await activate("#review-save")
            await review(
                "adjudicate",
                "Human fixture judgment: retain only the bounded conclusion.",
                target=True,
            )
            app.screen.query_one("#review-outcome", Select).value = "qualify"
            await activate("#review-save")
            await review("evaluate")
            await activate("#review-save")
            await review("checkpoint")
            await activate("#review-save")
            await review("fork", "Human-analysis alternative; no model replay.", target=True)
            await activate("#review-save")
            await pick("#branch-picker", "end")
            await review(
                "claim", "Human alternative: speed remains unmeasured.", target=True, evidence=True
            )
            await activate("#review-save")
            await command("Compare trajectories")
            await pick("#tool-left", "home", "down")
            await pick("#tool-right", "end")
            await activate("#tool-run")
            assert app.screen.query_one("#tool-result", TextArea).text
            await pilot.press("escape")
            await command("Export experiment history")
            app.screen.query_one("#export-path", Input).value = str(destination)
            await activate("#export-save")
            assert destination.is_file()
            await pilot.press("escape", "q")
        # Read-only verification after operations were performed exclusively on UI surfaces.
        records = [p for e in app.controller.inspect(app.selected).events for p in e.payload]
        assert not any(isinstance(p, ModelCall) for p in records)
        assert any(isinstance(p, Claim) and p.proposition == OPENING for p in records)
        assert any(isinstance(p, Claim) and p.revises_id for p in records)
        assert any(isinstance(p, Challenge) and p.responds_to_id for p in records)
        assert any(
            isinstance(p, Decision) and p.provenance == Provenance.HUMAN_ANNOTATION for p in records
        )
        with zipfile.ZipFile(destination) as archive:
            assert "history.json" in archive.namelist()

    asyncio.run(interaction())
