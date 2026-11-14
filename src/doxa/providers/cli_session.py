"""Trusted, tool-disabled account CLI adapters. No authentication file access."""

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from doxa.core.models import Contract, Usage
from doxa.core.profiles import ModelProfile
from doxa.providers.contracts import (
    Capabilities,
    ModelRequest,
    ModelResponse,
    ProviderConfig,
    ProviderError,
)

CLI_NAMES = {
    "codex_cli": ("Codex CLI", "codex"),
    "claude_cli": ("Claude Code", "claude"),
    "gemini_cli": ("Gemini CLI", "gemini"),
    "copilot_cli": ("GitHub Copilot CLI", "copilot"),
}
CLI_CAPABILITIES = Capabilities(
    text_generation="available",
    structured_output="prompted",
    usage_reporting=True,
    cancellation=True,
    tool_calling="unavailable",
)
REQUIRED_FLAGS = (
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--sandbox",
    "--json",
    "--skip-git-repo-check",
    "--disable",
    "--strict-config",
)
# These documented controls are adapter code, never profile-supplied shell/config input.
CODEX_SETTINGS = (
    'web_search="disabled"',
    'approval_policy="never"',
    "mcp_servers={}",
    "plugins._default.enabled=false",
    "apps._default.enabled=false",
    "skills.bundled.enabled=false",
    "skills.include_instructions=false",
    "project_doc_max_bytes=0",
    "project_doc_fallback_filenames=[]",
    'history.persistence="none"',
)
CLI_RETRY_WARNING = (
    "DOXA retries zero times. Codex transport retries are client-managed; "
    "this version cannot pin them to zero without overriding a reserved provider."
)
DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "apply_patch_freeform",
    "view_image",
    "multi_agent",
    "apps",
    "hooks",
    "memories",
    "goals",
    "code_mode",
    "code_mode_host",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "remote_plugin",
    "skill_search",
    "skill_mcp_dependency_install",
    "workspace_dependencies",
    "sleep_tool",
    "tool_suggest",
    "js_repl",
    "python_tool",
    "image_generation",
    "imagegen",
    "artifact",
    "agent_message_board",
    "deferred_executor",
    "request_permissions_tool",
    "unbounded_connection_retries",
    "daemon_auto_start",
)
ENV_KEYS = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "HOME",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "CODEX_HOME",
    }
)


class CliStatus(Contract):
    adapter: str
    name: str
    detected: bool
    version: str | None = None
    authentication: Literal["unknown", "authenticated", "missing"] = "unknown"
    supported: bool = False
    ready: bool = False
    schema_available: bool = False
    output_file: bool = False
    disabled_features: tuple[str, ...] = ()
    detail: str
    login_command: str | None = None


_CHECKS: dict[str, tuple[str, CliStatus]] = {}


def executable(adapter: str) -> str | None:
    """Resolve a fixed identity, excluding Windows shell shims and current-directory lookup."""
    if adapter not in CLI_NAMES:
        return None
    path = os.environ.get("PATH", "")
    entries = [
        p.strip('"') for p in path.split(os.pathsep) if p and Path(p.strip('"')).is_absolute()
    ]
    name = CLI_NAMES[adapter][1]
    if sys.platform == "win32":
        name += ".exe"
    # Absolute candidates prevent Windows' implicit current-directory executable search.
    result = next(
        (
            found
            for entry in entries
            if (found := shutil.which(str(Path(entry) / name), path=entry))
        ),
        None,
    )
    if not result or not Path(result).is_absolute():
        return None
    if sys.platform == "win32" and Path(result).suffix.lower() != ".exe":
        return None
    return str(Path(result).resolve())


def session_environment() -> dict[str, str]:
    # Preserve session location references only; no API keys, injected Node/Python code,
    # parent Codex session identifiers, proxy credentials or DOXA secrets are inherited.
    return {k: v for k, v in os.environ.items() if k.upper() in ENV_KEYS}


