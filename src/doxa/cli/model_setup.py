"""Terminal model registration and explicit, non-generative connection checks."""

import asyncio
import dataclasses
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Collapsible, DataTable, Input, Label, Select

from doxa.cli.model_catalog import (
    CONNECTION_BY_ID,
    CONNECTIONS,
    PROTOCOLS,
    CatalogEntry,
    catalog_entries,
    catalog_notes,
    save_catalog_note,
    search_catalog,
)
from doxa.cli.navigation import ClientModal
from doxa.core.controller import Controller
from doxa.core.profiles import CouncilConfig, ModelProfile


class SecretInput(Input):
    """Masked input without an application clipboard copy or cut action."""

    def action_copy(self) -> None:
        pass

    def action_cut(self) -> None:
        self.delete_selection()


class ModelScreen(ClientModal[bool]):
    CSS = """
    ModelScreen { align: center middle; }
    #model-shell { width: 94%; height: 96%; padding: 0 1; }
    #model-scroll { height: 1fr; }
    #model-identity-page, #model-connection-page { height: auto; }
    #catalog-list { height: 6; }
    ModelScreen Label { height: auto; width: 1fr; max-width: 100%; }
    ModelScreen Vertical { height: auto; }
    #model-error { height: auto; max-height: 3; }
    #model-actions { height: 3; }
    #model-actions Button { min-width: 9; width: 1fr; }
    """

    def __init__(self, controller: Controller, profile: ModelProfile | None = None):
        super().__init__()
        self.controller, self.profile = controller, profile
        self.page = 0
        self.selected_entry = CatalogEntry(
            "Other / Custom", "Custom", profile.model_id if profile else ""
        )
        self.last_connection = ""
        self.discovery_target: tuple[str, str, str, str, bool, str] | None = None
        self.available_references: set[str] | None = None
        self.catalog_error = ""
        self.saved_note: dict[str, Any] = {}
        try:
            self.entries = catalog_entries(
                controller.settings.data_dir, controller.configuration().profiles
            )
            if profile:
                notes = catalog_notes(controller.settings.data_dir)
                note = next(
                    (
                        n
                        for n in reversed(notes)
                        if n.get("profile_id") == profile.id
                        and n.get("profile_version") == profile.version
                    ),
                    None,
                )
                if note:
                    self.saved_note = note
                    self.selected_entry = CatalogEntry(**note["identity"])
        except (OSError, ValueError, TypeError):
            self.entries = [self.selected_entry]
            self.catalog_error = (
                "Catalog notes need review; existing profiles remain intact. No not"
                "es will be replaced."
            )
        self.matches = self.entries
        self.initial_connection = (
            {"openai": "openai", "claude": "anthropic", "runpod": "runpod"}.get(
                profile.runtime, "custom"
            )
            if profile
            else None
        )

        if self.saved_note.get("connection") in CONNECTION_BY_ID:
            self.initial_connection = self.saved_note["connection"]
        if profile and profile.runtime == "openai" and profile.request_protocol == "responses":
            self.initial_connection = "openai_responses"
        if profile and profile.transport == "cli_session":
            self.initial_connection = profile.runtime

    def compose(self) -> ComposeResult:
        p = self.profile
        with Vertical(id="model-shell"):
            yield Label("Choose a model, then its connection — saving makes no network request")
            with VerticalScroll(id="model-scroll"):
                with Vertical(id="model-identity-page"):
                    if p is None:
                        yield Button("Find models on a local server", id="model-local-setup")
                    yield Label(
                        "Search the offline catalog; families need an exact ID. Enter any c"
                        "ustom ID."
                    )
                    yield Input(
                        placeholder="Developer / family / model / exact ID", id="catalog-search"
                    )
                    yield DataTable(id="catalog-list", cursor_type="row")
                    yield Label("", id="catalog-detail", markup=False)
                    yield Label("Exact model ID, or cli-default to use an account CLI's default")
                    yield Input(value=p.model_id if p else "", id="model-id")
                    with Collapsible(
                        title="Model identity details (descriptive, not execution support)",
                        collapsed=True,
                    ):
                        for label, identity, text_value in (
                            ("Model developer", "model-developer", self.selected_entry.developer),
                            ("Model family", "model-family", self.selected_entry.family),
                            (
                                "Display name (optional)",
                                "model-display",
                                self.selected_entry.display_name,
                            ),
                            (
                                "Version / checkpoint (optional)",
                                "model-checkpoint",
                                self.selected_entry.checkpoint,
                            ),
                        ):
                            yield Label(label)
                            yield Input(value=text_value, id=identity)
                with Vertical(id="model-connection-page"):
                    yield Label("", id="model-summary", markup=False)
                    yield Label("Saved connection profile name (letters, digits, _ or -)")
                    yield Input(value=p.id if p else "", id="model-name")
                    yield Label("Connection / provider — independent of the model developer")
                    yield Select(
                        [(c.title, c.key) for c in CONNECTIONS],
                        value=self.initial_connection or Select.NULL,
                        id="model-connection",
                    )
                    yield Label(
                        "API protocol — incompatible native protocols are registration only",
                        id="protocol-label",
                    )
                    protocols = dict(PROTOCOLS)
                    from doxa.providers.cli_session import CLI_NAMES

                    protocols.update(
                        {key: title + " account CLI" for key, (title, _) in CLI_NAMES.items()}
                    )
                    for descriptor in self.controller.provider_catalog():
                        if descriptor.implemented and descriptor.provider not in protocols:
                            protocols[descriptor.provider] = (
                                "Registered adapter: " + descriptor.provider
                            )
                    if p and p.runtime not in protocols:
                        protocols[p.runtime] = "Existing registered adapter: " + p.runtime
                    yield Select(
                        [(label, key) for key, label in protocols.items()],
                        value=p.runtime if p else "openai_compatible",
                        allow_blank=False,
                        id="model-provider",
                    )
                    yield Label("", id="model-status", markup=False)
                    yield Button("Check installed CLIs (no inference)", id="model-cli-check")
                    yield Label("", id="model-cli-status", markup=False)
                    with Collapsible(
                        title="Deployment / connection notes (optional)", collapsed=True
                    ):
                        yield Label(
                            "Hosting / runtime description (optional; does not deploy anything)"
                        )
                        yield Input(
                            value=str(self.saved_note.get("hosting", "")), id="model-hosting"
                        )
                        yield Label("Connection label (optional; not the model developer)")
                        yield Input(value=p.provider if p else "", id="model-label")
                    with Vertical(id="endpoint-fields"):
                        yield Label("RunPod endpoint ID — existing vLLM OpenAI endpoint only")
                        yield Input(value=p.endpoint_id or "" if p else "", id="model-endpoint")
                    with Vertical(id="url-fields"):
                        yield Label(
                            "Server base URL including API prefix; no credentials or query string"
                        )
                        yield Input(value=p.base_url or "" if p else "", id="model-url")
                        yield Checkbox(
                            "Local loopback server (only localhost / 127.0.0.1 / ::1)",
                            value=p.local if p else False,
                            id="model-local",
                        )
                    with Vertical(id="local-discovery"):
                        yield Button("List local models (read-only)", id="model-discover")
                        yield Select[str]([], id="model-discovered", prompt="Choose a listed model")
                        yield Label("", id="model-discovery-status", markup=False)
                        yield Label(
                            "A loopback server may still forward requests outside this machine."
                        )
                    with Vertical(id="auth-fields"):
                        yield Label(
                            "Authentication — native adapters use their own documented key header"
                        )
                        yield Select(
                            [("Credential reference", "bearer"), ("No authentication", "none")],
                            value=(
                                p.authentication if p and p.transport != "cli_session" else "bearer"
                            ),
                            allow_blank=False,
                            id="model-auth",
                        )
                        with Vertical(id="credential-fields"):
                            with Collapsible(
                                title="API credential (optional secure storage)",
                                collapsed=True,
                                id="secret-entry",
                            ):
                                yield Label(
                                    "Enter a new key to store securely on Save. "
                                    "Leave blank to keep the existing reference."
                                )
                                yield SecretInput(password=True, id="model-secret")
                                yield Label("Existing reference (advanced; never enter a key here)")
                                yield Input(
                                    value=(p.credential_env or "") if p else "MODEL_API_KEY",
                                    id="model-env",
                                )
                                yield Checkbox(
                                    "Copy this legacy credential into protected storage on Save",
                                    id="model-migrate-secret",
                                )
                                if p and p.credential_env and p.authentication == "bearer":
                                    yield Label(
                                        "Replace or remove the key used by this saved profile. "
                                        "All versions sharing the reference are affected. Removal "
                                        "does not revoke a key at its provider."
                                    )
                                    yield Checkbox(
                                        "Confirm change to the saved reference",
                                        id="model-confirm-secret",
                                    )
                                    yield Button("Replace stored key", id="model-replace-secret")
                                    yield Button("Delete local key", id="model-delete-secret")
                    with Vertical(id="artifact-fields"):
                        yield Label(
                            "Optional repository identifier — registration, not weight loading"
                        )
                        yield Input(value=p.repository_id or "" if p else "", id="model-repository")
                        yield Label(
                            "Optional existing GGUF file — inspect metadata only; never execute"
                            " weights"
                        )
                        yield Input(id="model-artifact")
                    yield Label(
                        "DOXA currently sends bounded text only. Catalog features do not ad"
                        "d images, "
                        "audio, embeddings, native tools, streaming or reasoning controls."
                    )
                    with Collapsible(
                        title="Advanced generation and resource limits", collapsed=True
                    ):
                        yield Label(
                            "Current compatible/Messages adapters send temperature, max_tokens and "
                            "stream=false. Native OpenAI omits temperature. Exact model accepta"
                            "nce is unverified."
                        )
                        yield Checkbox(
                            "I checked compatibility with this fixed text request",
                            id="model-request-compatible",
                        )
                        with Vertical(id="temperature-fields"):
                            yield Label(
                                "Temperature (0–2); change only if supported by the selected model"
                            )
                            yield Input(
                                value=str(p.temperature if p else 0), id="model-temperature"
                            )
                        yield Checkbox(
                            "Omit temperature (required for some thinking models)",
                            value=p.omit_temperature if p else False,
                            id="model-omit-temperature",
                        )
                        yield Label(
                            "Reasoning declaration: preserve, omit, CLI/Responses effort, "
                            "or Claude adaptive"
                        )
                        yield Select(
                            [
                                (v, v)
                                for v in (
                                    "preserve",
                                    "omit",
                                    "low",
                                    "medium",
                                    "high",
                                    "xhigh",
                                    "max",
                                    "adaptive",
                                )
                            ],
                            value=str(p.reasoning.get("effort", "preserve"))
                            if p and p.transport == "cli_session"
                            else "preserve",
                            allow_blank=False,
                            id="model-reasoning",
                        )
                        yield Label(
                            "Gemini thinking token budget (optional; declares model support)"
                        )
                        yield Input(
                            placeholder="Leave blank to preserve current settings",
                            id="model-thinking-budget",
                        )
                        for label, identity, number in (
                            (
                                "Maximum input bytes",
                                "model-input-bytes",
                                p.max_input_bytes if p else 4096,
                            ),
                            (
                                "DOXA context budget (tokens, not the model's advertised capacity)",
                                "model-context",
                                p.max_context_tokens if p else 4096,
                            ),
                            (
                                "Maximum output (tokens)",
                                "model-output",
                                p.max_output_tokens if p else 256,
                            ),
                            (
                                "Request timeout (seconds)",
                                "model-timeout",
                                p.timeout_seconds if p else 30,
                            ),
                            (
                                "Maximum concurrent calls",
                                "model-concurrency",
                                p.concurrency if p else 1,
                            ),
                        ):
                            yield Label(label)
                            yield Input(value=str(number), id=identity)
                        yield Label(
                            "Text request capability — manual declaration, never a connection test"
                        )
                        yield Select(
                            [
                                ("Unknown", "unknown"),
                                ("Declared compatible (unverified)", "available"),
                                ("Unavailable", "unavailable"),
                            ],
                            value=p.capabilities.text_generation if p else "unknown",
                            allow_blank=False,
                            id="model-text-capability",
                        )
                        yield Label(
                            "Structured output declaration — verify exact model "
                            "and connection support"
                        )
                        yield Select(
                            [
                                ("Unknown", "unknown"),
                                ("Prompted JSON declared", "prompted"),
                                ("Native schema declared", "native"),
                                ("Unavailable", "unavailable"),
                            ],
                            value=p.capabilities.structured_output if p else "unknown",
                            allow_blank=False,
                            id="model-structured-capability",
                        )
                    with Vertical(id="enable-fields"):
                        yield Checkbox(
                            "Allow selection for authorized runs (not verified connectivity)",
                            value=p.enabled if p else False,
                            id="model-enabled",
                        )
                        yield Label(
                            "Remote spending allowance (USD); 0 disables paid dispatch",
                            id="allowance-label",
                        )
                        yield Input(value="0", id="model-allowance")
            yield Label(self.catalog_error, id="model-error", markup=False)
            with Horizontal(id="model-actions"):
                yield Button("Connection setup", id="model-next")
                yield Button("Back to model", id="model-back")
                yield Button("Save", id="model-save")
                yield Button("Cancel", id="model-cancel")

    def on_mount(self) -> None:
        table = self.query_one("#catalog-list", DataTable)
        for title, width in (("Developer / family", 20), ("Model or family", 28), ("Status", 15)):
            table.add_column(title, width=width)
        self.search()
        self.update_connection_fields()
        self.show_page()

    def input(self, identity: str) -> str:
        return self.query_one("#" + identity, Input).value.strip()

    def search(self) -> None:
        self.matches = search_catalog(self.entries, self.input("catalog-search"))
        table = self.query_one("#catalog-list", DataTable)
        table.clear()
        for index, entry in enumerate(self.matches):
            table.add_row(
                Text((entry.developer + " / " + entry.family)[:20]),
                Text((entry.model_id or (entry.family + " (" + entry.kind + ")"))[:28]),
                Text(entry.status[:15]),
                key=str(index),
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.is_mounted:
            if event.input.id == "catalog-search":
                self.search()
            elif event.input.id in {"model-url", "model-env"}:
                self.clear_stale_discovery()
                if event.input.id == "model-env":
                    self.update_status()
            elif event.input.id == "model-id":
                self.update_status()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "catalog-list":
            return
        entry = self.matches[int(str(event.row_key.value))]
        self.selected_entry = entry
        self.query_one("#model-id", Input).value = entry.model_id
        for identity, value in (
            ("model-developer", entry.developer),
            ("model-family", entry.family),
            ("model-display", entry.display_name),
            ("model-checkpoint", entry.checkpoint),
        ):
            self.query_one("#" + identity, Input).value = value
        self.query_one("#catalog-detail", Label).update(
            f"{entry.kind}: {entry.status}. Source: {entry.source}. "
            "Inclusion is not execution support."
        )
        self.update_connection_fields()
        self.query_one("#model-id", Input).focus()

    def show_page(self) -> None:
        self.query_one("#model-identity-page").display = self.page == 0
        self.query_one("#model-connection-page").display = self.page == 1
        self.query_one("#model-next").display = self.page == 0
        self.query_one("#model-back").display = self.page == 1
        self.query_one("#model-scroll", VerticalScroll).scroll_home(animate=False)
        self.query_one("#model-id" if self.page == 0 else "#model-name", Input).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if (
            event.select.id == "model-discovered"
            and isinstance(event.value, str)
            and self.discovery_target == self.local_target()
        ):
            self.query_one("#model-id", Input).value = event.value
            self.query_one("#model-discovery-status", Label).update(
                "Selected model is listed by this runtime. Inference remains untested."
            )
            if not self.input("model-name"):
                self.query_one("#model-name", Input).value = (
                    re.sub(r"[^A-Za-z0-9_-]", "-", event.value)[:64] or "local-model"
                )
        if self.is_mounted and event.select.id in {
            "model-connection",
            "model-provider",
            "model-auth",
        }:
            self.update_connection_fields()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if self.is_mounted:
            self.update_connection_fields()

    def update_connection_fields(self) -> None:
        if not self.is_mounted:
            return
        key = self.query_one("#model-connection", Select).value
        connection = CONNECTION_BY_ID.get(str(key))
        if connection and key != self.last_connection:
            first_edit = self.profile is not None and not self.last_connection
            self.last_connection = str(key)
            if not first_edit:
                self.query_one("#model-provider", Select).value = connection.protocol
                self.query_one("#model-secret", Input).value = ""
                self.query_one("#model-migrate-secret", Checkbox).value = False
                self.query_one("#model-env", Input).value = (
                    "" if connection.local else connection.credential
                )
                self.query_one("#model-local", Checkbox).value = connection.local
                self.query_one("#model-auth", Select).value = (
                    "none" if connection.local else "bearer"
                )
                self.query_one("#model-url", Input).value = connection.base_url
                self.query_one("#model-endpoint", Input).value = ""
        runtime = str(self.query_one("#model-provider", Select).value)
        from doxa.providers.cli_session import CLI_NAMES

        cli = runtime in CLI_NAMES
        if cli:
            if not self.input("model-id"):
                self.query_one("#model-id", Input).value = "cli-default"
            self.query_one("#model-secret", Input).value = ""
            self.query_one("#model-concurrency", Input).value = "1"
            self.query_one("#model-thinking-budget", Input).value = ""
            self.query_one("#model-text-capability", Select).value = "available"
            if self.query_one("#model-structured-capability", Select).value == "unknown":
                self.query_one("#model-structured-capability", Select).value = "prompted"
        self.query_one("#model-cli-check").display = cli
        self.query_one("#model-cli-status").display = cli
        self.query_one("#model-concurrency", Input).disabled = cli
        for control in (
            "#model-thinking-budget",
            "#model-omit-temperature",
            "#model-request-compatible",
        ):
            self.query_one(control).display = not cli
        implemented = runtime in {
            p.provider for p in self.controller.provider_catalog() if p.implemented
        }
        compatible = runtime == "openai_compatible"
        self.query_one("#model-provider").display = bool(connection and key == "custom")
        self.query_one("#protocol-label").display = self.query_one("#model-provider").display
        self.query_one("#endpoint-fields").display = runtime == "runpod"
        self.query_one("#url-fields").display = compatible or key in {"custom", "azure", "vertex"}
        self.query_one("#auth-fields").display = bool(connection) and not cli
        authenticated = self.query_one("#model-auth", Select).value != "none"
        self.query_one("#credential-fields").display = authenticated and not cli
        self.query_one("#model-secret").display = implemented and not cli
        self.query_one("#model-migrate-secret").display = implemented and not cli
        self.query_one("#local-discovery").display = (
            compatible and self.query_one("#model-local", Checkbox).value
        )
        self.clear_stale_discovery()
        self.query_one("#artifact-fields").display = (
            compatible
            and self.query_one("#model-local", Checkbox).value
            and (
                self.selected_entry.open_weight
                or self.selected_entry.kind == "custom"
                or self.selected_entry.developer in {"Other / Custom", "User registered"}
            )
        )
        self.query_one("#temperature-fields").display = (
            not cli
            and runtime != "openai"
            and (
                self.query_one("#model-request-compatible", Checkbox).value
                or self.profile is not None
            )
        )
        self.query_one("#enable-fields").display = implemented
        remote = not self.query_one("#model-local", Checkbox).value
        self.query_one("#model-allowance").display = implemented and remote and not cli
        self.query_one("#allowance-label").display = implemented and remote and not cli
        self.query_one("#model-save", Button).disabled = cli and not implemented
        self.query_one("#model-save", Button).label = (
            "Save profile" if implemented else "Register only"
        )
        self.update_status()

    def update_status(self) -> None:
        if not self.is_mounted:
            return
        from doxa.core.secrets import workspace_env

        key = str(self.query_one("#model-connection", Select).value)
        runtime = str(self.query_one("#model-provider", Select).value)
        implemented = runtime in {
            p.provider for p in self.controller.provider_catalog() if p.implemented
        }
        state = "Model selected. " if self.input("model-id") else "Enter an exact model ID. "
        from doxa.providers.cli_session import CLI_NAMES, CLI_RETRY_WARNING, cli_status

        if runtime in CLI_NAMES:
            check = cli_status(runtime)
            self.query_one("#model-status", Label).update(
                f"{check.name}: {check.detail}. Version: {check.version or 'unverified'}. "
                f"Authentication: {check.authentication}. Subscription quota use requires "
                "separate launch acknowledgment; USD billing unavailable, not zero. "
                + CLI_RETRY_WARNING
            )
            return
        if key not in CONNECTION_BY_ID:
            state += "Choose a connection method."
        elif not implemented:
            state += (
                "Unsupported transport: registration notes only; no assignable prof"
                "ile or execution."
            )
        else:
            authenticated = self.query_one("#model-auth", Select).value != "none"
            if authenticated and self.available_references is None:
                self.available_references = {
                    name for name, value in workspace_env(self.controller.settings.data_dir).items()
                    if value and value != "replace_me"
                }
            present = self.input("model-env") in (self.available_references or set())
            state += "Compatible text adapter exists; endpoint/model acceptance is unverified. "
            state += (
                "Credential not required. " if not authenticated else
                "Credential available. " if present else
                "Credentials required: missing reference or vault unavailable. "
            )
            state += (
                f"Text capability: {self.query_one('#model-text-capability', Select).value} "
                "(declaration only). "
                "Inference untested by setup; execution authorization is separate."
            )
            if self.profile:
                state = f"Registered: {self.profile.id} v{self.profile.version}. " + state
        self.query_one("#model-summary", Label).update(
            "Model: "
            + self.input("model-developer")
            + " / "
            + self.input("model-family")
            + " — "
            + self.input("model-id")
            + ". Back to model edits the served ID."
        )
        self.query_one("#model-status", Label).update(state)

    def identity_note(self) -> dict[str, object]:
        identity = dataclasses.asdict(
            dataclasses.replace(
                self.selected_entry,
                developer=self.input("model-developer"),
                family=self.input("model-family"),
                display_name=self.input("model-display"),
                checkpoint=self.input("model-checkpoint"),
                model_id=self.input("model-id"),
                kind="model",
            )
        )

        if self.input("model-id") != self.selected_entry.model_id:
            identity["source"] = (
                "User-entered served ID; catalog context: " + self.selected_entry.source
            )
            identity["status"] = "User-supplied; unverified"
        return identity

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "model-cancel":
            self.dismiss(False)
        elif event.button.id in {"model-next", "model-back"}:
            self.page = 1 if event.button.id == "model-next" else 0
            self.show_page()
        elif event.button.id == "model-local-setup":
            self.query_one("#model-connection", Select).value = "ollama"
            self.update_connection_fields()
            self.page = 1
            self.show_page()
        elif event.button.id == "model-save":
            await self.save()
        elif event.button.id == "model-discover":
            event.button.disabled = True
            try:
                await self.discover_local()
            finally:
                event.button.disabled = False
        elif event.button.id in {"model-replace-secret", "model-delete-secret"}:
            await self.change_saved_secret(event.button.id == "model-delete-secret")
        elif event.button.id == "model-cli-check":
            from doxa.providers.cli_session import check_installed_clis

            event.button.disabled = True
            try:
                checks = await check_installed_clis()
                self.query_one("#model-cli-status", Label).update(
                    "\n".join(
                        f"{c.name}: {c.detail}; version {c.version or 'unknown'}; "
                        f"authentication {c.authentication}"
                        for c in checks
                    )
                )
                self.update_status()
            finally:
                event.button.disabled = False

    def clear_stale_discovery(self) -> None:
        if self.discovery_target is not None and self.discovery_target != self.local_target():
            self.discovery_target = None
            self.query_one("#model-discovered", Select).set_options([])
            self.query_one("#model-discovery-status", Label).update("")

    def local_target(self) -> tuple[str, str, str, str, bool, str]:
        return (
            str(self.query_one("#model-connection", Select).value),
            self.input("model-url"),
            str(self.query_one("#model-auth", Select).value),
            self.input("model-env"),
            self.query_one("#model-local", Checkbox).value,
            str(self.query_one("#model-provider", Select).value),
        )

    async def discover_local(self) -> None:
        from doxa.core.secrets import reject_secrets, workspace_env
        from doxa.providers.discovery import describe_connection, discover_models

        status = self.query_one("#model-discovery-status", Label)
        selection = self.query_one("#model-discovered", Select)
        selection.set_options([])
        self.discovery_target = None
        target = self.local_target()
        key, url, auth, reference, local, runtime = target
        directory = self.controller.settings.data_dir
        try:
            # A URL must not embed a known secret. An unsaved key is never sent.
            reject_secrets(url, directory=directory, credential_names=(reference,))
            pending = self.query_one("#model-secret", Input).value
            if pending and pending in url:
                raise ValueError("Secret in URL")
            if not local or runtime != "openai_compatible":
                raise ValueError("Expected loopback compatible runtime")
            profile = ModelProfile.model_validate(
                dict(
                    id="local-discovery",
                    provider="ollama" if key == "ollama" else "openai_compatible",
                    adapter="openai_compatible",
                    local=True,
                    base_url=url,
                    model_id=self.input("model-id") or "unselected",
                    authentication=auth,
                    credential_env=reference or None if auth == "bearer" else None,
                )
            )
            env = await asyncio.to_thread(workspace_env, directory)
            report = await discover_models(profile, env, authorize_network=True)
        except (ValueError, OSError):
            status.update("Check loopback URL and credential reference. No inference requested.")
            return
        if target == self.local_target():
            self.discovery_target = target
            selection.set_options([(Text(model), model) for model in report.model_ids])
            status.update(describe_connection(report))

    async def change_saved_secret(self, delete: bool) -> None:
        from doxa.core.credential_store import delete_credential, replace_credential

        field = self.query_one("#model-secret", Input)
        status = self.query_one("#model-error", Label)
        confirmation = self.query_one("#model-confirm-secret", Checkbox)
        reference = self.profile.credential_env if self.profile else None
        if not confirmation.value or reference is None:
            status.update("Confirm the operation on the saved reference first.")
            return
        confirmation.value = False
        value = field.value
        field.value = ""
        try:
            directory = self.controller.settings.data_dir
            if delete:
                await asyncio.to_thread(delete_credential, directory, reference)
                status.update("Local copy removed. The provider key was not revoked.")
            else:
                await asyncio.to_thread(replace_credential, directory, reference, value)
                status.update("Stored key replaced. Profile and experiment versions are unchanged.")
        except (ValueError, OSError):
            status.update("Could not change the stored key. Check vault access and the reference.")
        self.available_references = None
        self.update_status()

    async def save(self) -> None:
        wrote_profile = False
        pending = self.query_one("#model-secret", Input).value
        self.query_one("#model-secret", Input).value = ""
        try:
            name = self.input("model-name")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or not self.input("model-id"):
                raise ValueError("Enter a profile name and exact model ID; use Connection setup.")
            key = str(self.query_one("#model-connection", Select).value)
            connection = CONNECTION_BY_ID.get(key)
            if not connection:
                raise ValueError("Choose how to access this model in Connection setup.")
            runtime = str(self.query_one("#model-provider", Select).value)
            if key != "custom" and runtime != connection.protocol:
                raise ValueError(
                    "Protocol does not match this connection. Select Custom for a diffe"
                    "rent protocol."
                )
            # Never replace unreadable user catalog entries as a side effect of saving.
            catalog_notes(self.controller.settings.data_dir)
            note: dict[str, Any] = {
                "identity": self.identity_note(),
                "connection": key,
                "protocol": runtime,
                "hosting": self.input("model-hosting"),
                "profile_id": name,
            }
            implemented = runtime in {
                p.provider for p in self.controller.provider_catalog() if p.implemented
            }
            if not implemented:
                if pending:
                    raise ValueError("Registration-only connections cannot store API keys")
                url = self.input("model-url")
                if url:
                    parsed = urlsplit(url)
                    if (
                        parsed.scheme != "https"
                        or not parsed.hostname
                        or parsed.username
                        or parsed.password
                        or parsed.query
                        or parsed.fragment
                    ):
                        raise ValueError(
                            "Registration URL must be HTTPS without credentials, query or fragment."
                        )
                registration_reference = self.input("model-env")
                if not re.fullmatch(r"[A-Z][A-Z0-9_]*", registration_reference):
                    raise ValueError("Enter a credential reference name, not a secret value.")
                note.update(
                    registration_only=True, base_url=url,
                    credential_reference=registration_reference,
                )
                save_catalog_note(self.controller.settings.data_dir, note)
                self.notify(
                    "Registration saved; transport unsupported. No model profile or cre"
                    "dential was created."
                )
                self.dismiss(True)
                return
            if (
                runtime in {"openai", "claude", "gemini", "runpod"}
                and self.query_one("#model-auth", Select).value != "bearer"
            ):
                raise ValueError("This native connection requires its credential reference.")
            enabled = self.query_one("#model-enabled", Checkbox).value
            changed_request = (
                not self.profile
                or not self.profile.enabled
                or self.profile.model_id != self.input("model-id")
                or self.profile.runtime != runtime
                or self.profile.base_url != (self.input("model-url") or None)
            )
            if (
                enabled
                and changed_request
                and runtime != "codex_cli"
                and not self.query_one("#model-request-compatible", Checkbox).value
            ):
                raise ValueError(
                    "Before enabling, confirm fixed-request compatibility in Advanced; "
                    "saving disabled is allowed."
                )
            values = self.profile.model_dump() if self.profile else {}
            auth = str(self.query_one("#model-auth", Select).value)
            reference = self.input("model-env") or None
            if auth != "bearer":
                reference = None
            migrate = self.query_one("#model-migrate-secret", Checkbox).value
            if (pending or migrate) and (auth != "bearer" or runtime == "codex_cli"):
                raise ValueError("Secure API storage is only for API credential connections")
            values.update(
                id=name,
                version=self.profile.version + 1 if self.profile else 1,
                provider=self.input("model-label") or ("claude" if key == "anthropic" else key),
                adapter=runtime,
                request_protocol=(
                    "responses"
                    if key == "openai_responses"
                    else "default"
                    if key == "openai"
                    else self.profile.request_protocol
                    if self.profile
                    else "default"
                ),
                omit_temperature=self.query_one("#model-omit-temperature", Checkbox).value,
                model_id=self.input("model-id"),
                local=self.query_one("#model-local", Checkbox).value
                if runtime == "openai_compatible"
                else False,
                authentication=auth,
                credential_env=reference or ("MODEL_API_KEY" if pending else None),
                base_url=self.input("model-url") or None,
                endpoint_id=self.input("model-endpoint") or None if runtime == "runpod" else None,
                repository_id=self.input("model-repository")
                or (self.profile.repository_id if self.profile else None),
                enabled=enabled,
                temperature=0 if runtime == "openai" else float(self.input("model-temperature")),
                max_context_tokens=int(self.input("model-context")),
                max_input_bytes=int(self.input("model-input-bytes")),
                max_output_tokens=int(self.input("model-output")),
                timeout_seconds=float(self.input("model-timeout")),
                concurrency=int(self.input("model-concurrency")),
            )
            values["capabilities"] = {
                **(self.profile.capabilities.model_dump() if self.profile else {}),
                "text_generation": str(self.query_one("#model-text-capability", Select).value),
                "structured_output": str(
                    self.query_one("#model-structured-capability", Select).value
                ),
            }
            if key == "codex_cli":
                values.update(
                    transport="cli_session",
                    authentication="cli_session",
                    credential_env=None,
                    base_url=None,
                    endpoint_id=None,
                    local=False,
                    retries=0,
                    concurrency=1,
                    pricing=None,
                    artifact=None,
                    generation_parameters={},
                    reasoning=(
                        self.profile.reasoning
                        if self.profile and self.profile.transport == "cli_session"
                        else {}
                    ),
                    temperature=0,
                )
            else:
                values["transport"] = "http"
            reasoning_choice = str(self.query_one("#model-reasoning", Select).value)
            if reasoning_choice == "omit":
                values["reasoning"] = {}
            elif reasoning_choice in {"low", "medium", "high", "xhigh", "max"}:
                if runtime != "codex_cli" and (
                    runtime != "openai" or values["request_protocol"] != "responses"
                ):
                    raise ValueError("Reasoning effort requires Codex CLI or OpenAI Responses")
                values["reasoning"] = {"effort": reasoning_choice}
            elif reasoning_choice == "adaptive":
                if runtime != "claude":
                    raise ValueError("Adaptive thinking requires native Anthropic")
                values["reasoning"] = {"type": "adaptive"}
            if self.input("model-thinking-budget"):
                if runtime != "gemini":
                    raise ValueError("Thinking token budget field requires native Gemini")
                values["reasoning"] = {"thinkingBudget": int(self.input("model-thinking-budget"))}
            if values.get("reasoning"):
                parameters = list(values["capabilities"].get("sampling_parameters", []))
                values["capabilities"]["sampling_parameters"] = sorted(
                    set(parameters + ["reasoning"])
                )
            profile = ModelProfile.model_validate(values)
            if self.query_one("#artifact-fields").display and self.input("model-artifact"):
                from doxa.core.model_artifacts import inspect_model_artifact

                artifact = await asyncio.to_thread(
                    inspect_model_artifact, Path(self.input("model-artifact"))
                )
                profile = profile.model_copy(update={"artifact": artifact})
            from doxa.core.credential_store import MANAGED_PREFIX, create_credential
            from doxa.core.secrets import configure_runtime_guard, workspace_env
            from doxa.providers.registry import validate_profile

            directory = self.controller.settings.data_dir
            env = await asyncio.to_thread(workspace_env, directory)
            validate_profile(profile, env)
            if migrate:
                if pending or not reference or reference.startswith(MANAGED_PREFIX):
                    raise ValueError("Choose a legacy reference and leave the new key field blank")
                pending = env.get(reference, "")
                if pending in {"", "replace_me"}:
                    raise ValueError("The legacy credential is missing")
            if pending:
                import json

                from doxa.core.secrets import safe_text

                body = json.dumps([profile.model_dump(mode="json"), note])
                if safe_text(body, extra_values=(pending,)) != body:
                    raise ValueError("A credential must not appear in profile or model fields")
                managed = await asyncio.to_thread(create_credential, directory, pending)
                profile = profile.model_copy(update={"credential_env": managed})

            if profile.enabled and not profile.local and profile.transport != "cli_session":
                configure_runtime_guard(
                    self.controller.settings.data_dir,
                    profile.runtime,
                    self.input("model-allowance"),
                )
            self.controller.save_configuration(CouncilConfig(profiles=(profile,)))
            wrote_profile = True
            note.update(profile_version=profile.version, registration_only=False)
            save_catalog_note(self.controller.settings.data_dir, note)
            self.notify(
                "Connection configured; availability unverified. "
                "Launch requires separate authorization."
            )
            self.dismiss(True)
        except ValidationError as exc:
            from doxa.core.secrets import safe_text

            fields = safe_text(
                ", ".join(
                    ".".join(str(p) for p in e["loc"]) for e in exc.errors(include_input=False)
                ),
                directory=self.controller.settings.data_dir,
                extra_values=(pending,),
            )
            self.query_one("#model-error", Label).update("Check field limits or format: " + fields)
        except (ValueError, KeyError, OSError) as exc:
            if wrote_profile:
                self.notify(
                    "Profile saved; optional catalog notes failed to save. Inspect Models.",
                    severity="warning",
                )
                self.dismiss(True)
            else:
                from doxa.core.secrets import safe_text

                message = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else (
                        "Check file access or the selected configuration; "
                        "existing files are preserved."
                    )
                )
                self.query_one("#model-error", Label).update(
                    safe_text(
                        message,
                        directory=self.controller.settings.data_dir,
                        extra_values=(pending,),
                    )
                )
