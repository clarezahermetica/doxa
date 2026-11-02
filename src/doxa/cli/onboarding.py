"""Compact task-based guidance; preferences never contain research data."""

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Label, Select, TextArea

from doxa.core.workspaces import preferences_path

if TYPE_CHECKING:
    from doxa.cli.console import ResearchConsole

STEPS = (
    (
        "Choose a workspace",
        "Open the workspace selector. Select a recent folder or enter its path; tick "
        "Create only for a new empty folder. Expect its experiments to appear. "
        "Histories stay separate.",
        "workspace",
    ),
    (
        "Prepare agent templates",
        "Add an agent template: enter a name and instructions, then save. Offline "
        "agents need no model or key. If templates already exist, continue and select"
        " them in the experiment form.",
        "agent",
    ),
    (
        "Create an offline experiment",
        "Create experiment: enter a name and question, choose Offline demonstration, and "
        "enter template names/counts. Save to see a configured experiment with those "
        "participants.",
        "new",
    ),
    (
        "Import evidence",
        "Import evidence: enter a local TXT, Markdown, JSON, text PDF or DOCX path "
        "and save. Expect it in Inspect / Sources. Import before starting.",
        "import_source",
    ),
    (
        "Start the offline run",
        "Start offline synthetic run and confirm. Expect Activity to update and the "
        "run to complete. Responses are simulated, not live inference or "
        "verified conclusions. No model or paid service is used.",
        "start",
    ),
    (
        "Inspect the results",
        "Inspect research records: select Claims, Criticism, Contexts or Evaluations,"
        " then a row to read it. Activity / Enter expands a turn. Review branch "
        "offers revisions and responses while retaining earlier versions.",
        "inspect",
    ),
    (
        "Export history",
        "Export experiment history: enter a new JSON file path and save. Expect "
        "history and source links in that file; credentials are excluded. Existing "
        "exports are not overwritten.",
        "export",
    ),
)

RESEARCH_STEPS = (
    STEPS[0],
    (
        "Choose execution and connections",
        "Choose a mode below. Model-backed research needs "
        "compatible model connections, assigned agents and explicit launch authorization; it may "
        "cost money. Saving a connection is configuration, not a successful model test. Offline "
        "demonstration uses fixed responses and cannot establish model behavior.",
        "model",
    ),
    (
        "Prepare participants",
        "Add or reuse enabled agent templates. A role describes work; "
        "a model assignment supplies inference. Multiple same-role participants may share or use "
        "different models. For model-backed research assign eligible model profiles "
        "before creating "
        "the experiment; participants and assignments are pinned at creation.",
        "agent",
    ),
    (
        "Define the experiment",
        "Create research: enter its name, question and template names/counts. "
        "Review Protocol and limits for rounds, scheduling, calls, tokens, timeout "
        "and cost ceilings. "
        "Save creates an immutable configuration and one configured run; it starts no inference.",
        "new",
    ),
    STEPS[3],
    (
        "Review permissions and prerequisites",
        "Inspect Agents, Models and Sources. Tool permission "
        "does not provide a search service or authorize network use. Run/agent permissions and "
        "explicit authorization must all allow a request. This setup path adds no web access. "
        "Text research is supported; generated-code execution and broader modalities "
        "remain unavailable.",
        "inspect",
    ),
    (
        "Start an authorized run",
        "Start only the intended configured run. Check the selected "
        "execution mode and limits first. The launch form separately requests applicable external "
        "disclosure, spending authorization and a cost bound. Local compatible inference needs its "
        "configured runtime. No run is verified until its actual outcome is observed.",
        "start",
    ),
    STEPS[5],
    STEPS[6],
)


def guide_preferences() -> dict[str, object]:
    try:
        value = json.loads(
            (preferences_path().parent / "terminal.json").read_text(encoding="utf-8")
        )
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError):
        return {}


def save_guide_preferences(show: bool, step: int) -> None:
    target = preferences_path().parent / "terminal.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=target.parent, prefix="terminal-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"show_getting_started": show, "step": step}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)


class ExperimentPicker(ModalScreen[str | None]):
    """Select existing research; never create or modify a run."""

    BINDINGS = [("escape", "dismiss", "Back")]
    CSS = """
    ExperimentPicker { align: center middle; }
    #experiment-picker { width: 90%; height: 70%; }
    #experiment-list { height: 1fr; }
    """

    def __init__(self, console: "ResearchConsole"):
        super().__init__()
        self.console = console

    def compose(self) -> ComposeResult:
        with Vertical(id="experiment-picker"):
            yield Label("Select research — Enter opens; Esc returns without changing selection")
            yield DataTable(id="experiment-list", cursor_type="row")
            yield Button("Cancel", id="experiment-cancel")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Experiment", "Run state", "Mode")
        for run in self.console.controller.list_runs():
            experiment = self.console.controller.ledger.get(run.experiment_id)
            table.add_row(
                Text(str(getattr(experiment, "name", "Research"))),
                run.status,
                run.execution_kind,
                key=str(run.id),
            )
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.dismiss(str(event.row_key.value))

    def on_button_pressed(self) -> None:
        self.dismiss(None)