class StreamLimit(ValueError):
    pass


class SpawnFailed(OSError):
    pass


class CliFailure(ValueError):
    def __init__(self, category: str):
        self.category = category
        super().__init__("CLI reported a sanitized failure")


def research_schema() -> dict[str, Any]:
    """Native output choices mirror controller contracts; authorization stays in the controller."""
    from doxa.core.text_research import ReviewAssessment, ReviewDecision, ReviewResponse

    string = {"type": "string"}
    sources = {"type": "array", "items": string}
    nullable = {"type": ["string", "null"]}
    operations: dict[str, dict[str, Any]] = {
        "claim": {"proposition": string, "source_ids": sources, "revises_id": nullable},
        "challenge": {"claim_id": string, "objection": string, "source_ids": sources},
        "respond": {
            "challenge_id": string,
            "response": {
                **ReviewResponse.model_json_schema()["properties"]["response"],
                "description": "Disposition only. Put the prose explanation in reason.",
            },
            "reason": string,
            "revised_proposition": nullable,
            "revision_of": nullable,
            "source_ids": sources,
        },
        "adjudicate": {
            "claim_id": nullable,
            "challenge_id": nullable,
            "outcome": ReviewDecision.model_json_schema()["properties"]["outcome"],
            "reason": string,
            "source_ids": sources,
        },
        "assess": {
            "claim_id": string,
            "challenge_id": nullable,
            "stance": ReviewAssessment.model_json_schema()["properties"]["stance"],
            "reason": string,
            "source_ids": sources,
        },
    }
    variants = []
    for operation, properties in operations.items():
        props = {"operation": {"type": "string", "const": operation}, **properties}
        variants.append(
            {
                "type": "object",
                "properties": props,
                "required": list(props),
                "additionalProperties": False,
            }
        )
    return {
        "type": "object",
        "properties": {"research_action": {"anyOf": variants}},
        "required": ["research_action"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class ProcessResult:
    code: int
    stdout: bytes
    stderr: bytes
    pid: int | None = None


async def stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), 0.75)
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        await process.wait()


async def _read(
    stream: asyncio.StreamReader,
    limit: int,
    events: int | None,
    on_event: Callable[[str], None] | None = None,
) -> bytes:
    chunks: list[bytes] = []
    pending = b""
    size = count = 0
    while data := await stream.read(4096):
        size += len(data)
        count += data.count(b"\n")
        if size > limit or (events is not None and count > events):
            raise StreamLimit("CLI output exceeded a bounded stream limit")
        chunks.append(data)
        if on_event:
            pending += data
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError):
                    continue  # Final bounded parser remains authoritative.
                kind = str(event.get("type", "")) if isinstance(event, dict) else ""
                stage = {
                    "thread.started": "session_started",
                    "turn.started": "turn_started",
                    "turn.completed": "turn_finished",
                    "error": "provider_error",
                    "turn.failed": "provider_error",
                }.get(kind)
                if kind == "item.completed" and isinstance(event.get("item"), dict):
                    if event["item"].get("type") == "agent_message":
                        stage = "output_available"
                if stage:
                    on_event(stage)  # Persistence errors abort rather than disappear silently.
    return b"".join(chunks)


