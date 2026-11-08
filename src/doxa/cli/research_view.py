"""Claim exchanges and citation navigation over existing immutable records."""

import difflib
import re
from typing import Any
from uuid import UUID

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, TextArea

from doxa.cli.navigation import ClientModal
from doxa.core.investigation import ClaimThread
from doxa.core.models import Evidence, SourceDocument
from doxa.storage.artifacts import ArtifactStore


def thread_text(thread: ClaimThread, names: dict[Any, str] | None = None) -> str:
    names = names or {}
    lines = [
        thread.current.proposition,
        "",
        "Position: " + thread.position,
        "Author: " + names.get(thread.current.author_id, "Researcher"),
        "All model judgments below remain unverified.",
    ]
    for i, claim in enumerate(thread.versions, 1):
        lines += [f"\nCLAIM VERSION {i}", claim.proposition]
        for criticism in thread.criticisms:
            if criticism.claim_id != claim.id:
                continue
            lines += [
                "\nOBJECTION · " + names.get(criticism.critic_id, "Skeptic"),
                criticism.objection,
            ]
            responses = [r for r in thread.responses if r.responds_to_id == criticism.id]
            if not responses:
                lines.append("Author response pending / not recorded")
            for response in responses:
                lines += ["\nAUTHOR RESPONSE · " + str(response.response), response.objection]
        for assessment in thread.assessments:
            if assessment.claim_id == claim.id:
                lines += ["\nREASSESSMENT · " + assessment.stance, assessment.reason]
        for decision in thread.decisions:
            if decision.claim_id == claim.id:
                lines += [
                    "\nJUDGMENT · " + decision.outcome + " · " + str(decision.provenance),
                    decision.reason,
                ]
    if len(thread.versions) > 1:
        lines += [
            "\nVERSION COMPARISON",
            *difflib.unified_diff(
                thread.versions[0].proposition.splitlines(),
                thread.current.proposition.splitlines(),
                fromfile="original claim",
                tofile="current claim",
                lineterm="",
            ),
        ]
    lines.append("\nSources open separately; full text is never inserted into this exchange.")
    return "\n".join(lines)


