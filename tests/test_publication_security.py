"""Offline socket fixtures: real stdlib reads; no external DNS/provider requests."""

import socket
import ssl
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from doxa.core import web_tools
from doxa.core.web_tools import ApprovedFetch


@pytest.mark.parametrize("phase", ["headers", "detached_body", "truncated", "complete"])
def test_http_deadline_and_complete_response_on_local_socket_pair(monkeypatch, phase):
    client, server = socket.socketpair()
    stopped = threading.Event()
    results, errors = [], []

    class SocketFacade:
        def __getattr__(self, name):
            return getattr(client, name)

        def do_handshake(self):
            pass

    class Context:
        def wrap_socket(self, raw, **kwargs):
            assert not kwargs["do_handshake_on_connect"]
            return SocketFacade()

    monkeypatch.setattr(web_tools, "_FETCH_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(web_tools, "_resolve_addresses", lambda *a: ("93.184.216.34",))
    monkeypatch.setattr(web_tools.socket, "create_connection", lambda *a, **k: client)
    monkeypatch.setattr(web_tools.ssl, "create_default_context", Context)

    def serve():
        try:
            request = b""
            server.settimeout(1)
            while b"\r\n\r\n" not in request:
                request += server.recv(4096)
            if phase == "headers":
                server.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                while not stopped.wait(0.01):
                    server.sendall(b"x")
            else:
                body = b"ok" if phase == "complete" else b"partial"
                length = len(body) if phase == "complete" else 10000
                headers = (
                    "HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n"
                    f"Content-Length: {length}\r\n\r\n"
                ).encode()
                server.sendall(headers + body)
                if phase != "truncated":
                    stopped.wait(2)
        except OSError:
            pass
        finally:
            server.close()

    def fetch():
        try:
            results.append(ApprovedFetch.fetch("https://approved.example/", ("approved.example",)))
        except Exception as exc:
            errors.append(exc)

    peer, worker = threading.Thread(target=serve), threading.Thread(target=fetch)
    peer.start()
    worker.start()
    try:
        worker.join(1)
        assert not worker.is_alive(), "HTTP reader outlived its total I/O deadline"
        if phase == "complete":
            assert not errors and results[0].text == "ok"
        elif phase == "truncated":
            assert errors and isinstance(errors[0], ValueError) and not results
        else:
            assert errors and isinstance(errors[0], TimeoutError) and not results
        assert client.fileno() == -1
    finally:
        stopped.set()
        client.close()
        server.close()
        peer.join(3)
        worker.join(3)


@pytest.mark.parametrize(
    "addresses", [["93.184.216.34"], ["127.0.0.1"], ["93.184.216.34", "10.0.0.1"]]
)
def test_resolver_process_receives_no_credentials_and_parent_rechecks_all_addresses(
    monkeypatch, addresses
):
    import json

    monkeypatch.setenv("PUBLICATION_DUMMY_SECRET", "not-a-real-key")

    def resolve(command, **options):
        assert command[-1] == "approved.example" and not options.get("shell")
        assert "PUBLICATION_DUMMY_SECRET" not in options["env"]
        assert "DOXA_ENV_FILE" not in options["env"]
        return SimpleNamespace(returncode=0, stdout=json.dumps({"addresses": addresses}).encode())

    monkeypatch.setattr(web_tools.subprocess, "run", resolve)
    if addresses == ["93.184.216.34"]:
        assert web_tools._resolve_addresses("approved.example", 0.2) == tuple(addresses)
    else:
        with pytest.raises(PermissionError):
            web_tools._resolve_addresses("approved.example", 0.2)


def test_stalled_resolver_child_is_killed_before_returning_timeout(monkeypatch):
    real_run = subprocess.run

    def stalled(command, **options):
        # A real child is deliberately blocked without issuing a DNS/network request.
        return real_run([sys.executable, "-c", "import time; time.sleep(5)"], **options)

    monkeypatch.setattr(web_tools.subprocess, "run", stalled)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="DNS resolution"):
        web_tools._resolve_addresses("approved.example", 0.1)
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("entry", ["terminal_entry.py"])
def test_frozen_internal_resolver_entry_dispatches_only_fixed_worker(monkeypatch, entry):
    import runpy
    from pathlib import Path

    from doxa.retrieval import dns_worker

    called = []
    monkeypatch.setattr(sys, "argv", ["doxa.exe", "--resolve-host", "approved.example"])
    monkeypatch.setattr(dns_worker, "main", lambda: called.append("resolver"))
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts" / entry), run_name="__main__"
    )
    assert called == ["resolver"]


def test_actual_tls_handshake_timeout_releases_socket(monkeypatch):
    client, server = socket.socketpair()
    stopped, started = threading.Event(), threading.Event()
    errors = []
    monkeypatch.setattr(web_tools, "_FETCH_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(web_tools, "_resolve_addresses", lambda *a: ("93.184.216.34",))
    monkeypatch.setattr(web_tools.socket, "create_connection", lambda *a, **k: client)
    assert isinstance(ssl.create_default_context(), ssl.SSLContext)

    def stalled_peer():
        try:
            server.recv(16384)
            started.set()
            stopped.wait(2)
        finally:
            server.close()

    def fetch():
        try:
            ApprovedFetch.fetch("https://approved.example/", ("approved.example",))
        except Exception as exc:
            errors.append(exc)

    peer, worker = threading.Thread(target=stalled_peer), threading.Thread(target=fetch)
    peer.start()
    worker.start()
    try:
        assert started.wait(1)
        worker.join(1)
        assert not worker.is_alive() and errors and isinstance(errors[0], TimeoutError)
        assert client.fileno() == -1
    finally:
        stopped.set()
        client.close()
        server.close()
        peer.join(3)
        worker.join(3)