async def run_process(
    argv: list[str],
    cwd: Path,
    prompt: bytes = b"",
    *,
    timeout: float = 10,
    stdout_limit: int = 65536,
    stderr_limit: int = 16384,
    events: int | None = None,
    active: dict[UUID, asyncio.subprocess.Process] | None = None,
    call_id: UUID | None = None,
    on_spawn: Callable[[int], None] | None = None,
    on_event: Callable[[str], None] | None = None,
) -> ProcessResult:
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=session_environment(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=8192,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
    except OSError:
        raise SpawnFailed("CLI executable could not be started") from None
    if active is not None and call_id is not None:
        active[call_id] = process
    assert process.stdin and process.stdout and process.stderr

    async def feed() -> None:
        assert process.stdin
        try:
            process.stdin.write(prompt)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            process.stdin.close()

    read_stdout = asyncio.create_task(_read(process.stdout, stdout_limit, events, on_event))
    read_stderr = asyncio.create_task(_read(process.stderr, stderr_limit, None))
    jobs = [
        asyncio.create_task(feed()),
        read_stdout,
        read_stderr,
        asyncio.create_task(process.wait()),
    ]
    try:
        if on_spawn is not None:
            on_spawn(process.pid)
        async with asyncio.timeout(timeout):
            await asyncio.gather(*jobs)
        return ProcessResult(
            process.returncode or 0, read_stdout.result(), read_stderr.result(), process.pid
        )
    finally:
        for job in jobs:
            if not job.done():
                job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)

        # Drain without retaining bytes while terminating: a full pipe can otherwise
        # keep Process.wait() pending after the OS process has exited (notably Windows).
        async def drain(stream: asyncio.StreamReader) -> None:
            try:
                while await stream.read(4096):
                    pass
            except (OSError, ValueError):
                pass

        drains = [
            asyncio.create_task(drain(process.stdout)),
            asyncio.create_task(drain(process.stderr)),
        ]
        try:
            await stop_process(process)
            try:
                await asyncio.wait_for(asyncio.gather(*drains), 0.75)
            except TimeoutError:
                pass
        finally:
            for task in drains:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*drains, return_exceptions=True)
            process.stdin.close()
            try:
                await asyncio.wait_for(process.stdin.wait_closed(), 0.75)
            except (OSError, TimeoutError):
                pass
            # StreamReader has no public close method. Close the completed subprocess
            # transport to release pipe handles before a short-lived event loop exits.
            transport = getattr(process, "_transport", None)
            if transport is not None:
                transport.close()
            await asyncio.sleep(0)
        if active is not None and call_id is not None:
            active.pop(call_id, None)


def cli_status(adapter: str) -> CliStatus:
    title = CLI_NAMES.get(adapter, (adapter, ""))[0]
    found = executable(adapter)
    shim = False
    if not found and sys.platform == "win32" and adapter in CLI_NAMES:
        shim = any(
            (Path(entry.strip('"')) / (CLI_NAMES[adapter][1] + suffix)).is_file()
            for entry in os.environ.get("PATH", "").split(os.pathsep)
            if entry and Path(entry.strip('"')).is_absolute()
            for suffix in (".cmd", ".bat", ".ps1")
        )
    cached = _CHECKS.get(adapter)
    if found and cached and cached[0] == found:
        return cached[1]
    return CliStatus(
        adapter=adapter,
        name=title,
        detected=bool(found) or shim,
        detail="Executable present; run Check installed CLIs to verify local readiness"
        if found
        else "Shell shim detected; a native executable is required and the shim is not executed"
        if shim
        else "Executable absent; install and sign in manually outside DOXA",
    )


async def _probe(argv: list[str]) -> ProcessResult:
    with tempfile.TemporaryDirectory(prefix="doxa-cli-check-") as directory:
        return await run_process(argv, Path(directory))


