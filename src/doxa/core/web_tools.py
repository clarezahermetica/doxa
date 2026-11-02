"""Bounded, opt-in web evidence. No general browser or generated-code network access."""

import asyncio
import http.client
import io
import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid5

from pydantic import Field

from doxa.core.controller import Controller
from doxa.core.execution import Runtime
from doxa.core.models import Contract, Event, EventType, Provenance, SourceDocument, ToolAudit
from doxa.core.secrets import local_env, reject_secrets
from doxa.retrieval.dns_worker import public_addresses as public_addresses


class ToolRequest(Contract):
    agent_id: UUID
    tool: Literal["web_search", "web_fetch"]
    query_or_url: str = Field(min_length=1, max_length=2000)
    authorize_external: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)


@dataclass(frozen=True)
class ToolResult:
    text: str
    urls: tuple[str, ...]


class WebAdapter(Protocol):
    name: str
    synthetic: bool

    async def invoke(self, command: ToolRequest, domains: tuple[str, ...]) -> ToolResult: ...


def checked_url(url: str, domains: tuple[str, ...]) -> tuple[str, str]:
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError
        host = parsed.hostname.encode("idna").decode().lower()
        if host not in {d.lower() for d in domains}:
            raise ValueError
        # Literal addresses are deliberately unsupported, even publicly routed ones.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        return host, (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
    except (ValueError, UnicodeError):
        raise PermissionError("URL must use HTTPS and an explicitly approved domain") from None


def _resolve_addresses(host: str, timeout: float) -> tuple[str, ...]:
    # Unlike a thread, this fixed resolver process can be stopped if OS DNS stalls.
    command = (
        [sys.executable, "--resolve-host", host]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "doxa.retrieval.dns_worker", host]
    )
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH"}
    }
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            env=environment,
            timeout=timeout,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError("Web DNS resolution exceeded its time limit") from None
    if result.returncode or len(result.stdout) > 65536:
        raise PermissionError("Public DNS resolution failed")
    try:
        values = json.loads(result.stdout)["addresses"]
        if not isinstance(values, list) or not 1 <= len(values) <= 64:
            raise ValueError
        addresses = tuple(str(ipaddress.ip_address(value)) for value in values)
        if any(not ipaddress.ip_address(value).is_global for value in addresses):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise PermissionError("Invalid or non-public DNS result refused") from None
    return addresses


_FETCH_TIMEOUT_SECONDS = 10.0


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Web fetch I/O deadline expired")
    return remaining


class _DeadlineReader(io.RawIOBase):
    def __init__(self, stream: ssl.SSLSocket, deadline: float):
        super().__init__()
        self.stream, self.deadline = stream, deadline

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        # HTTP header and chunk parsers may perform many reads inside one call.
        # Reapply the absolute budget to every underlying receive, not just read1.
        self.stream.settimeout(_remaining(self.deadline))
        return self.stream.recv_into(buffer)


class _DeadlineSocket:
    """Non-owning HTTP socket view; fetch's finally block owns the TLS socket."""

    def __init__(self, stream: ssl.SSLSocket, deadline: float):
        self.stream, self.deadline = stream, deadline

    def sendall(self, data: bytes) -> None:
        self.stream.settimeout(_remaining(self.deadline))
        self.stream.sendall(data)

    def makefile(self, mode: str) -> io.BufferedReader:
        if mode != "rb":
            raise ValueError("Only a binary HTTP response reader is supported")
        return io.BufferedReader(_DeadlineReader(self.stream, self.deadline))

    def close(self) -> None:
        """HTTPConnection may close its view while HTTPResponse still reads."""


