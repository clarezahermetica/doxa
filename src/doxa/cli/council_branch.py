"""Explicit checkpoint preparation for a selected Live Council event."""

import asyncio
from uuid import UUID, uuid4

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from doxa.cli.navigation import ClientModal
from doxa.core.controller import Controller
from doxa.core.models import Checkpoint, Event
from doxa.core.text_research import ReviewFork, TextResearch
from doxa.storage.ledger import LedgerConflict


class CouncilBranch(ClientModal[UUID | None]):
    CSS = """
    CouncilBranch { align: center middle; }
    #council-fork-form { width: 92%; max-width: 92; height: auto; max-height: 95%;
                          padding: 1 2; background: $surface; border: solid $primary; }
    #council-fork-note, #council-fork-result { height: auto; }
    #council-fork-buttons { height: 3; }
    """

    def __init__(self, controller: Controller, branch: UUID, selected: Event) -> None:
        super().__init__()
        self.controller, self.branch, self.selected = controller, branch, selected
        self.options: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="council-fork-form"):
            yield Label(f"Prepare an analysis branch · selected event #{self.selected.sequence}")
            yield Static("Checking stored snapshots…", id="council-fork-result", markup=False)
            yield Select[str]([], prompt="Choose a verified checkpoint", id="council-fork-check")
            yield Static("", id="council-fork-note", markup=False)
            yield Input(placeholder="Intervention description", id="council-fork-intervention")
            yield Checkbox("Confirm a new branch (no inference)", id="council-fork-confirm")
            with Horizontal(id="council-fork-buttons"):
                yield Button("Create branch", id="council-fork-create", disabled=True)
                yield Button("Back", id="council-fork-back")

    def checkpoints(self) -> dict[str, str]:
        if self.selected.trajectory_id != self.branch:
            return {}
        review = TextResearch(self.controller, self.selected.run_id, self.branch)
        order = {event.id: i for i, event in enumerate(review.visible)}
        events = {event.id: event for event in review.visible}
        result = {}
        for record in review.records.values():
            if not isinstance(record, Checkpoint) or record.trajectory_id != self.branch:
                continue
            if record.event_cursor not in events or self.selected.id not in order:
                continue
            try:
                review.validate_fork_checkpoint(record)
            except (KeyError, ValueError, OSError):
                continue
            cursor = events[record.event_cursor]
            relative = order[cursor.id] - order[self.selected.id]
            position = "at" if not relative else "before" if relative < 0 else "after"
            result[str(record.id)] = (
                f"Through #{cursor.sequence} ({position} selected event) · {record.id.hex[:10]}"
            )
        return result

    async def on_mount(self) -> None:
        try:
            self.options = await asyncio.to_thread(self.checkpoints)
        except (KeyError, ValueError, OSError):
            self.options = {}
        select = self.query_one("#council-fork-check", Select)
        select.set_options([(label, identity) for identity, label in self.options.items()])
        select.disabled = not self.options
        if self.selected.trajectory_id != self.branch:
            message = "This event is inherited. Select its owning trajectory to prepare a fork."
        elif not self.options:
            message = "No verified text checkpoint is available on this trajectory."
        else:
            message = (
                "The branch inherits history through the selected checkpoint cursor. "
                "Later parent writes are excluded. This creates analysis history only."
            )
        self.query_one("#council-fork-result", Static).update(message)
        self.update_button()

    def update_button(self) -> None:
        value = self.query_one("#council-fork-check", Select).value
        text = self.query_one("#council-fork-intervention", Input).value.strip()
        self.query_one("#council-fork-create", Button).disabled = not (
            isinstance(value, str)
            and value in self.options
            and 0 < len(text) <= 2000
            and self.query_one("#council-fork-confirm", Checkbox).value
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        self.query_one("#council-fork-note", Static).update(self.options.get(str(event.value), ""))
        self.update_button()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.update_button()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.update_button()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "council-fork-back":
            self.dismiss(None)
            return
        value = self.query_one("#council-fork-check", Select).value
        if event.button.disabled or not isinstance(value, str) or value not in self.options:
            return
        command = ReviewFork(
            idempotency_key=str(uuid4()),
            checkpoint_id=UUID(value),
            intervention=self.query_one("#council-fork-intervention", Input).value.strip(),
        )
        event.button.disabled = True
        try:
            created = await asyncio.to_thread(
                self.controller.review_command, self.selected.run_id, self.branch, command
            )
        except (KeyError, LedgerConflict, ValueError, OSError):
            self.query_one("#council-fork-result", Static).update(
                "The branch could not be created. Check the checkpoint and try again."
            )
            self.update_button()
        else:
            self.dismiss(created.trajectory_id)