async def check_cli(adapter: str) -> CliStatus:
    status = cli_status(adapter).model_copy(
        update={
            "ready": False,
            "supported": False,
            "authentication": "unknown",
            "version": None,
        }
    )
    path = executable(adapter)
    if not path:
        return status
    if adapter != "codex_cli":
        status = status.model_copy(
            update={
                "supported": False,
                "ready": False,
                "detail": "Detected; a reviewed tool-disabled adapter is not implemented",
            }
        )
        _CHECKS[adapter] = (path, status)
        return status
    try:
        version = await _probe([path, "--version"])
        match = re.fullmatch(rb"codex-cli ([0-9][0-9A-Za-z.+_-]{0,80})\s*", version.stdout)
        if version.code or not match:
            raise ValueError("Version probe failed")
        status = status.model_copy(update={"version": match[1].decode()})
        help_result = await _probe([path, "exec", "--help"])
        help_text = help_result.stdout.decode("utf-8", "replace")
        supported = help_result.code == 0 and all(f in help_text for f in REQUIRED_FLAGS)
        features = await _probe([path, "features", "list"])
        names = {line.split()[0] for line in features.stdout.decode().splitlines() if line.split()}
        supported = (
            supported
            and features.code == 0
            and {
                "shell_tool",
                "unified_exec",
                "multi_agent",
                "apps",
                "hooks",
                "view_image",
                "skip_host_skill_discovery",
            }
            <= names
        )
        try:
            auth = await _probe([path, "login", "status"])
        except (OSError, ValueError, TimeoutError):
            auth = ProcessResult(2, b"", b"")
        auth_text = (auth.stdout + auth.stderr).decode("utf-8", "replace").lower()
        # API-key authentication is intentionally not accepted for this transport.
        authentication: Literal["unknown", "authenticated", "missing"] = "unknown"
        if auth.code == 0 and any(
            line.strip() == "logged in using chatgpt" for line in auth_text.splitlines()
        ):
            authentication = "authenticated"
        elif "not logged in" in auth_text:
            authentication = "missing"
        status = status.model_copy(
            update={
                "version": match[1].decode(),
                "supported": supported,
                "authentication": authentication,
                "ready": supported and authentication == "authenticated",
                "schema_available": "--output-schema" in help_text,
                "output_file": "--output-last-message" in help_text,
                "disabled_features": tuple(f for f in DISABLED_FEATURES if f in names),
                "login_command": "codex login" if authentication != "authenticated" else None,
                "detail": "CLI reports ChatGPT sign-in; session freshness and generation unverified"
                if supported and authentication == "authenticated"
                else "Installed version lacks required safe noninteractive flags"
                if not supported
                else "ChatGPT session missing or unverified; run codex login manually",
            }
        )
    except (OSError, ValueError, TimeoutError):
        status = status.model_copy(
            update={
                "ready": False,
                "authentication": "unknown",
                "supported": False,
                "detail": "Local CLI readiness check failed; no inference was requested",
            }
        )
    _CHECKS[adapter] = (path, status)
    return status


async def check_installed_clis() -> tuple[CliStatus, ...]:
    return tuple([await check_cli(name) for name in CLI_NAMES])


def validate_cli_profile(profile: ModelProfile) -> None:
    if profile.runtime != "codex_cli":
        raise ValueError("This CLI adapter has no reviewed executable implementation")
    if profile.transport != "cli_session":
        raise ValueError("CLI providers require explicit CLI-session transport")
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", profile.model_id)
        or profile.generation_parameters
        or (
            profile.reasoning
            and (
                set(profile.reasoning) != {"effort"}
                or profile.reasoning["effort"] not in ("low", "medium", "high", "xhigh", "max")
            )
        )
        or profile.temperature != 0
        or profile.capabilities.streaming
        or profile.capabilities.images == "available"
        or profile.capabilities.embeddings == "available"
        or profile.capabilities.text_generation == "unavailable"
        or profile.capabilities.seed_control
        or profile.capabilities.tool_calling in {"native", "emulated"}
    ):
        raise ValueError("CLI profile requires a model ID or cli-default and text-only defaults")


def _category(text: str) -> str:
    if re.search(r"error loading config|reserved built-in provider|unknown field", text, re.I):
        return "configuration"
    if re.search(r"quota|usage.limit|rate.limit|credits.exhausted", text, re.I):
        return "quota"
    if re.search(r"not.logged.in|unauthori[sz]ed|authentication|expired.token|login", text, re.I):
        return "authentication"
    if re.search(r"unexpected.argument|unknown.flag|invalid.config|unknown.model", text, re.I):
        return "configuration"
    if "invalid_request_error" in text:
        return "invalid_request"
    return "transport"