class ApprovedFetch:
    name = "https_pinned_fetch_v1"
    synthetic = False

    async def invoke(self, command: ToolRequest, domains: tuple[str, ...]) -> ToolResult:
        if command.tool != "web_fetch":
            raise PermissionError("No live search provider has been configured")
        return await asyncio.to_thread(self.fetch, command.query_or_url, domains)

    @staticmethod
    def fetch(url: str, domains: tuple[str, ...]) -> ToolResult:
        host, path = checked_url(url, domains)
        # Resolve once, validate every answer, connect to a checked address, and retain
        # the original hostname for TLS verification. No proxy, redirects or cookies.
        deadline = time.monotonic() + _FETCH_TIMEOUT_SECONDS
        address = _resolve_addresses(host, _remaining(deadline))[0]
        remaining = _remaining(deadline)
        connection = http.client.HTTPSConnection(host, timeout=remaining)
        raw = socket.create_connection((address, 443), timeout=remaining)
        secure: ssl.SSLSocket | None = None
        response: http.client.HTTPResponse | None = None
        try:
            # Retain the TLS socket even when HTTPResponse takes ownership of its
            # file and HTTPConnection clears sock (e.g. Connection: close).
            secure = ssl.create_default_context().wrap_socket(
                raw, server_hostname=host, do_handshake_on_connect=False
            )
            connection.sock = cast(Any, _DeadlineSocket(secure, deadline))
            secure.settimeout(_remaining(deadline))
            secure.do_handshake()
            connection.request(
                "GET",
                path,
                headers={
                    "Host": host,
                    "Accept": "text/plain,text/html,application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "DOXA-evidence/1",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError("Only a direct successful response is accepted")
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise ValueError("Compressed evidence is unsupported")
            media = response.getheader("Content-Type", "").split(";")[0].lower()
            if media not in {"text/plain", "text/html", "text/markdown", "application/json"}:
                raise ValueError("Unsupported evidence type")
            chunks: list[bytes] = []
            size = 0
            while True:
                if response.isclosed():
                    break
                _remaining(deadline)
                chunk = response.read1(min(16384, 262145 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > 262144:
                    raise ValueError("Evidence response exceeds 256 KiB")
                chunks.append(chunk)
            if response.length not in {None, 0}:
                raise ValueError("Incomplete evidence response")
            result = ToolResult(b"".join(chunks).decode("utf-8", errors="replace"), (url,))
        finally:
            if response is not None:
                response.close()
            connection.close()
            if secure is not None:
                secure.close()
            raw.close()
        _remaining(deadline)
        return result


class MockWeb:
    name = "offline_tool_fixture"
    synthetic = True

    async def invoke(self, command: ToolRequest, domains: tuple[str, ...]) -> ToolResult:
        if command.tool == "web_fetch":
            checked_url(command.query_or_url, domains)
        return ToolResult(
            "Synthetic tool fixture: retrieved evidence is an untrusted source.",
            (command.query_or_url,) if command.tool == "web_fetch" else (),
        )


async def use_tool(
    controller: Controller, run_id: UUID, command: ToolRequest, adapter: WebAdapter | None = None
) -> ToolAudit:
    runtime = Runtime(controller, run_id)
    task = runtime.experiment.task
    if not task or runtime.run.status not in {"configured", "running"}:
        raise ValueError("Tools require an active workbench task")
    agent = next(
        (a for a in runtime.experiment.agents if a.id == command.agent_id and a.enabled), None
    )
    if not agent or command.tool not in agent.permissions.allowed_tools:
        raise PermissionError("Agent is not authorized for this tool")
    expected = "approved_search" if command.tool == "web_search" else "approved_fetch"
    if (
        task.network_mode not in {expected, "approved_search_and_fetch"}
        or not command.authorize_external
    ):
        raise PermissionError("Run policy and explicit disclosure authorization are required")
    chosen = adapter or ApprovedFetch()
    if not chosen.synthetic and local_env().get("DOXA_WEB_ENABLED", "false").lower() != "true":
        raise PermissionError("Live web tools are disabled")
    if chosen.synthetic and runtime.run.execution_kind != "synthetic":
        raise PermissionError("Synthetic tool output requires a synthetic run")
    reject_secrets(command.model_dump_json(), directory=controller.settings.data_dir)
    prior_events = runtime.ledger.events(run_id)
    operation = uuid5(run_id, "tool:" + command.idempotency_key)
    previous = [
        p
        for e in prior_events
        for p in e.payload
        if isinstance(p, ToolAudit) and p.operation_id == operation
    ]
    if previous:
        if any(
            (p.agent_id, p.tool, p.query_or_url)
            != (command.agent_id, command.tool, command.query_or_url)
            for p in previous
        ):
            raise ValueError("Tool idempotency conflict")
        return previous[-1]  # In-flight/uncertain calls are never retried automatically.
    count = sum(
        isinstance(p, ToolAudit) and p.status == "started" and p.tool == command.tool
        for e in prior_events
        for p in e.payload
    )
    cap = task.max_searches if command.tool == "web_search" else task.max_fetches
    total = sum(
        isinstance(p, ToolAudit) and p.status == "started" for e in prior_events for p in e.payload
    )
    if count >= cap or total >= runtime.experiment.budget.max_tool_calls:
        raise ValueError("Persistent web-tool quota reached")
    if command.tool == "web_fetch":
        checked_url(command.query_or_url, task.allowed_domains)
    provenance = Provenance.IMPORTED_SOURCE if chosen.synthetic else Provenance.TOOL_OBSERVATION
    started = ToolAudit.model_validate(
        dict(
            **runtime.scope(provenance),
            id=uuid5(operation, "started"),
            operation_id=operation,
            agent_id=agent.id,
            tool=command.tool,
            query_or_url=command.query_or_url,
            provider=chosen.name,
            status="started",
        )
    )
    runtime.ledger.append(
        Event(
            experiment_id=runtime.experiment.id,
            run_id=run_id,
            trajectory_id=runtime.branch,
            sequence=1,
            type=EventType.ACTION_REQUESTED,
            actor_id=agent.id,
            actor_role=agent.role,
            model=agent.model,
            provenance=provenance,
            payload=(started,),
            parent_event_ids=(prior_events[-1].id,),
            expected_cursor=prior_events[-1].id,
            expected_trajectory_id=runtime.branch,
            idempotency_key=f"{run_id}:tool:{command.idempotency_key}:started",
        )
    )
    try:
        async with asyncio.timeout(12):
            result = await chosen.invoke(command, task.allowed_domains)
        if len(result.text.encode()) > 262144 or len(result.urls) > 10:
            raise ValueError("Tool result exceeds quota")
        for url in result.urls:
            checked_url(url, task.allowed_domains)
        reject_secrets(result.text, directory=controller.settings.data_dir)
        artifact = runtime.store.put(result.text.encode(), "text/plain")
        finished = started.model_copy(
            update={
                "id": uuid5(operation, "completed"),
                "status": "completed",
                "result": artifact,
                "source_urls": result.urls,
            }
        )
        source = SourceDocument.model_validate(
            dict(
                **runtime.scope(provenance),
                id=uuid5(operation, "source"),
                title="Web tool evidence",
                source=json.dumps(result.urls),
                content=artifact,
                visibility="private",
                owner_agent_id=agent.id,
            )
        )
        runtime.emit(
            "tool:" + command.idempotency_key + ":finished",
            EventType.TOOL_RESULT_OBSERVED,
            (finished, source),
            agent,
            provenance,
        )
        return finished
    except BaseException:
        failed = started.model_copy(
            update={
                "id": uuid5(operation, "failed"),
                "status": "failed",
                "error_code": "tool_failed_or_interrupted",
            }
        )
        runtime.emit(
            "tool:" + command.idempotency_key + ":failed",
            EventType.TOOL_RESULT_OBSERVED,
            (failed,),
            agent,
            provenance,
        )
        raise
