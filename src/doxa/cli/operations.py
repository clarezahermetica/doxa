"""Local terminal operations; worker lifetime is independent of the viewer."""

import base64
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select

from doxa.cli.model_setup import ModelScreen as ModelScreen
from doxa.cli.navigation import ClientModal
from doxa.core.controller import Controller
from doxa.core.profiles import ModelProfile
from doxa.core.workbench import ImportDocument, import_document


def start_offline(controller: Controller, run_id: UUID) -> subprocess.Popen[bytes]:
    if controller.inspect(run_id).run.execution_kind != "synthetic":
        raise ValueError("Offline quick start requires a synthetic run")
    return start_worker(controller, run_id)


def start_worker(
    controller: Controller,
    run_id: UUID,
    *,
    authorize_paid: bool = False,
    authorize_external: bool = False,
    upper_bound: str | None = None,
) -> subprocess.Popen[bytes]:
    run = controller.inspect(run_id).run
    if run.status != "configured":
        raise ValueError("Only configured runs may start")
    from decimal import Decimal

    from doxa.core.preflight import authorize

    authorize(
        controller,
        run_id,
        paid=authorize_paid,
        external=authorize_external,
        upper_bound=Decimal(upper_bound) if upper_bound else None,
    )
    extra = []
    if authorize_paid:
        extra.append("--authorize-paid")
    if authorize_external:
        extra.append("--authorize-external")
    if upper_bound:
        extra += ["--upper-bound", upper_bound]
    directory = controller.settings.data_dir / "worker-logs"
    directory.mkdir(exist_ok=True)
    # Fixed Python entry point with separate argv, no shell interpolation.
    with (directory / f"{run_id}.log").open("ab") as stream:
        return subprocess.Popen(
            (
                [sys.executable, "--cli"]
                if getattr(sys, "frozen", False)
                else [sys.executable, "-c", "from doxa.cli.main import app; app()"]
            )
            + [
                "run",
                "start",
                str(run_id),
                "--data-dir",
                str(controller.settings.data_dir.resolve()),
            ]
            + extra,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            creationflags=0x08000000 | 0x200 if sys.platform == "win32" else 0,
            start_new_session=sys.platform != "win32",
        )