def failure_diagnostic(text: str) -> tuple[str, str, bool]:
    """Return only fixed codes and whether startup definitely failed before a request."""
    if "model_providers contains reserved built-in provider IDs" in text:
        return "configuration", "reserved_builtin_provider", True
    if re.search(r"Error loading config\.toml|unknown field.*config", text, re.I):
        return "configuration", "invalid_cli_configuration", True
    category = _category(text)
    return category, "cli_" + category + "_failure", False


def codex_argv(
    path: str, profile: ModelProfile, status: CliStatus, schema: Path | None, final: Path
) -> list[str]:
    """One reviewed command policy; no executable/config fragments come from profiles."""
    validate_cli_profile(profile)
    argv = [
        path,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--json",
        "--color",
        "never",
    ]
    for feature in status.disabled_features:
        argv += ["--disable", feature]
    argv += ["--enable", "skip_host_skill_discovery"]
    for setting in CODEX_SETTINGS:
        argv += ["-c", setting]
    if profile.reasoning:
        argv += ["-c", "model_reasoning_effort=" + json.dumps(profile.reasoning["effort"])]
    if profile.model_id != "cli-default":
        argv += ["--model", profile.model_id]
    if schema:
        argv += ["--output-schema", str(schema)]
    if status.output_file:
        argv += ["--output-last-message", str(final)]
    return [*argv, "-"]


