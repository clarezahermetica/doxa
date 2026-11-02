"""Textual viewer: closing it never cancels a run owned by another client."""

import asyncio
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import UUID

from rich.text import Text
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import Resize
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from doxa.cli.activity import Operation, OperationDetails, operations, worker_observation
from doxa.cli.reference import ACTIONS
from doxa.core.config import Settings
from doxa.core.controller import Controller, RunBundle
from doxa.core.models import Claim, Evaluation, Experiment, ModelCall, Trajectory
from doxa.systems.research import branch_events


class ResearchConsole(App[None]):
    TITLE = "DOXA · Research Console"
    BINDINGS = [
        Binding("q", "quit", "Quit viewer"),
        Binding("r", "refresh", "Refresh ledger", show=False),
        Binding("n", "new", "New experiment", show=False),
        Binding("a", "agent", "Add agent", show=False),
        Binding("c", "review", "Review branch", show=False),
        Binding("s", "start", "Start run", show=False),
        Binding("x", "cancel", "Cancel run", show=False),
        Binding("m", "model", "Add model", show=False),
        Binding("i", "import_source", "Import evidence", show=False),
        Binding("w", "workspace", "Workspace", show=False),
        Binding("e", "export", "Export", show=False),
        Binding("f1", "help", "Help", priority=True),
        Binding("f2", "details", "Expand record", show=False),
        Binding("ctrl+j", "raw", "Raw record", show=False),
    ]
    CSS = """
    #runs { height: 5; }
    #filter-bar { height: 3; }
    #record-kind, #filter { width: 1fr; }
    #notice { height: 2; }
    #branch-picker, #filter { height: 3; }
    #tools, #activity-controls { height: 3; }
    #activity-pages { height: 1; }
    #activity-pages Button { height: 1; min-height: 1; }
    #action-menu, #activity-search { width: 1fr; }
    #activity-operations { height: 1fr; }
    #activity-pages Button { min-width: 10; }
    #activity-count { width: 1fr; }
    #timeline { display: none; }

    #tools Button { min-width: 12; width: 1fr; }
    #records { width: 1fr; height: 1fr; }
    #inspector { width: 45%; height: 1fr; border: none; }
    #records-layout { height: 1fr; }
    TabbedContent { height: 1fr; }
    """

    def __init__(self, data_dir: Path, *, show_guide: bool | None = None):
        super().__init__()
        self._persist_theme = False
        self.appearance_error = ""
        from doxa.cli.appearance import read_appearance

        try:
            saved_theme = read_appearance().get("theme")
            if saved_theme in self.available_themes:
                self.theme = saved_theme
            elif saved_theme is not None:
                self.appearance_error = (
                    "Saved theme is unavailable; using the default without replacing it."
                )
        except (ValueError, OSError):
            self.appearance_error = (
                "Appearance settings could not be read; existing file preserved."
            )
        self.controller = Controller(Settings(data_dir=data_dir))
        self._loading = False
        from doxa.cli.onboarding import guide_preferences

        self.offer_guide = (
            show_guide
            if show_guide is not None
            else guide_preferences().get("show_getting_started", True) is True
        )
        self.guide_location: tuple[str | None, int, str | None] = (None, 0, None)
        self.current_bundle: RunBundle | None = None
        self.observation = "unverified"
        self.uncertain = False
        self.activity_signature: object = None
        self.activity_rows: list[Operation] = []
        self.activity_map: dict[str, Operation] = {}
        self.activity_page = -1
        self.selected_operation: Operation | None = None

        self.ready = (data_dir / "ledger.sqlite3").is_file()
        self.workspace_error = ""
        if self.ready:
            try:
                self.controller.initialize()
            except (ValueError, OSError):
                self.ready = False
                self.workspace_error = "Workspace cannot be opened; W selects another workspace.\n"
        self.selected_record: Any = None
        self.record_map: dict[str, Any] = {}
        self.view_signature: object = None
        self.selected: UUID | None = None
        self.branch_id: UUID | None = None
        self.branch_options: tuple[UUID, ...] = ()
        self.cursor = 0
        self.run_ids: tuple[UUID, ...] = ()

    def watch_theme(self, theme: str) -> None:
        if not getattr(self, "_persist_theme", False):
            return
        from doxa.cli.appearance import save_theme

        try:
            save_theme(theme)
        except (OSError, ValueError):
            self.notify(
                "Theme applied to this viewer but could not be saved. "
                "Existing settings were preserved; check file permissions or settings format.",
                severity="error",
            )

    def compose(self) -> ComposeResult:
        yield Static(
            self.workspace_error + str(self.controller.settings.data_dir.resolve()),
            id="notice",
            markup=False,
        )
        yield DataTable(id="runs", cursor_type="row")
        yield Select(
            [("Select an experiment", "")], value="", allow_blank=False, id="branch-picker"
        )
        with Horizontal(id="tools"):
            yield Select([], prompt="Actions for this workspace", id="action-menu")
            yield Button("Open", id="action-open", disabled=True)
        with TabbedContent(initial="activity"):
            with TabPane("Activity", id="activity"):
                with Horizontal(id="activity-controls"):
                    yield Input(placeholder="Search complete branch history…", id="activity-search")
                yield DataTable(id="activity-operations", cursor_type="row")
                with Horizontal(id="activity-pages"):
                    yield Button("Earlier", id="activity-earlier")
                    yield Static("", id="activity-count")
                    yield Button("Later", id="activity-later")
                yield RichLog(wrap=True, markup=False, max_lines=500, id="timeline")
            with TabPane("Inspect", id="inspect"):
                with Horizontal(id="filter-bar"):
                    yield Select(
                        [
                            (name, name)
                            for name in (
                                "Claims",
                                "Criticism",
                                "Sources",
                                "Contexts",
                                "Agents",
                                "Models",
                                "Memory",
                                "Evaluations",
                                "Checkpoints",
                            )
                        ],
                        value="Claims",
                        allow_blank=False,
                        id="record-kind",
                    )
                    yield Input(placeholder="Filter records…", id="filter")
                with Horizontal(id="records-layout"):
                    yield DataTable(id="records", cursor_type="row")
                    yield TextArea(read_only=True, show_line_numbers=False, id="inspector")
        yield Footer()

    def on_mount(self) -> None:
        self._persist_theme = True
        if self.appearance_error:
            self.notify(self.appearance_error, severity="warning")
        self.run_column_keys = self.query_one("#runs", DataTable).add_columns(
            "Experiment", "State", "Kind"
        )
        self.render_activity()
        self.query_one("#records", DataTable).add_columns("Record", "State / assignment")
        if self.ready:
            self.action_refresh()
        self.update_actions()
        if self.offer_guide:
            self.call_after_refresh(self.action_guide)
        elif not self.ready:
            self.call_after_refresh(self.action_workspace)
        self.set_interval(0.75, self.poll)

    def action_refresh(self) -> None:
        if not self.ready:
            return
        runs = self.controller.list_runs()
        if not runs:
            self.query_one("#notice", Static).update(
                "No runs in this workspace. W: open an existing/recent workspace.\n"
                + str(self.controller.settings.data_dir.resolve())
            )
        self.run_ids = tuple(r.id for r in runs)
        table = self.query_one("#runs", DataTable)
        table.clear()
        for run in runs:
            exp = self.controller.ledger.get(run.experiment_id)
            assert isinstance(exp, Experiment)
            table.add_row(Text(exp.name), run.status, run.execution_kind, key=str(run.id))
        if self.selected is None and runs:
            self.selected = runs[-1].id
        if self.selected in self.run_ids:
            table.move_cursor(row=self.run_ids.index(self.selected))
        self.update_actions()
        self.poll()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id not in {"runs", "records", "activity-operations"}:
            return
        if event.data_table.id == "activity-operations":
            self.selected_operation = self.activity_map.get(str(event.row_key.value))
            if self.selected_operation:
                self.push_screen(OperationDetails(self.selected_operation, self.controller))
            return
        if event.data_table.id == "records":
            self.selected_record = self.record_map.get(str(event.row_key.value))
            self.show_record()
            self.update_actions()
            return
        self.selected_record = None
        self.selected_operation = None
        self.query_one("#inspector", TextArea).clear()
        self.selected = UUID(str(event.row_key.value))
        self.branch_id = None
        self.branch_options = ()
        self.activity_signature = None
        self.activity_page = -1
        self.current_bundle = None
        self.cursor = 0
        self.query_one("#timeline", RichLog).clear()
        self.poll()

    def poll(self) -> None:
        if not self.ready or len(self.screen_stack) > 1 or self._loading:
            return
        if self.selected is None:
            self.render_records([])
            return
        self._loading = True
        self.run_worker(self.read_bundle(), name="ledger-reader", exit_on_error=False)

    async def read_bundle(self) -> None:
        controller, selected = self.controller, self.selected
        try:
            if selected is None:
                return
            bundle = await asyncio.to_thread(controller.inspect, selected)
            observation = (
                await asyncio.to_thread(worker_observation, controller.settings.data_dir, selected)
                if bundle.run.status == "running"
                else "unowned"
            )
            branch = self.branch_id
            query = self.query_one("#activity-search", Input).value
            signature = (selected, branch, len(bundle.events), query)
            projected = None
            if signature != self.activity_signature:

                def project() -> list[Operation]:
                    exp = controller.ledger.get(bundle.run.experiment_id)
                    assert isinstance(exp, Experiment)
                    return operations(
                        branch_events(
                            list(bundle.events), branch or bundle.events[0].trajectory_id
                        ),
                        exp,
                        query,
                    )

                projected = await asyncio.to_thread(project)
            if (
                self.controller is controller
                and self.selected == selected
                and self.branch_id == branch
                and self.query_one("#activity-search", Input).value == query
            ):
                self.observation = observation
                if projected is not None:
                    self.activity_rows = projected
                    self.activity_signature = signature
                    self.render_activity()
                self.apply_bundle(bundle)
                if projected is not None:
                    self.render_activity()
        except (ValueError, KeyError, OSError):
            self.notify(
                "Ledger temporarily unavailable; persisted history will be reloaded.",
                severity="warning",
            )
        finally:
            self._loading = False

    def apply_bundle(self, bundle: RunBundle) -> None:
        branches = [p for e in bundle.events for p in e.payload if isinstance(p, Trajectory)]
        if self.branch_id is None:
            self.branch_id = next(p.id for p in branches if p.parent_id is None)
        identities = tuple(b.id for b in branches)
        if identities != self.branch_options:
            self.branch_options = identities
            picker = self.query_one("#branch-picker", Select)
            picker.set_options(
                [
                    (
                        Text(
                            "Main trajectory"
                            if b.parent_id is None
                            else f"Branch {i}: {b.intervention}"
                        ),
                        str(b.id),
                    )
                    for i, b in enumerate(branches)
                ]
            )
            picker.value = str(self.branch_id)
        events = branch_events(list(bundle.events), self.branch_id)
        self.current_bundle = bundle
        if bundle.run.id in self.run_ids:
            self.query_one("#runs", DataTable).update_cell(
                str(bundle.run.id), self.run_column_keys[1], bundle.run.status
            )
        local = {}
        for event in bundle.events:
            for record in event.payload:
                if isinstance(record, ModelCall):
                    local[record.call_id] = record
        self.uncertain = any(
            o["state"] == "uncertain" or (o["state"] == "in_flight" and self.observation != "owned")
            for o in bundle.accounting
        ) or any(
            c.status == "uncertain" or (c.status == "started" and self.observation != "owned")
            for c in local.values()
        )
        self.cursor = len(events)
        self.render_records(events)
        exp = self.controller.ledger.get(bundle.run.experiment_id)
        notice = self.query_one("#notice", Static)
        notice.styles.height = 3
        name = str(getattr(exp, "name", "Experiment"))
        limit = max(18, self.size.width - 20)
        name = name[: limit - 1] + "…" if len(name) > limit else name
        notice.update(
            f"{name} · {bundle.run.execution_kind}\n"
            f"{self.state_label()}{self.sync_status()}\n"
            f"{self.controller.settings.data_dir.resolve()}"
        )
        self.update_actions()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "action-menu":
            self.query_one("#action-open", Button).disabled = not isinstance(event.value, str)
            return
        if event.select.id == "record-kind":
            self.view_signature = None
            self.poll()
            return
        if (
            event.select.id == "branch-picker"
            and isinstance(event.value, str)
            and event.value
            and str(event.value) != str(self.branch_id)
        ):
            self.branch_id = UUID(str(event.value))
            self.activity_signature = None
            self.activity_page = -1
            self.cursor = 0
            self.query_one("#timeline", RichLog).clear()
            self.poll()

    def refreshed(self, changed: bool | None) -> None:
        if changed:
            self.action_refresh()

    def action_new(self, *, execution_kind: str | None = None) -> None:
        reason = self.unavailable_reason("new")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.screens import SetupScreen

        screen = SetupScreen(self.controller, "experiment", execution_kind=execution_kind)

        def saved(changed: bool | None) -> None:
            if changed and screen.created_run_id:
                self.select_experiment(screen.created_run_id)
            self.refreshed(changed)

        self.push_screen(screen, saved)

    def action_agent(self, *, create_new: bool = False) -> None:
        reason = self.unavailable_reason("agent")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.screens import SetupScreen
        from doxa.core.profiles import AgentDefinition

        definition = (
            self.selected_record
            if not create_new and isinstance(self.selected_record, AgentDefinition)
            else None
        )
        self.push_screen(SetupScreen(self.controller, "agent", definition), self.refreshed)

    def action_review(self) -> None:
        reason = self.unavailable_reason("review")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.screens import ReviewScreen

        if self.selected and self.branch_id:
            try:
                self.push_screen(
                    ReviewScreen(self.controller, self.selected, self.branch_id), self.refreshed
                )
            except ValueError:
                self.notify("Text review requires a research-debate task", severity="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "action-open":
            value = self.query_one("#action-menu", Select).value
            if isinstance(value, str):
                self.dispatch_action(value)
        elif event.button.id in {"activity-earlier", "activity-later"}:
            last = max(0, (len(self.activity_rows) - 1) // 100)
            current = last if self.activity_page == -1 else self.activity_page
            self.activity_page = max(
                0, min(last, current + (-1 if event.button.id == "activity-earlier" else 1))
            )
            self.render_activity()
        elif event.button.id == "new-experiment":
            self.action_new()
        elif event.button.id == "new-agent":
            self.action_agent()
        elif event.button.id == "review-branch":
            self.action_review()

    def action_model(self) -> None:
        reason = self.unavailable_reason("model")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.operations import ModelScreen
        from doxa.core.profiles import ModelProfile

        profile = self.selected_record if isinstance(self.selected_record, ModelProfile) else None
        self.push_screen(ModelScreen(self.controller, profile), self.refreshed)

    def action_import_source(self) -> None:
        reason = self.unavailable_reason("import_source")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.operations import ImportScreen

        if self.selected:
            self.push_screen(ImportScreen(self.controller, self.selected), self.refreshed)

    def action_start(self) -> None:
        reason = self.unavailable_reason("start")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.operations import StartScreen

        if self.selected:
            self.push_screen(StartScreen(self.controller, self.selected), self.refreshed)

    def action_preflight(self) -> None:
        from doxa.cli.research_tools import ResearchToolScreen

        if self.selected:
            self.push_screen(ResearchToolScreen(self.controller, "preflight", self.selected))

    def action_new_attempt(self) -> None:
        from doxa.cli.operations import AttemptScreen

        if self.selected:
            screen = AttemptScreen(self.controller, self.selected)

            def finished(saved: bool | None) -> None:
                if saved and screen.created_run_id:
                    self.select_experiment(screen.created_run_id)

            self.push_screen(screen, finished)

    def action_cancel(self) -> None:
        reason = self.unavailable_reason("cancel")
        if reason:
            self.notify(reason, severity="warning")
            return
        if self.selected:
            try:
                run = self.controller.inspect(self.selected).run
                if run.status not in {"configured", "running"}:
                    raise ValueError("Run is already terminal")
                self.controller.cancel(self.selected)
                self.action_refresh()
            except ValueError:
                self.notify("Only active runs can be cancelled.", severity="warning")

    def get_system_commands(self, screen: Screen[Any]) -> Iterable[SystemCommand]:
        for spec in ACTIONS:
            if not self.unavailable_reason(spec.action):
                yield SystemCommand(
                    spec.title, spec.description, getattr(self, "action_" + spec.action)
                )
        descriptions = {
            "Theme": "Change DOXA's color theme. Your selection is saved automatically.",
            "Quit": (
                "Close this viewer. Running experiments keep their own worker; history is retained."
            ),
            "Keys": "Show or hide keyboard help for the focused control.",
            "Screenshot": (
                "Save the visible terminal screen as an SVG image; it may contain research data."
            ),
        }
        for command in super().get_system_commands(screen):
            yield command._replace(help=descriptions.get(command.title, command.help))

    def action_workspace(self) -> None:
        from doxa.cli.workspace_screen import WorkspaceScreen

        self.push_screen(WorkspaceScreen(self.controller.settings.data_dir), self.open_workspace)

    def open_workspace(self, directory: Path | None) -> None:
        if directory is None:
            return
        from doxa.core.workspaces import remember_workspace

        try:
            controller = Controller(Settings(data_dir=directory))
            controller.initialize(allow_create=True)
            remember_workspace(directory)
            self.controller = controller
            self.ready = True
            self.selected = self.branch_id = None
            self.current_bundle = None
            self.selected_record = None
            self.selected_operation = None
            self.query_one("#inspector", TextArea).clear()
            self.activity_rows = []
            self.activity_signature = None
            self.activity_page = -1
            self.query_one("#activity-operations", DataTable).clear()
            self.branch_options = ()
            self.cursor = 0
            self.view_signature = None
            self.query_one("#timeline", RichLog).clear()
            self.action_refresh()
        except (OSError, ValueError):
            self.notify(
                "Cannot open workspace; check directory permissions and ledger.", severity="error"
            )

    def action_help(self) -> None:
        from doxa.cli.reference import CommandReference

        if isinstance(self.screen, CommandReference):
            self.screen.query_one("#reference-search", Input).focus()
            return
        self.push_screen(CommandReference(self), self.dispatch_action)

    def action_raw(self) -> None:
        from doxa.cli.inspectors import DetailScreen

        if self.query_one(TabbedContent).active == "activity" and self.selected_operation:
            self.push_screen(OperationDetails(self.selected_operation, self.controller, raw=True))
            return
        if self.selected_record is not None:
            self.push_screen(
                DetailScreen("Exact record", self.selected_record.model_dump_json(indent=2))
            )

    def action_export(self) -> None:
        reason = self.unavailable_reason("export")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.inspectors import ExportScreen

        if self.selected:
            self.push_screen(ExportScreen(self.controller, self.selected))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "activity-search":
            self.activity_page = -1
            self.poll()
        elif event.input.id == "filter":
            self.view_signature = None
            self.poll()

    def render_records(self, events: list[Any]) -> None:
        from doxa.core.models import Challenge, Checkpoint, ContextManifest, Memory, SourceDocument

        category = str(self.query_one("#record-kind", Select).value)
        query = self.query_one("#filter", Input).value.casefold()
        kinds: dict[str, type[Any]] = {
            "Claims": Claim,
            "Criticism": Challenge,
            "Sources": SourceDocument,
            "Contexts": ContextManifest,
            "Memory": Memory,
            "Evaluations": Evaluation,
            "Checkpoints": Checkpoint,
        }
        if category == "Models":
            records: list[Any] = list(self.controller.configuration().profiles)
        elif category == "Agents":
            records = []
            if self.selected:
                experiment = self.controller.ledger.get(
                    self.controller.inspect(self.selected).run.experiment_id
                )
                records = list(getattr(experiment, "agents", ()))
            records += list(self.controller.configuration().agents)
        else:
            records = [p for e in events for p in e.payload if isinstance(p, kinds[category])]
        signature = (category, query, tuple(p.model_dump_json() for p in records[-1000:]))
        if signature == self.view_signature:
            return
        self.view_signature = signature
        self.record_map = {}
        table = self.query_one("#records", DataTable)
        table.clear()
        from doxa.cli.inspectors import record_summary

        matches = [(record, *record_summary(record)) for record in records]
        if query:
            matches = [
                item
                for item in matches
                if query in (item[1] + " " + item[2] + " " + item[0].model_dump_json()).casefold()
            ]
        for record, label, state in matches[-1000:]:
            identity = str(record.id)
            self.record_map[identity] = record
            table.add_row(Text(label[:120]), Text(state[:100]), key=identity)
        if self.selected_record is not None and str(self.selected_record.id) not in self.record_map:
            self.selected_record = None
            self.query_one("#inspector", TextArea).clear()

    def show_record(self) -> None:
        from doxa.cli.inspectors import describe_record

        if self.selected_record:
            self.query_one("#inspector", TextArea).load_text(
                describe_record(self.controller, self.selected_record)
            )

    def action_compare(self) -> None:
        reason = self.unavailable_reason("compare")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.research_tools import ResearchToolScreen

        if self.selected:
            self.push_screen(ResearchToolScreen(self.controller, "compare", self.selected))

    def action_memory(self) -> None:
        reason = self.unavailable_reason("memory")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.research_tools import ResearchToolScreen

        if self.selected:
            self.push_screen(ResearchToolScreen(self.controller, "memory", self.selected))

    def action_connection(self) -> None:
        reason = self.unavailable_reason("connection")
        if reason:
            self.notify(reason, severity="warning")
            return
        from doxa.cli.research_tools import ResearchToolScreen

        self.push_screen(ResearchToolScreen(self.controller, "connection", self.selected))

    def sync_status(self) -> str:
        if any(
            p.casefold().startswith("onedrive") for p in self.controller.settings.data_dir.parts
        ):
            return " · OneDrive sync: W for precautions"
        return ""

    def state_label(self) -> str:
        if not self.ready:
            return "No workspace selected"
        if self.current_bundle is None:
            return "Select an experiment"
        state = self.current_bundle.run.status
        if state == "configured" and self.current_bundle.run.execution_kind == "live":
            if self.unavailable_reason("start"):
                return "configured · model/task setup unavailable; see Inspect and Help"
        if self.uncertain:
            return state + " · uncertain operation; inspect Recovery details"
        if state == "running":
            return (
                "running · local worker owned"
                if self.observation == "owned"
                else "historical running · worker activity unverified"
            )
        return state

    def unavailable_reason(self, action: str) -> str:
        if action in {"workspace", "help", "guide"}:
            return ""
        if not self.ready:
            return "Open or create a workspace first"
        if action in {"new", "agent", "model", "inspect", "connection"}:
            return ""
        if action == "details":
            return "" if self.selected_record is not None else "Select a record in Inspect first"
        if self.selected is None:
            return "Select an experiment first"
        bundle = self.current_bundle
        if bundle is None or bundle.run.id != self.selected:
            bundle = self.controller.inspect(self.selected)
        if action in {"start", "import_source"}:
            exp = self.controller.ledger.get(bundle.run.experiment_id)
            if not isinstance(exp, Experiment) or exp.task is None:
                return "This legacy task uses CLI operations; see Help for run-task/inspection."
        if action == "start":
            if bundle.run.status != "configured":
                if bundle.run.status == "running":
                    return "This run is already running. Follow Activity; do not start it again."
                return (
                    f"This run is {bundle.run.status}. Choose a configured run "
                    "or create new research. "
                    "Earlier calls are not replayed."
                )
            if bundle.run.execution_kind == "live":
                exp = self.controller.ledger.get(bundle.run.experiment_id)
                assert isinstance(exp, Experiment)
                if any(not a.model_profile_id or not a.model for a in exp.agents):
                    return "Model assignment missing. Inspect Agents/Models before live inference."
                report = self.controller.validate_configuration()
                if not report.valid:
                    return (
                        "Model configuration unsupported/unavailable. "
                        "Inspect Models and doctor --json."
                    )
        if action == "new_attempt":
            if bundle.run.status in {"configured", "running"}:
                return "Finish or cancel this attempt before configuring another"
            exp = self.controller.ledger.get(bundle.run.experiment_id)
            if not isinstance(exp, Experiment) or not exp.task:
                return "This operation requires a research experiment"
        if action == "import_source" and bundle.run.status != "configured":
            return "Import evidence before starting this experiment"
        if action == "cancel" and bundle.run.status not in {"configured", "running"}:
            return "This run is already terminal"
        if action == "review":
            exp = self.controller.ledger.get(bundle.run.experiment_id)
            if (
                not isinstance(exp, Experiment)
                or exp.task is None
                or exp.task.task_type != "research_debate"
            ):
                return "Text review requires a research-debate experiment"
            if self.branch_id is None:
                return "Wait for the selected trajectory to load"
        if action == "compare":
            branches = [p for e in bundle.events for p in e.payload if isinstance(p, Trajectory)]
            if len(branches) < 2:
                return "Create a second trajectory before comparing; text forks are in Review"
        if action == "memory":
            exp = self.controller.ledger.get(bundle.run.experiment_id)
            if not isinstance(exp, Experiment) or not exp.agents:
                return "This experiment has no participants for a memory query"
        if action == "recovery" and not (
            self.uncertain or bundle.run.status in {"running", "failed", "cancelled"}
        ):
            return "No interrupted or uncertain operation to inspect"
        return ""

    def update_actions(self) -> None:
        options = [
            (spec.title, spec.action)
            for spec in ACTIONS
            if not self.unavailable_reason(spec.action)
        ]
        picker = self.query_one("#action-menu", Select)
        previous = picker.value
        signature = tuple(options)
        if getattr(self, "action_signature", None) != signature:
            picker.set_options(options)
            if previous in [value for _, value in options]:
                picker.value = previous
            self.action_signature = signature

    def dispatch_action(self, action: str | None) -> None:
        if action is None:
            if not self.ready and len(self.screen_stack) == 1:
                self.action_workspace()
            return
        reason = self.unavailable_reason(action)
        if reason:
            self.notify(reason, severity="warning")
            return
        getattr(self, "action_" + action)()

    def select_experiment(self, identity: UUID) -> None:
        self.selected = identity
        self.branch_id = None
        self.current_bundle = None
        self.selected_record = self.selected_operation = None
        self.branch_options = ()
        self.activity_signature = self.view_signature = None
        self.activity_page = -1
        self.action_refresh()

    def action_guide(self) -> None:
        from doxa.cli.onboarding import GettingStarted

        for screen in self.screen_stack:
            if isinstance(screen, GettingStarted):
                # Wait for the reference/palette's own dismissal before unwinding children.
                self.call_after_refresh(screen.pop_until_active)
                return
        self.push_screen(GettingStarted(self), self.dispatch_action)

    def can_guide_start(self) -> bool:
        return bool(
            self.selected
            and not self.unavailable_reason("start")
            and self.controller.inspect(self.selected).run.execution_kind == "synthetic"
        )

    def action_inspect(self) -> None:
        self.query_one(TabbedContent).active = "inspect"
        self.query_one("#record-kind", Select).focus()
        self.poll()

    def action_recovery(self) -> None:
        from doxa.cli.inspectors import DetailScreen

        if not self.selected:
            return
        bundle = self.controller.inspect(self.selected)
        text = f"""Persisted state: {bundle.run.status}
Local ownership observation: {self.observation}
This is not proof of a live remote job. Closing a viewer does not cancel its worker.

No calls are replayed. No reservation is automatically released.
Cancel an orphaned running run explicitly, then recover after its worker exits.
Unknown cost remains held. Local holds require a stopped-process confirmation and evidence.

System shell examples (do not paste into the palette):
doxa run cancel {self.selected}
doxa recover {self.selected}
doxa doctor --json

Exact accounting (unknown is null):
"""

        if not bundle.accounting:
            text += "No paid-operation reservations recorded for this run."
        for item in bundle.accounting:
            text += (
                "\n"
                + "\n".join(
                    str(key).replace("_", " ") + ": " + ("unknown" if value is None else str(value))
                    for key, value in item.items()
                )
                + "\n"
            )
        text += "\nA held amount is a spending ceiling, not evidence of a charge. "
        text += "Confirm the actual outcome and bill before explicit reconciliation."
        self.push_screen(DetailScreen("Recovery details", text))

    def render_activity(self) -> None:
        table = self.query_one("#activity-operations", DataTable)
        previous = table.cursor_row
        last = max(0, (len(self.activity_rows) - 1) // 100)
        page = last if self.activity_page == -1 else min(last, self.activity_page)
        start = page * 100
        self.activity_map = {r.key: r for r in self.activity_rows[start : start + 100]}
        table.clear(columns=True)
        usable = max(40, self.size.width - 12)
        widths = [8, max(9, usable // 6), max(12, usable // 4), 0, max(13, usable // 5)]
        widths[3] = max(8, usable - sum(widths))
        for title, width in zip(
            ("Time", "Actor", "Operation", "Result", "Origin"), widths, strict=True
        ):
            table.add_column(title, width=width)
        kind = self.current_bundle.run.execution_kind if self.current_bundle else ""
        for row in self.activity_map.values():
            origin = ", ".join(row.origins)
            if kind == "synthetic" and any(
                p.kind in {"claim", "council_message"}
                and str(getattr(p, "provenance", None)) == "imported_source"
                for event in row.events
                for p in event.payload
            ):
                origin = origin.replace("imported", "synthetic")
            table.add_row(
                f"{row.events[0].timestamp:%H:%M:%S}",
                Text(row.actor),
                Text(row.action[:90]),
                Text(row.result[:160]),
                Text(origin),
                key=row.key,
            )
        table.move_cursor(row=min(previous, max(0, len(self.activity_map) - 1)))
        self.query_one("#activity-earlier", Button).disabled = page == 0
        self.query_one("#activity-later", Button).disabled = page == last
        self.query_one("#activity-count", Static).update(
            f"{start + 1 if self.activity_rows else 0:,}–{start + len(self.activity_map):,} / "
            f"{len(self.activity_rows):,} operations · Enter expands"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "activity-operations" and event.row_key:
            self.selected_operation = self.activity_map.get(str(event.row_key.value))

    def action_details(self) -> None:
        from doxa.cli.inspectors import DetailScreen, describe_record

        if self.selected_record is not None:
            self.push_screen(
                DetailScreen(
                    "Record detail", describe_record(self.controller, self.selected_record)
                )
            )

    def on_resize(self, event: Resize) -> None:
        if self.query("#runs"):
            self.query_one("#runs", DataTable).styles.height = 3 if event.size.height < 30 else 5
        if (
            self.query("#activity-count")
            and self.query_one("#activity-operations", DataTable).is_mounted
        ):
            self.render_activity()
