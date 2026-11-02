"""Canonical fixture, independent archive inspection and preserved-history reproduction."""

import asyncio
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from doxa.core.config import Settings
from doxa.core.controller import Controller
from doxa.core.models import Claim, ContextManifest, Evidence, Experiment
from doxa.storage.backup import backup_workspace, restore_workspace
from scripts.canonical_research import BOUNDED, OPENING, conduct


@pytest.fixture(scope="module")
def canonical_study(tmp_path_factory):
    base = tmp_path_factory.mktemp("canonical-v1")
    corpus = Path(__file__).resolve().parents[1] / "examples/canonical-research"
    result = conduct(base / "workspace", base / "results", corpus)
    return base, result


def test_canonical_controls_measure_linkage_without_claiming_entailment(canonical_study):
    base, result = canonical_study
    controller = Controller(Settings(data_dir=base / "workspace"))
    controller.initialize()
    for condition, participants, objections, revisions in (
        ("A", 1, 0, 0),
        ("B", 2, 1, 1),
        ("C", 5, 2, 1),
    ):
        observation = result["conditions"][condition]
        assert observation["participants"] == participants
        assert len(set(observation["participant_ids"])) == participants
        assert observation["contexts"] == participants * 3
        metrics = observation["metrics"]["metrics"]
        assert metrics["criticisms"] == objections and metrics["revisions"] == revisions
        assert metrics["criticisms_unresolved"] == 0
        assert metrics["evidence_linked_claim_rate"] == 1
        assert metrics["objective_correctness"] is None
        assert metrics["citation_entailment"] is None
        assert observation["metrics"]["usage"]["billed_usd"] is None
        from uuid import UUID

        bundle = controller.inspect(UUID(observation["run_id"]))
        records = {p.id: p for e in bundle.events for p in e.payload}
        wrong = next(
            p for p in records.values() if isinstance(p, Claim) and p.proposition == OPENING
        )
        assert wrong.evidence_ids  # A real citation can support a false/unsupported sentence.
        assert any(isinstance(records[i], Evidence) for i in wrong.evidence_ids)
        if condition != "A":
            assert any(
                isinstance(p, Claim) and p.revises_id == wrong.id and p.proposition == BOUNDED
                for p in records.values()
            )
        experiment = controller.ledger.get(bundle.run.experiment_id)
        assert isinstance(experiment, Experiment)
        contexts = {p.phase: p for p in records.values() if isinstance(p, ContextManifest)}
        for event in bundle.events:
            if event.idempotency_key.startswith("generated:"):
                phase = event.idempotency_key.split(":", 3)[3]
                assert contexts[phase].agent_id == event.actor_id
        assert observation["branch_changes"] == 1
    companion = result["six_system_cache_companion"]
    assert companion["retrieved_before_revocation"]
    assert not companion["retrieved_after_revocation"]
    assert len(companion["children"]) == 2
    assert result["conditions"]["C"]["adjudications"] == 1


def test_archives_are_inspectable_without_doxa_import_or_source_workspace(canonical_study):
    base, result = canonical_study
    script = Path(__file__).resolve().parents[1] / "scripts/inspect_research_archive.py"
    detached = base / "independent"
    detached.mkdir()
    for archive in sorted((base / "results").glob("*.zip")):
        process = subprocess.run(
            [sys.executable, "-I", "-S", str(script), str(archive)],
            cwd=detached,
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert process.returncode == 0, process.stderr
        observed = json.loads(process.stdout)
        assert observed["files_verified"] > 0 and not observed["truth_or_entailment_verified"]
        if archive.name.startswith("condition-"):
            condition = archive.stem[-1]
            expected = result["conditions"][condition]["inspection"]
            assert observed["event_ids"] == expected["event_ids"]
            assert observed["source_hashes"] == expected["source_hashes"]
            assert observed["valid_citation_spans"] > 0


def test_workspace_restore_preserves_claims_contexts_evaluations_and_ancestry(canonical_study):
    base, result = canonical_study
    backup_workspace(base / "workspace", base / "backup")
    restore_workspace(base / "backup", base / "restored")
    first = Controller(Settings(data_dir=base / "workspace"))
    second = Controller(Settings(data_dir=base / "restored"))
    first.initialize()
    second.initialize()
    from uuid import UUID

    for condition in result["conditions"].values():
        identity = UUID(condition["run_id"])
        assert first.inspect(identity).model_dump() == second.inspect(identity).model_dump()
    with pytest.raises(FileExistsError):
        restore_workspace(base / "backup", base / "restored")


def test_independent_inspector_rejects_tampered_archive(canonical_study):
    base, _ = canonical_study
    from scripts.inspect_research_archive import inspect_archive

    damaged = base / "tampered.zip"
    with zipfile.ZipFile(base / "results/condition-A.zip") as original:
        with zipfile.ZipFile(damaged, "x") as destination:
            for entry in original.infolist():
                destination.writestr(
                    entry.filename,
                    b"{}" if entry.filename == "history.json" else original.read(entry.filename),
                )
    with pytest.raises(ValueError, match="hash mismatch"):
        inspect_archive(damaged)


def test_terminal_adjudication_can_review_a_responded_challenge(canonical_study, monkeypatch):
    from uuid import UUID

    from textual.widgets import Select

    from doxa.cli.console import ResearchConsole
    from doxa.cli.screens import ReviewScreen
    from doxa.core.models import Challenge, Trajectory

    base, result = canonical_study
    monkeypatch.setenv("LOCALAPPDATA", str(base / "ui-preferences"))
    controller = Controller(Settings(data_dir=base / "workspace"))
    controller.initialize()
    run_id = UUID(result["conditions"]["C"]["run_id"])
    bundle = controller.inspect(run_id)
    records = [p for e in bundle.events for p in e.payload]
    answered = {p.responds_to_id for p in records if isinstance(p, Challenge) and p.responds_to_id}
    target = next(p for p in records if isinstance(p, Challenge) and p.id in answered)
    branch = next(p.id for p in records if isinstance(p, Trajectory) and p.parent_id is None)

    async def interaction():
        app = ResearchConsole(base / "workspace", show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.push_screen(ReviewScreen(controller, run_id, branch))
            await pilot.pause()
            app.screen.query_one("#review-action", Select).value = "adjudicate"
            await pilot.pause()
            app.screen.query_one("#review-target", Select).value = str(target.id)
            assert app.screen.query_one("#review-target", Select).value == str(target.id)
            await pilot.press("escape", "q")

    asyncio.run(interaction())