class CodexCliProvider:
    def __init__(self, profile: ModelProfile, env: Mapping[str, str] | None = None):
        validate_cli_profile(profile)
        self.profile = profile
        self.active: dict[UUID, asyncio.subprocess.Process] = {}
        self.activity_observer: Callable[[str], None] | None = None

    def capabilities(self, config: ProviderConfig) -> Capabilities:
        return CLI_CAPABILITIES

    def prompt(self, request: ModelRequest) -> bytes:
        from doxa.core.context_planning import cli_prompt

        return cli_prompt(request.messages)

    def validate_request(self, request: ModelRequest) -> None:
        validate_cli_profile(self.profile)
        if not self.profile.enabled:
            raise PermissionError("CLI profile is disabled")
        if (
            request.assignment.provider != self.profile.provider
            or request.assignment.model_id != self.profile.model_id
            or request.profile_id not in {None, self.profile.id}
            or request.profile_version not in {None, self.profile.version}
            or request.adapter not in {None, self.profile.runtime}
        ):
            raise ValueError("CLI request differs from the pinned profile")
        from doxa.core.context_planning import input_size

        size = input_size(request.messages, request.response_schema, True)
        if (
            request.tools
            or not request.messages
            or any(m.role == "tool" for m in request.messages)
            or size > self.profile.max_input_bytes
        ):
            raise ValueError("CLI request tools or input size exceed the allowed text request")
        if request.max_output_tokens > self.profile.max_output_tokens:
            raise ValueError("CLI output limit exceeds the pinned profile")
        if request.response_schema and len(json.dumps(request.response_schema).encode()) > 65536:
            raise ValueError("CLI response schema exceeds its bound")

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.validate_request(request)
        started = time.monotonic()
        diagnostics: dict[str, Any] = {
            "adapter": "codex_cli",
            "command_policy": "tool_disabled_text_v2",
            "cli_version": None,
            "process_id": None,
            "exit_code": None,
            "stage": "readiness",
            "requested_model_id": self.profile.model_id,
            "requested_reasoning_effort": self.profile.reasoning.get("effort"),
            "native_retry_policy": "client_managed_not_pinned",
            "doxa_retries": 0,
            "accounting": "subscription_quota",
            "usd_billing": "unavailable",
        }
        try:
            async with asyncio.timeout(min(request.timeout_seconds, self.profile.timeout_seconds)):
                return await self._generate(request, diagnostics)
        except TimeoutError:
            return ModelResponse(
                call_id=request.call_id,
                assignment=request.assignment,
                execution_kind="live",
                completion_state="incomplete",
                usage=Usage(latency_seconds=time.monotonic() - started),
                raw_response={**diagnostics, "diagnostic_code": "cli_timeout"},
                error=ProviderError(
                    category="timeout",
                    retryable=False,
                    safe_message="CLI invocation exceeded its time limit",
                ),
            )

    async def _generate(self, request: ModelRequest, diagnostics: dict[str, Any]) -> ModelResponse:
        self.validate_request(request)
        started = time.monotonic()
        observed_usage = Usage()

        def failed(category: str, uncertain: bool = True, code: str | None = None) -> ModelResponse:
            return ModelResponse(
                call_id=request.call_id,
                assignment=request.assignment,
                execution_kind="live",
                completion_state="incomplete",
                raw_response={
                    **diagnostics,
                    "diagnostic_code": code or "cli_" + category + "_failure",
                },
                usage=observed_usage.model_copy(
                    update={"latency_seconds": time.monotonic() - started}
                ),
                error=ProviderError.model_validate(
                    dict(
                        category=category,
                        retryable=False,
                        billing_uncertain=uncertain,
                        safe_message="CLI invocation failed: "
                        + category
                        + (" (" + code + ")" if code else ""),
                    )
                ),
            )

        status = await check_cli("codex_cli")
        diagnostics["cli_version"] = status.version
        if not status.ready:
            return failed("configuration" if not status.supported else "authentication", False)
        path = executable("codex_cli")
        if not path:
            return failed("configuration", False)
        try:
            with tempfile.TemporaryDirectory(prefix="doxa-cli-call-") as directory:
                root = Path(directory)
                cwd = root / "work"
                cwd.mkdir()
                schema = None
                if request.response_schema:
                    if not status.schema_available:
                        return failed("unsupported", False)
                    schema = root / "response.schema.json"
                    schema.write_text(json.dumps(request.response_schema), encoding="utf-8")
                final_path = root / "final.txt"
                argv = codex_argv(path, self.profile, status, schema, final_path)

                def spawned(pid: int) -> None:
                    diagnostics.update(process_id=pid, stage="process_started")
                    if self.activity_observer:
                        self.activity_observer("process_started")

                result = await run_process(
                    argv,
                    cwd,
                    self.prompt(request),
                    timeout=request.timeout_seconds,
                    stdout_limit=1048576,
                    events=256,
                    active=self.active,
                    call_id=request.call_id,
                    on_spawn=spawned,
                    on_event=self.activity_observer,
                )
                diagnostics.update(exit_code=result.code, stage="process_exited")
                if result.pid is not None:
                    diagnostics["process_id"] = result.pid
                if result.code:
                    category, code, before_request = failure_diagnostic(
                        (result.stderr + result.stdout).decode("utf-8", "replace")
                    )
                    # Only a silent stdout plus a recognized startup diagnostic can
                    # establish no request occurred. Never trust model/event text as
                    # evidence for releasing an uncertain quota admission.
                    return failed(
                        category, not (before_request and not result.stdout.strip()), code
                    )
                response = self.parse(request, result.stdout, status)
                observed_usage = response.usage
                # Prefer the bounded final file when present; reject symlinks/non-regular files.
                if final_path.exists():
                    if (
                        final_path.is_symlink()
                        or not final_path.is_file()
                        or final_path.stat().st_size > request.max_output_tokens
                    ):
                        return failed("invalid_response")
                    text = final_path.read_text(encoding="utf-8")
                    if text.strip() or response.completion_state != "refused":
                        response = response.model_copy(update={"text": text})
                if response.text is None or not response.text.strip():
                    return failed("invalid_response")
                if len(response.text.encode()) > request.max_output_tokens:
                    return failed("invalid_response")
                if request.response_schema and response.completion_state == "completed":
                    # The CLI enforces the schema; DOXA still refuses invalid JSON at its boundary.
                    json.loads(response.text)
                if (
                    response.usage.output_tokens is not None
                    and response.usage.output_tokens > request.max_output_tokens
                ):
                    response = response.model_copy(update={"completion_state": "incomplete"})
                return response.model_copy(
                    update={
                        "usage": response.usage.model_copy(
                            update={"latency_seconds": time.monotonic() - started}
                        ),
                        "raw_response": {
                            **(response.raw_response or {}),
                            **diagnostics,
                            "stage": response.completion_state,
                        },
                    }
                )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return failed("timeout")
        except CliFailure as exc:
            return failed(exc.category)
        except (ValueError, UnicodeError, KeyError, TypeError):
            return failed("invalid_response")
        except SpawnFailed:
            return failed("configuration", False)
        except OSError:
            return failed("transport")

    def parse(self, request: ModelRequest, stdout: bytes, status: CliStatus) -> ModelResponse:
        text: str | None = None
        usage = Usage()
        completed = False
        refused = False
        reported: str | None = None
        response_id: str | None = None
        cached: int | None = None
        lines = stdout.splitlines()
        if len(lines) > 256:
            raise ValueError("CLI event count exceeds its bound")
        for line in lines:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("CLI event must be an object")
            kind = event.get("type")
            if kind == "thread.started" and event.get("thread_id"):
                try:
                    response_id = str(UUID(event["thread_id"]))
                except (ValueError, TypeError, AttributeError):
                    pass
            model = event.get("model")
            if isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", model):
                reported = model
            if kind in {"error", "turn.failed"}:
                raise CliFailure(_category(json.dumps(event)))
            if kind == "item.completed":
                item = event.get("item", {})
                if not isinstance(item, dict):
                    raise ValueError("CLI item must be an object")
                if item.get("type") == "agent_message":
                    text = item.get("text")
                elif item.get("type") == "refusal":
                    text = item.get("text", "CLI reported a refusal")
                    refused = True
                elif item.get("type") in {
                    "command_execution",
                    "mcp_tool_call",
                    "web_search",
                    "file_change",
                }:
                    raise ValueError("CLI unexpectedly exposed native tools")
            if kind == "turn.completed":
                completed = True
                tokens = event.get("usage") or {}
                if not isinstance(tokens, dict) or any(
                    value is not None and (type(value) is not int or value < 0)
                    for value in (
                        tokens.get("input_tokens"),
                        tokens.get("output_tokens"),
                        tokens.get("cached_input_tokens"),
                    )
                ):
                    raise ValueError("CLI usage must contain nonnegative integer counts")
                usage = Usage(
                    input_tokens=tokens.get("input_tokens"),
                    output_tokens=tokens.get("output_tokens"),
                )
                cached = tokens.get("cached_input_tokens")
        return ModelResponse(
            call_id=request.call_id,
            assignment=request.assignment,
            execution_kind="live",
            text=text or "",
            usage=usage,
            reported_model_id=reported,
            response_id=response_id,
            completion_state="refused" if refused else "completed" if completed else "incomplete",
            finish_reason="turn.completed" if completed else "completion_unobserved",
            raw_response={
                "adapter": "codex_cli",
                "cli_version": status.version,
                "accounting": "subscription_quota",
                "quota_consumption": "unknown",
                "usd_billing": "unavailable",
                "sampling": "CLI defaults",
                "cached_input_tokens": cached,
                "events_observed": len(lines),
            },
        )

    async def cancel(self, call_id: UUID) -> bool:
        process = self.active.get(call_id)
        if process is None:
            return False
        await stop_process(process)
        return True


# Extending this map requires reviewed Python code; profiles cannot name executables.
CLI_ADAPTERS = {"codex_cli": CodexCliProvider}