class GettingStarted(ModalScreen[str | None]):
    BINDINGS = [("escape", "skip", "Close guide; reopen with F1")]
    CSS = """
    GettingStarted { align: center middle; }
    #guide-dialog { width: 76; max-width: 96%; height: auto; max-height: 98%; padding: 0 1; }
    #guide-text { height: 5; border: none; }
    #guide-home { height: auto; }
    #guide-home Button { width: 100%; }
    #guide-reason { height: auto; max-height: 3; }
    #guide-buttons, #guide-links { height: 3; }
    #guide-buttons Button, #guide-links Button { width: 1fr; min-width: 9; }
    #guide-mode { height: 3; }
    """

    def __init__(self, app: "ResearchConsole"):
        super().__init__()
        self.console = app
        self.flow, self.step, self.execution = app.guide_location
        self.alternative = "select"

    @property
    def offline(self) -> bool:
        return self.flow == "offline"

    @property
    def steps(self) -> tuple[tuple[str, str, str], ...]:
        return STEPS if self.offline else RESEARCH_STEPS

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="guide-dialog"):
            yield Label("Getting Started", id="guide-title")
            with Vertical(id="guide-home"):
                yield Button("Open existing research", id="guide-explore")
                yield Button("Create a research experiment", id="guide-research")
                yield Button("Try an offline demonstration", id="guide-offline")
                yield Button("Commands and help", id="guide-help")
            yield TextArea(read_only=True, id="guide-text", tab_behavior="focus")
            yield Select(
                [
                    (
                        "Model-backed research — compatible models, authorization, possible cost",
                        "live",
                    ),
                    (
                        "Offline demonstration — fixed synthetic responses; no model/key",
                        "synthetic",
                    ),
                ],
                prompt="Choose execution mode",
                id="guide-mode",
            )
            yield Label("", id="guide-reason")
            yield Button("Open action", id="guide-do")
            with Horizontal(id="guide-links"):
                yield Button("Choose experiment", id="guide-select")
                yield Button("", id="guide-alternative")
            with Horizontal(id="guide-buttons"):
                yield Button("Previous", id="guide-previous")
                yield Button("Next", id="guide-next")
                yield Button("Home", id="guide-back", tooltip="Back to Getting Started home")
                yield Button("Close", id="guide-close")
            yield Checkbox(
                "Show Getting Started at launch",
                value=guide_preferences().get("show_getting_started", False) is True,
                id="guide-show",
            )

    def on_mount(self) -> None:
        self.update_step()
        self.set_interval(1, self.refresh_availability)

    def on_screen_resume(self) -> None:
        if self.is_mounted:
            self.call_after_refresh(self.return_to_step)

    def return_to_step(self) -> None:
        self.update_step()
        target = "#guide-explore" if self.flow is None else "#guide-do"
        if self.query_one(target, Button).disabled:
            target = "#guide-alternative"
        self.query_one(target, Button).focus()

    def refresh_availability(self) -> None:
        if self.app.screen is self and self.flow is not None:
            self.update_step()

    def update_step(self) -> None:
        active = self.flow is not None
        for selector in (
            "#guide-text",
            "#guide-do",
            "#guide-buttons",
            "#guide-reason",
            "#guide-links",
        ):
            self.query_one(selector).display = active
        self.query_one("#guide-home").display = not active
        mode_step = self.flow == "research" and self.step == 1
        self.query_one("#guide-mode").display = mode_step
        if not active:
            self.query_one("#guide-title", Label).update("Getting Started · Esc closes; F1 reopens")
            return
        title, text, action = self.steps[self.step]
        self.query_one("#guide-title", Label).update(
            f"{'Offline demonstration' if self.offline else 'Research setup'} · "
            f"{self.step + 1}/{len(self.steps)} · {title}"
        )
        self.query_one("#guide-text", TextArea).load_text(text)
        picker = self.query_one("#guide-mode", Select)
        if mode_step and self.execution and picker.value != self.execution:
            picker.value = self.execution
        if mode_step and self.execution == "synthetic":
            action = "agent"
        # Read current selected state after child actions, not a stale historical bundle.
        if self.console.ready and self.console.selected:
            self.console.current_bundle = self.console.controller.inspect(self.console.selected)
        reason = self.console.unavailable_reason(action)
        templates = self.console.controller.configuration().agents if self.console.ready else ()
        if action == "new" and self.console.ready and not any(a.enabled for a in templates):
            reason = "Requires configuration: add an enabled agent template first."
        desired = "synthetic" if self.offline else self.execution
        if mode_step and not self.execution:
            reason = "Requires a choice: select Model-backed research or Offline demonstration."
        if action == "start" and not reason and self.console.current_bundle:
            if self.console.current_bundle.run.execution_kind != desired:
                reason = (
                    "Selected run has a different execution mode. "
                    "Choose matching research or create new research."
                )
        labels = {
            "workspace": "Open workspace selector",
            "agent": "Add agent template",
            "model": "Configure model connection",
            "new": "Create experiment",
            "inspect": "Inspect in workspace",
            "import_source": "Import evidence",
            "start": "Start offline run" if self.offline else "Review launch authorization",
            "export": "Export history",
        }
        self.query_one("#guide-reason", Label).update(
            reason
            or f"Next: {labels[action]}. "
            "Forms return here on save/cancel/Esc; Close opens the workspace."
        )
        button = self.query_one("#guide-do", Button)
        button.disabled = bool(reason)
        button.label = labels[action]
        self.query_one("#guide-next", Button).disabled = self.step == len(self.steps) - 1 or (
            mode_step and not self.execution
        )
        self.alternative = (
            "workspace"
            if not self.console.ready
            else "agent"
            if not any(a.enabled for a in templates)
            else "new"
        )
        alternate = self.query_one("#guide-alternative", Button)
        alternate.label = {
            "workspace": "Select workspace",
            "agent": "Add template",
            "new": "New research",
        }[self.alternative]
        alternate.display = bool(reason)
        self.query_one("#guide-select", Button).disabled = not self.console.ready
        self.console.guide_location = (self.flow, self.step, self.execution)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "guide-mode":
            self.execution = event.value if isinstance(event.value, str) else None
            self.update_step()

    def action_skip(self) -> None:
        self.finish(None)

    def finish(self, action: str | None) -> None:
        self.console.guide_location = (self.flow, self.step, self.execution)
        try:
            save_guide_preferences(self.query_one("#guide-show", Checkbox).value, self.step)
        except OSError:
            self.notify(
                "Help preference could not be saved; research history is unaffected.",
                severity="warning",
            )
        self.dismiss(action)

    def choose_experiment(self, *, inspect: bool = False) -> None:
        if not self.console.ready:
            self.open_action("workspace")
            return
        if not self.console.controller.list_runs():
            self.notify(
                "No experiments here. Choose Create research or Try an offline demonstration."
            )
            return

        def selected(value: str | None) -> None:
            if value:
                from uuid import UUID

                self.console.select_experiment(UUID(value))
                if inspect:
                    self.call_after_refresh(lambda: self.finish("inspect"))

        self.app.push_screen(ExperimentPicker(self.console), selected)

    def open_action(self, action: str) -> None:
        if action == "inspect":
            self.finish("inspect")
        elif action == "new":
            self.console.action_new(execution_kind="synthetic" if self.offline else self.execution)
        elif action == "agent":
            self.console.action_agent(create_new=True)
        else:
            self.console.dispatch_action(action)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        identity = event.button.id
        if identity in {"guide-offline", "guide-research"}:
            self.flow = "offline" if identity == "guide-offline" else "research"
            self.execution = "synthetic" if self.offline else None
            self.step = 0
            self.update_step()
            self.query_one("#guide-do", Button).focus()
        elif identity == "guide-explore":
            self.choose_experiment(inspect=True)
        elif identity == "guide-help":
            self.console.action_help()
        elif identity == "guide-close":
            self.finish(None)
        elif identity == "guide-back":
            self.flow, self.step = None, 0
            self.update_step()
            self.query_one("#guide-explore", Button).focus()
        elif identity in {"guide-next", "guide-previous"}:
            if identity == "guide-previous" and self.step == 0:
                self.flow = None
            else:
                self.step += 1 if identity == "guide-next" else -1
            self.update_step()
        elif identity == "guide-select":
            self.choose_experiment()
        elif identity == "guide-alternative":
            self.open_action(self.alternative)
        elif identity == "guide-do":
            action = self.steps[self.step][2]
            if self.flow == "research" and self.step == 1 and self.execution == "synthetic":
                action = "agent"
            self.open_action(action)
