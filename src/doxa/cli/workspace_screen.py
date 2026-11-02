from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select

from doxa.cli.navigation import ClientModal


class WorkspaceScreen(ClientModal[Path | None]):
    CSS = """
    WorkspaceScreen { align: center middle; }
    #workspace-dialog { width: 90%; height: auto; max-height: 90%; padding: 1; }
    """

    def __init__(self, current: Path):
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="workspace-dialog"):
            from doxa.core.workspaces import recent_workspaces

            recent = recent_workspaces()
            if recent:
                yield Select(
                    [(Text(str(p)), str(p)) for p in recent],
                    prompt="Recent workspaces",
                    id="workspace-recent",
                )
            yield Label("Workspace directory (contains ledger.sqlite3)")
            yield Input(value=str(self.current), id="workspace-path")
            yield Checkbox("Create a new workspace at this path", id="workspace-create")
            yield Label("Existing ledgers are opened independently; no histories are merged.")
            yield Label("", id="workspace-sync")
            yield Label("", id="workspace-error")
            yield Button("Open workspace", id="workspace-open")
            yield Button("Close", id="workspace-close")

    def on_mount(self) -> None:
        self.update_sync_warning(str(self.current))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "workspace-path":
            self.update_sync_warning(event.value)

    def update_sync_warning(self, path: str) -> None:
        existing = (Path(path).expanduser() / "ledger.sqlite3").is_file()
        create = self.query_one("#workspace-create", Checkbox)
        if existing:
            create.value = False
        create.disabled = existing
        create.label = (
            "Existing workspace — open its history; creation is disabled"
            if existing
            else "Create a new workspace at this path"
        )
        warning = (
            "OneDrive-synced folder: avoid opening this workspace on two computers or restoring "
            "synced database files while DOXA is running. Sync is not a database backup. "
            "Nothing will be moved automatically."
            if any(
                part.casefold().startswith("onedrive")
                for part in path.replace("\\", "/").split("/")
            )
            else ""
        )
        self.query_one("#workspace-sync", Label).update(warning)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "workspace-recent" and isinstance(event.value, str):
            self.query_one("#workspace-path", Input).value = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "workspace-close":
            self.dismiss(None)
        elif event.button.id == "workspace-open":
            from doxa.core.workspaces import validate_workspace

            try:
                path = Path(self.query_one("#workspace-path", Input).value).expanduser().resolve()
                if path.exists() and not path.is_dir():
                    raise ValueError("Choose a directory")
                if (path / "ledger.sqlite3").exists():
                    validate_workspace(path)
            except (OSError, ValueError):
                self.query_one("#workspace-error", Label).update(
                    "Invalid or unreadable DOXA workspace; nothing changed."
                )
                return
            create = self.query_one("#workspace-create", Checkbox).value
            if not (path / "ledger.sqlite3").is_file() and not create:
                self.query_one("#workspace-error", Label).update(
                    "No ledger found. Choose its containing directory or explicitly create one."
                )
                return
            if create and path.exists() and any(path.iterdir()):
                self.query_one("#workspace-error", Label).update(
                    "Create requires an empty directory; open an existing workspace instead."
                )
                return
            self.dismiss(path)