class CitationScreen(ClientModal[None]):
    CSS = """
    CitationScreen { align: center middle; }
    #citation-dialog { width: 96%; height: 96%; }
    #citation-text { height: 1fr; border: none; }
    #citation-controls { height: 3; }
    """

    def __init__(self, controller: Any, evidence_ids: tuple[Any, ...], text: str):
        super().__init__()
        self.controller, self.subject_text = controller, text
        self.sources: dict[str, tuple[Evidence, SourceDocument]] = {}
        for identity in evidence_ids:
            evidence = controller.ledger.get(identity)
            if isinstance(evidence, Evidence) and evidence.source.startswith("source-document:"):
                from uuid import UUID

                source = controller.ledger.get(UUID(evidence.source.split(":", 1)[1]))
                if isinstance(source, SourceDocument):
                    self.sources[str(source.id)] = (evidence, source)

    def compose(self) -> ComposeResult:
        with Vertical(id="citation-dialog"):
            yield Label("Evidence passage · citation location may be unverified", markup=False)
            yield Select(
                [(Text(source.title), key) for key, (_, source) in self.sources.items()],
                prompt="Select cited source",
                id="citation-source",
            )
            yield Input(
                placeholder="Physical PDF page (optional); Enter opens that page",
                id="citation-page",
            )
            yield TextArea(read_only=True, id="citation-text")
            with Horizontal(id="citation-controls"):
                yield Button("Cited passage", id="citation-passage")
                yield Button("Full source", id="citation-full")
                yield Button("Close", id="citation-close")

    def on_mount(self) -> None:
        if self.sources:
            self.query_one("#citation-source", Select).value = next(iter(self.sources))
        else:
            self.query_one("#citation-text", TextArea).load_text(
                "No source-document citation is recorded."
            )
            self.query_one("#citation-source", Select).disabled = True
            self.query_one("#citation-page", Input).disabled = True
            self.query_one("#citation-passage", Button).disabled = True
            self.query_one("#citation-full", Button).disabled = True

    def show_source(self, full: bool = False) -> None:
        key = self.query_one("#citation-source", Select).value
        if not isinstance(key, str) or key not in self.sources:
            return
        evidence, source = self.sources[key]
        text = (
            ArtifactStore(self.controller.settings.data_dir / "artifacts")
            .get(source.content)
            .decode()
        )
        location = "Full source (explicitly opened)"
        if not full:
            span = re.fullmatch(r"unicode_characters:(\d+):(\d+)", evidence.source_location or "")
            page = re.search(
                r"(?:physical\s+PDF\s+)?(?:pp?\.|pages?)\s*(\d+)", self.subject_text, re.I
            )
            if span:
                start, end = map(int, span.groups())
                text = text[max(0, start - 200) : end + 200]
                location = f"Recorded character span {start}:{end}; surrounding context included"
            elif self.query_one("#citation-page", Input).value:
                chosen = self.query_one("#citation-page", Input).value
                if chosen.isdigit() and f"[Page {int(chosen)}]" in text:
                    number = int(chosen)
                    text = text.split(f"[Page {number}]", 1)[1].split(f"[Page {number + 1}]", 1)[0]
                    location = f"Selected physical PDF page {number}; entailment remains unverified"
                else:
                    text = "Requested physical page is absent. No citation location was invented."
                    location = "Location unavailable"
            elif page and f"[Page {page[1]}]" in text:
                number = int(page[1])
                text = text.split(f"[Page {number}]", 1)[1].split(f"[Page {number + 1}]", 1)[0]
                location = f"Physical PDF page {number}, mentioned in claim; exact span unverified"
            else:
                from doxa.retrieval.excerpts import evidence_excerpt

                text = evidence_excerpt(
                    self.controller.settings.database_path,
                    source.id,
                    text,
                    self.subject_text,
                    max_bytes=2400,
                )
                location = "Relevant located excerpts; exact citation location unverified"
        self.query_one("#citation-text", TextArea).load_text(
            source.title
            + "\n"
            + location
            + "\nPrinted page numbering: not inferred\n"
            + "Source: "
            + str(source.id)
            + "\nEntailment: unverified\n\n"
            + text
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "citation-page":
            self.show_source()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "citation-source":
            self.show_source()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "citation-close":
            self.dismiss(None)
        else:
            self.show_source(full=event.button.id == "citation-full")


class ThreadScreen(ClientModal[None]):
    CSS = CitationScreen.CSS.replace("CitationScreen", "ThreadScreen").replace(
        "citation-", "thread-"
    )

    def __init__(self, controller: Any, thread: ClaimThread, names: dict[Any, str]):
        super().__init__()
        self.controller, self.thread, self.names = controller, thread, names

    def compose(self) -> ComposeResult:
        with Vertical(id="thread-dialog"):
            yield Label("Claim · criticism · response · revisions · judgments", markup=False)
            yield TextArea(thread_text(self.thread, self.names), read_only=True, id="thread-text")
            with Horizontal(id="thread-controls"):
                yield Button("Sources", id="thread-sources")
                yield Button(
                    "Label revision",
                    id="thread-quality",
                    disabled=len(self.thread.versions) < 2,
                    tooltip="A versioned revision is required for correction labels",
                )
                yield Button("Close", id="thread-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "thread-close":
            self.dismiss(None)
        elif event.button.id == "thread-quality":
            self.app.push_screen(QualityScreen(self.controller, self.thread.current))
        else:
            records = [
                *self.thread.versions,
                *self.thread.criticisms,
                *self.thread.responses,
                *self.thread.assessments,
                *self.thread.decisions,
            ]
            ids = tuple(dict.fromkeys(e for r in records for e in getattr(r, "evidence_ids", ())))
            self.app.push_screen(
                CitationScreen(self.controller, ids, thread_text(self.thread, self.names))
            )


class QualityScreen(ClientModal[None]):
    CSS = CitationScreen.CSS.replace("CitationScreen", "QualityScreen").replace(
        "citation-", "quality-"
    )

    def __init__(self, controller: Any, claim: Any):
        super().__init__()
        self.controller, self.claim = controller, claim

    def compose(self) -> ComposeResult:
        with Vertical(id="quality-dialog"):
            yield Label("Human correction labels; uncertainty must remain unknown", markup=False)
            yield Input(
                value="local-operator", placeholder="Human reviewer identity", id="quality-reviewer"
            )
            for key, label in (
                ("initial", "Original claim correctness"),
                ("final", "Revised claim correctness"),
                ("justified", "Was the revision justified by evidence?"),
            ):
                yield Label(label, markup=False)
                yield Select(
                    [("Unknown", "unknown"), ("Yes / correct", "yes"), ("No / incorrect", "no")],
                    value="unknown",
                    allow_blank=False,
                    id="quality-" + key,
                )
            yield TextArea(id="quality-text")
            yield Label("", id="quality-error", markup=False)
            with Horizontal(id="quality-controls"):
                yield Button("Save human labels", id="quality-save")
                yield Button("Cancel", id="quality-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quality-cancel":
            self.dismiss(None)
            return
        from doxa.core.quality_labels import label_correction

        values = [
            {"unknown": None, "yes": True, "no": False}[
                str(self.query_one("#quality-" + key, Select).value)
            ]
            for key in ("initial", "final", "justified")
        ]
        try:
            label_correction(
                self.controller,
                self.claim.run_id,
                self.claim.trajectory_id,
                self.claim.id,
                values[0],
                values[1],
                values[2],
                self.query_one("#quality-text", TextArea).text,
                self.query_one("#quality-reviewer", Input).value,
            )
        except (ValueError, PermissionError):
            self.query_one("#quality-error", Label).update(
                "Cannot save: select a revision and supply a human reviewer identity."
            )
            return
        self.dismiss(None)


class ControlScreen(ClientModal[None]):
    CSS = """ControlScreen { align: center middle; }
    #control-dialog { width: 85%; height: auto; padding: 1; }"""

    def __init__(self, controller: Any, reference_run: Any):
        super().__init__()
        self.controller, self.reference_run = controller, reference_run
        self.created_run: UUID | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="control-dialog"):
            yield Label("Prepare an unstarted control; no model calls", markup=False)
            yield Select(
                [
                    ("Solo baseline", "solo"),
                    ("Self-correction baseline", "self_correction"),
                    ("Multi-agent investigation", "multi_agent"),
                ],
                value="solo",
                allow_blank=False,
                id="control-condition",
            )
            yield Label(
                "Reuse shared sources, question and model settings. Call ceilings differ.",
                markup=False,
            )
            yield Label("", id="control-error", markup=False)
            yield Button("Prepare control", id="control-save")
            yield Button("Cancel", id="control-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "control-cancel":
            self.dismiss(None)
            return
        from typing import cast

        from doxa.core.controls import prepare_control

        try:
            self.created_run = prepare_control(
                self.controller,
                self.reference_run,
                cast(Any, self.query_one("#control-condition", Select).value),
            )
        except (ValueError, PermissionError):
            self.query_one("#control-error", Label).update(
                "Cannot prepare: use shared evidence and compatible pinned participants."
            )
            return
        self.dismiss(None)
