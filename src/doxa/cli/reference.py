"""One action registry feeds the palette, contextual menu and searchable F1 reference."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, TextArea
from typer import _click as click
from typer.core import TyperGroup, TyperOption

REFERENCE_CATEGORIES = (
    "Common research tasks",
    "Getting started",
    "Experiments and runs",
    "Agents and models",
    "Evidence and retrieval",
    "Claims and revision",
    "Evaluation and export",
    "Workspace and maintenance",
    "Advanced CLI commands",
    "Application and widget shortcuts",
    "All commands",
)


@dataclass(frozen=True)
class ActionSpec:
    action: str
    title: str
    description: str
    category: str
    required: str = "No shell arguments."


ACTIONS = (
    ActionSpec(
        "details",
        "Expand record",
        "Expand a selected record; Ctrl+J retains exact JSON.",
        "Research",
        required="Selected record in Inspect. No mutation.",
    ),
    ActionSpec(
        "workspace",
        "Select workspace",
        "Open/create a workspace; existing histories stay separate.",
        "Workspace",
        required="Existing ledger directory, or a new empty directory with explicit creation.",
    ),
    ActionSpec(
        "new",
        "Create experiment",
        "Create a new offline or explicitly authorized model-backed experiment.",
        "Experiments",
        required="Name, question, agent template names/counts. Composition is pinned on creation.",
    ),
    ActionSpec(
        "agent",
        "Add agent template",
        "Create/version an agent template; changes affect future experiments.",
        "Configuration",
        required="Name, role, instructions; optional existing model-profile assignment.",
    ),
    ActionSpec(
        "model",
        "Choose model and connection",
        "Search the offline model catalog or enter a custom ID, then choose a connection.",
        "Configuration",
        required=(
            "Profile name, exact served ID and connection; "
            "unsupported transports register notes only."
        ),
    ),
    ActionSpec(
        "inspect",
        "Inspect research records",
        "Inspect claims, criticism, contexts, agents, models and evaluations.",
        "Research",
        required="Open workspace; choose category and record. No mutation.",
    ),
    ActionSpec(
        "import_source",
        "Import evidence",
        "Import evidence into the selected configured experiment.",
        "Research",
        required="Selected configured research-debate experiment; local document path.",
    ),
    ActionSpec(
        "start",
        "Start selected run",
        "Start a configured run through the existing authorization form.",
        "Execution",
        required="Configured task. Synthetic: no paid gates. Live: explicit authorization.",
    ),
    ActionSpec(
        "preflight",
        "Inspect launch preflight",
        "Inspect pinned participants, limits, authorization requirements and blockers "
        "without network calls.",
        "Execution",
        required="Selected research run. Eligibility does not verify inference.",
    ),
    ActionSpec(
        "new_attempt",
        "Create another run attempt",
        "Reuse an immutable experiment or declare a changed criticism strategy; "
        "earlier runs remain intact.",
        "Execution",
        required="Finished research run; import evidence into the new attempt.",
    ),
    ActionSpec(
        "cancel",
        "Cancel selected run",
        "Record cancellation; remote execution/billing can remain uncertain.",
        "Execution",
        required="Configured/running run. Local cancellation does not prove remote termination.",
    ),
    ActionSpec(
        "review",
        "Review branch and revise claims",
        "Propose revisions, respond to criticism, evaluate, checkpoint or fork text analysis.",
        "Research",
        required="Research-debate trajectory; operation, target, actor, text and evidence.",
    ),
    ActionSpec(
        "compare",
        "Compare trajectories",
        "Compare persisted experiment branches; no model inference.",
        "Research",
        required="Selected run; two trajectories in the existing comparison form.",
    ),
    ActionSpec(
        "memory",
        "Query eligible memory",
        "Query eligible participant memories through existing permissions.",
        "Research",
        required="Selected run; participant and query in the existing retrieval form.",
    ),
    ActionSpec(
        "connection",
        "Check connection metadata",
        "Explicit metadata discovery only; never verifies generation.",
        "Configuration",
        required="Existing profile and explicit metadata-disclosure authorization; no inference.",
    ),
    ActionSpec(
        "export",
        "Export experiment history",
        "Export exact history to a new file without overwriting another export.",
        "Results",
        required="Selected run and new destination file path.",
    ),
    ActionSpec(
        "recovery",
        "Recovery details",
        "Inspect worker ownership, uncertain calls and guarded recovery instructions.",
        "Execution",
        required="Interrupted/uncertain run. Viewing does not reconcile or release holds.",
    ),
    ActionSpec(
        "guide",
        "Getting Started",
        "Open research, configure an experiment, try an offline demo or browse help.",
        "Help",
    ),
    ActionSpec(
        "help",
        "Browse commands and help",
        "Search terminal actions, shortcuts, widget navigation and registered CLI commands.",
        "Help",
    ),
)


@dataclass(frozen=True)
class ReferenceEntry:
    title: str
    category: str
    description: str
    detail: str
    action: str | None = None
    unavailable: str = ""
    callback: Callable[[], Any] | None = None


def bindings_for(cls: type[Any]) -> dict[str, Binding]:
    bindings = {}
    for base in reversed(cls.__mro__):
        for binding in Binding.make_bindings(base.__dict__.get("BINDINGS", [])):
            bindings[binding.key] = binding
    return bindings


def cli_reference() -> Iterator[ReferenceEntry]:
    from typer.main import get_command

    from doxa.cli.main import app

    def visit(command: click.Command, path: str) -> Iterator[ReferenceEntry]:
        required = [p for p in command.params if p.required]
        args = " ".join(
            (p.opts[0] + " " if isinstance(p, TyperOption) else "") + (p.name or "VALUE").upper()
            for p in required
        )
        example = (path + " " + args).strip()
        description = (
            command.get_short_help_str()
            or {
                "doxa": "Open the research console, or choose a command for scripting.",
                "doxa experiment": "Create a configured experiment without starting inference.",
                "doxa run": "Start, follow or cancel an experiment using its recorded run ID.",
            }.get(path)
            or path.removeprefix("doxa ").replace("-", " ").capitalize() + "."
        )
        detail = (
            "System shell only; do not type this into the command palette.\n"
            f"Required: {args or 'none'}\nExample: {example}\n"
            "Arguments above are placeholders. Use --data-dir PATH where supported.\n"
            "Paid inference/network disclosure require separate explicit authorization.\n"
            "Unknown cost is not zero. GUI commands remain archived.\n"
            "Availability can differ in a terminal-only package.\n\n"
            + "\n".join(
                (
                    "Option " + "/".join(p.opts)
                    if isinstance(p, TyperOption)
                    else "Argument " + (p.name or "VALUE")
                )
                + f" · type: {p.type} · required: {p.required}"
                + (" · " + str(getattr(p, "help", "") or ""))
                for p in command.params
            )
        )
        yield ReferenceEntry(path, "Shell CLI", description, detail)
        if isinstance(command, TyperGroup):
            for name, child in sorted(command.commands.items()):
                yield from visit(child, path + " " + name)

    yield from visit(get_command(app), "doxa")


def command_reference(console: Any) -> list[ReferenceEntry]:
    entries = []
    for spec in ACTIONS:
        reason = console.unavailable_reason(spec.action)
        entries.append(
            ReferenceEntry(
                spec.title,
                spec.category,
                spec.description,
                f"In-application action.\nAvailability: {reason or 'available'}\nRequired: "
                + spec.required
                + (
                    f"\nExample: Ctrl+P → {spec.title}\n\n{spec.description}\n"
                    "Research changes preserve earlier versions.\n"
                    "Synthetic output is not live inference or independent verification."
                ),
                spec.action,
                reason,
            )
        )
    for key, binding in bindings_for(type(console)).items():
        entries.append(
            ReferenceEntry(
                key,
                "Application shortcuts",
                binding.description or binding.action,
                (
                    f"Keyboard shortcut: {key}\n"
                    f"Press {key} to {binding.description or binding.action}.\n"
                    "Availability depends on focus and the selected experiment.\n"
                    "Editable fields receive ordinary letters as text.\n"
                    "Tab/Shift+Tab move focus; Escape closes Help and guide."
                ),
            )
        )
    from textual.containers import VerticalScroll
    from textual.widgets import Checkbox, Collapsible, Select, SelectionList, TabbedContent

    from doxa.cli.activity import OperationDetails
    from doxa.cli.inspectors import DetailScreen, ExportScreen
    from doxa.cli.onboarding import ExperimentPicker, GettingStarted
    from doxa.cli.operations import ImportScreen, ModelScreen, StartScreen
    from doxa.cli.research_tools import ResearchToolScreen
    from doxa.cli.screens import ReviewScreen, SetupScreen
    from doxa.cli.workspace_screen import WorkspaceScreen

    for widget in (
        DataTable,
        Input,
        TextArea,
        Select,
        TabbedContent,
        Button,
        Checkbox,
        Collapsible,
        SelectionList,
        VerticalScroll,
        CommandReference,
        OperationDetails,
        GettingStarted,
        ExperimentPicker,
        DetailScreen,
        ExportScreen,
        ImportScreen,
        ModelScreen,
        StartScreen,
        ResearchToolScreen,
        ReviewScreen,
        SetupScreen,
        WorkspaceScreen,
    ):
        name = {
            "DataTable": "Tables",
            "Input": "Text fields",
            "TextArea": "Text panels",
            "Select": "Selection menus",
            "TabbedContent": "Tabs",
            "Button": "Buttons",
            "Checkbox": "Checkboxes",
            "Collapsible": "Expandable sections",
            "SelectionList": "Multiple-choice lists",
            "VerticalScroll": "Scrollable panels",
            "CommandReference": "Help",
            "OperationDetails": "Activity details",
            "GettingStarted": "Getting Started",
            "ExperimentPicker": "Experiment selection",
            "DetailScreen": "Record details",
            "ExportScreen": "Export",
            "ImportScreen": "Evidence import",
            "ModelScreen": "Model setup",
            "StartScreen": "Run launch",
            "ResearchToolScreen": "Research tools",
            "ReviewScreen": "Branch review",
            "SetupScreen": "Experiment and agent setup",
            "WorkspaceScreen": "Workspace selection",
        }.get(widget.__name__, widget.__name__)
        for key, binding in bindings_for(widget).items():
            entries.append(
                ReferenceEntry(
                    f"{name}: {key}",
                    "Focused widget",
                    binding.description or binding.action,
                    (
                        f"Only while {name.lower()} has focus.\n"
                        f"{binding.description or binding.action}\n"
                        f"Example: focus with Tab, then press {key}.\n"
                        "Read-only fields support navigation. "
                        "Editing bindings do not modify history."
                    ),
                )
            )
    titles = {e.title for e in entries}
    for command in console.get_system_commands(console.screen):
        if command.title not in titles:
            entries.append(
                ReferenceEntry(
                    command.title,
                    "Application commands",
                    command.help,
                    (
                        "Theme\n\nChange DOXA's color theme.\n\n"
                        "Press Ctrl+P, select Theme, and choose a color scheme.\n\n"
                        "Your selection is saved automatically.\n\n"
                        "Open action opens the same theme chooser. No model call is made."
                        if command.title == "Theme"
                        else f"{command.title}\n\n{command.help}\n\n"
                        f"Press Ctrl+P and select {command.title}, or choose Open action here."
                    ),
                    callback=command.callback,
                )
            )
    entries.extend(cli_reference())
    categories = {
        "workspace": "Workspace and maintenance",
        "new": "Experiments and runs",
        "start": "Experiments and runs",
        "cancel": "Experiments and runs",
        "preflight": "Experiments and runs",
        "new_attempt": "Experiments and runs",
        "recovery": "Workspace and maintenance",
        "agent": "Agents and models",
        "model": "Agents and models",
        "connection": "Agents and models",
        "import_source": "Evidence and retrieval",
        "memory": "Evidence and retrieval",
        "inspect": "Claims and revision",
        "details": "Claims and revision",
        "review": "Claims and revision",
        "compare": "Evaluation and export",
        "export": "Evaluation and export",
        "guide": "Getting started",
        "help": "Getting started",
    }
    from dataclasses import replace

    entries = [
        replace(
            e,
            category=categories.get(
                e.action or "",
                "Advanced CLI commands"
                if e.category == "Shell CLI"
                else "Application and widget shortcuts",
            ),
        )
        for e in entries
    ]
    order = REFERENCE_CATEGORIES[1:]
    return sorted(entries, key=lambda entry: (order.index(entry.category), entry.title.casefold()))


class CommandReference(ModalScreen[str | None]):
    BINDINGS = [("escape", "close", "Close reference")]
    CSS = """
    CommandReference { align: center middle; }
    #reference-dialog { width: 96%; height: 26; max-height: 96%; background: $surface; }
    #reference-list { height: 8; min-height: 3; }
    #reference-text { height: 1fr; min-height: 4; border: none; }
    #reference-buttons { height: 3; }
    """

    def __init__(self, console: Any):
        super().__init__()
        self.entries = command_reference(console)
        self.matches = self.entries
        self.current: ReferenceEntry | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="reference-dialog"):
            yield Label("Help · terminal actions and shell reference", id="reference-title")
            yield Input(
                placeholder="Search names, arguments, shortcuts, limitations…",
                id="reference-search",
            )
            yield Select(
                [(c, c) for c in REFERENCE_CATEGORIES],
                value=REFERENCE_CATEGORIES[0],
                allow_blank=False,
                id="reference-category",
            )
            yield DataTable(id="reference-list", cursor_type="row")
            yield TextArea(read_only=True, id="reference-text")
            with Horizontal(id="reference-buttons"):
                yield Button("Open action", id="reference-run", disabled=True)
                yield Button("Getting Started", id="reference-guide")
                yield Button("Close", id="reference-close")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("Category", width=20)
        table.add_column("Command", width=24)
        table.add_column("Description / availability", width=max(24, self.size.width - 54))
        self.update_list()
        self.query_one(Input).focus()

    def update_list(self) -> None:
        query = self.query_one(Input).value.casefold()
        category = self.query_one("#reference-category", Select).value
        self.matches = [
            e
            for e in self.entries
            if (
                bool(query)
                or category == "All commands"
                or e.category == category
                or (
                    category == "Common research tasks"
                    and (e.action is not None or e.callback is not None)
                )
            )
            and query
            in (e.title + " " + e.category + " " + e.description + " " + e.detail).casefold()
        ]
        table = self.query_one(DataTable)
        table.clear()
        for i, e in enumerate(self.matches):
            table.add_row(e.category, e.title, (e.unavailable or e.description)[:100], key=str(i))
        table.styles.height = min(8, max(3, len(self.matches) + 1))
        self.query_one("#reference-dialog").styles.height = 18 + min(
            8, max(3, len(self.matches) + 1)
        )
        self.query_one("#reference-title", Label).update(
            f"Help · {len(self.matches):,} matches · shell entries are reference only"
        )
        self.current = self.matches[0] if self.matches else None
        self.show_entry()

    def show_entry(self) -> None:
        self.query_one("#reference-text", TextArea).load_text(
            self.current.detail
            + (
                "\n\nUnavailable: " + self.current.unavailable
                if self.current.unavailable
                else "\n\nReference only: use the invocation described above."
                if not (self.current.action or self.current.callback)
                else ""
            )
            if self.current
            else "No commands match. Clear the search to browse categories."
        )
        self.query_one("#reference-run", Button).disabled = not (
            self.current
            and (self.current.action or self.current.callback)
            and not self.current.unavailable
        )
        self.query_one("#reference-run", Button).label = (
            "Reference only"
            if self.current and not (self.current.action or self.current.callback)
            else "Open action"
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if self.is_mounted and self.query_one(DataTable).columns:
            self.update_list()

    def on_input_changed(self) -> None:
        if self.is_mounted and self.query_one(DataTable).columns:
            self.update_list()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and int(str(event.row_key.value)) < len(self.matches):
            self.current = self.matches[int(str(event.row_key.value))]
            self.show_entry()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.query_one("#reference-text", TextArea).focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reference-close":
            self.dismiss(None)
        elif event.button.id == "reference-guide":
            self.dismiss("guide")
        elif self.current and self.current.action and not self.current.unavailable:
            self.dismiss(self.current.action)
        elif self.current and self.current.callback and not self.current.unavailable:
            callback = self.current.callback
            self.dismiss(None)
            self.app.call_after_refresh(callback)