class ImportScreen(ClientModal[bool]):
    CSS = """
    ImportScreen { align: center middle; }
    #model-dialog { width: 85%; height: 90%; padding: 1 2; }
    """

    def __init__(self, controller: Controller, run_id: UUID):
        super().__init__()
        self.controller, self.run_id = controller, run_id

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="model-dialog"):
            yield Label("Import shared evidence into the configured run (up to 10 MB)")
            yield Input(placeholder="Local TXT / Markdown / JSON / PDF / DOCX path", id="file")
            yield Label("", id="import-error")
            yield Button("Import", id="import-save")
            yield Button("Cancel", id="import-cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-cancel":
            self.dismiss(False)
        elif event.button.id == "import-save":
            import asyncio

            try:
                path = Path(self.query_one("#file", Input).value).expanduser()
                if path.stat().st_size > 10_000_000:
                    raise ValueError("File too large")
                command = ImportDocument(
                    filename=path.name,
                    data_base64=base64.b64encode(path.read_bytes()).decode(),
                    idempotency_key=str(uuid4()),
                )
                await asyncio.to_thread(import_document, self.controller, self.run_id, command)
                self.dismiss(True)
            except (OSError, ValueError):
                self.query_one("#import-error", Label).update(
                    "Import rejected: check path, format, size and configured-run state."
                )


class StartScreen(ClientModal[bool]):
    CSS = ImportScreen.CSS.replace("ImportScreen", "StartScreen")

    def __init__(self, controller: Controller, run_id: UUID):
        super().__init__()
        self.controller, self.run_id = controller, run_id

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="model-dialog"):
            yield Label("Launch selected experiment in an independent worker")
            from doxa.core.preflight import format_preflight, preflight

            yield Label(
                format_preflight(preflight(self.controller, self.run_id)),
                id="start-preflight",
                markup=False,
            )
            yield Label(
                "Model-backed runs use configured connections. Remote calls require explicit "
                "context disclosure, paid-call authorization and spending limits.",
                id="start-description",
            )
            yield Checkbox(
                "Authorize disclosure of permitted context to remote endpoints", id="start-external"
            )
            yield Checkbox("Authorize paid inference within configured ceilings", id="start-paid")
            yield Input(placeholder="Complete remote per-attempt cost bound USD", id="start-bound")
            yield Label("", id="start-error")
            yield Button("Start experiment", id="start-save")
            yield Button("Cancel", id="start-close")

    def on_mount(self) -> None:
        if self.controller.inspect(self.run_id).run.execution_kind == "synthetic":
            self.query_one("#start-description", Label).update(
                "Offline synthetic demonstration · no live model inference or paid calls."
            )
            for identity in ("#start-external", "#start-paid", "#start-bound"):
                self.query_one(identity).display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-close":
            self.dismiss(False)
        elif event.button.id == "start-save":
            try:
                from doxa.core.models import Experiment
                from doxa.storage.configurations import ConfigurationStore

                run = self.controller.inspect(self.run_id).run
                experiment = self.controller.ledger.get(run.experiment_id)
                assert isinstance(experiment, Experiment)
                profiles = [
                    ConfigurationStore(self.controller.settings.database_path).get(
                        "profile", a.model_profile_id, a.model_profile_version
                    )
                    for a in experiment.agents
                    if a.model_profile_id
                ]
                if run.execution_kind == "live" and len(profiles) != len(experiment.agents):
                    raise ValueError("Every live participant requires a model profile")
                paid = self.query_one("#start-paid", Checkbox).value
                external = self.query_one("#start-external", Checkbox).value
                bound = self.query_one("#start-bound", Input).value or None
                if run.execution_kind == "live" and any(
                    isinstance(p, ModelProfile) and not p.local for p in profiles
                ):
                    if not (paid and external and bound):
                        raise ValueError("Remote inference requires authorization and a cost bound")
                start_worker(
                    self.controller,
                    self.run_id,
                    authorize_paid=paid,
                    authorize_external=external,
                    upper_bound=bound,
                )
                self.dismiss(True)
            except (OSError, ValueError):
                self.query_one("#start-error", Label).update(
                    "Launch rejected: check authorizations, cost bound and configured-run state."
                )


class AttemptScreen(ClientModal[bool]):
    CSS = ImportScreen.CSS.replace("ImportScreen", "AttemptScreen")

    def __init__(self, controller: Controller, run_id: UUID):
        super().__init__()
        self.controller, self.run_id = controller, run_id
        self.created_run_id: UUID | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="model-dialog"):
            yield Label("Create another attempt; preserve all earlier runs")
            yield Label(
                "Import evidence into the new attempt before launch. "
                "Comparison checks source hashes; equal configuration alone is insufficient."
            )
            yield Select(
                [
                    ("Same immutable experiment", "same"),
                    ("Condition: evidence gaps", "evidence_gaps"),
                    ("Condition: counterexamples", "counterexamples"),
                    ("Condition: source conflicts", "source_conflicts"),
                ],
                value="same",
                allow_blank=False,
                id="attempt-condition",
            )
            yield Label("", id="attempt-error")
            yield Button("Create configured attempt", id="attempt-save")
            yield Button("Cancel", id="attempt-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "attempt-cancel":
            self.dismiss(False)
        elif event.button.id == "attempt-save":
            from typing import Any, cast

            from doxa.core.attempts import new_attempt

            condition = self.query_one("#attempt-condition", Select).value
            try:
                run = new_attempt(
                    self.controller,
                    self.run_id,
                    criticism_strategy=cast(Any, None if condition == "same" else condition),
                    idempotency_key=str(uuid4()),
                )
                self.created_run_id = run.id
                self.dismiss(True)
            except (ValueError, OSError):
                self.query_one("#attempt-error", Label).update(
                    "Cannot configure this attempt: select a changed condition "
                    "or a finished research run."
                )
