"""Offline reproductions of the post-acceptance defects; never call live providers."""

import asyncio
import gzip
import json

import httpx
import pytest
from test_backend_completion import environment, live_run, profile, request
from test_investigation_protocol import prepare

from doxa.core.execution import ExecuteTask
from doxa.core.models import Claim, ResearchOutcome, RunState
from doxa.core.text_research import ReviewCheckpoint, ReviewEvaluate
from doxa.core.workbench import DebateExecution, DebateRuntime
from doxa.providers import discovery
from doxa.providers.runpod import RunPodProvider
from doxa.storage.budget import BudgetStore


def test_remote_cache_requires_disclosure_before_dispatch_or_reservation(controller, monkeypatch):
    reached = []
    run = live_run(controller, monkeypatch, lambda req: reached.append(req))
    with pytest.raises(PermissionError, match="disclosure"):
        asyncio.run(
            controller.execute_task(
                run.id, ExecuteTask(authorize_paid=True, upper_bound_usd_per_attempt="0.01")
            )
        )
    assert not reached
    assert not BudgetStore(controller.settings.database_path).operations()


class Body(httpx.AsyncByteStream):
    def __init__(self, content, delay=0):
        self.content, self.delay, self.reads, self.closed = content, delay, 0, False

    async def __aiter__(self):
        for chunk in self.content:
            await asyncio.sleep(self.delay)
            self.reads += 1
            yield chunk

    async def aclose(self):
        self.closed = True


def test_discovery_total_deadline_closes_slow_stream(monkeypatch):
    monkeypatch.setattr(discovery, "DISCOVERY_TIMEOUT_SECONDS", 0.04, raising=False)
    body = Body([b" "] * 100, delay=0.01)
    result = asyncio.run(
        discovery.discover_models(
            profile(),
            environment(),
            authorize_network=True,
            transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=body)),
        )
    )
    assert result.status == "unavailable"
    assert body.closed and body.reads < 20


@pytest.mark.parametrize("operation", ["discovery", "generation"])
def test_compressed_provider_body_is_rejected_before_reading(operation):
    body = Body([gzip.compress(b" " * 4_000_000)])

    def respond(req):
        assert req.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"content-encoding": "gzip"}, stream=body)

    transport = httpx.MockTransport(respond)
    if operation == "discovery":
        result = asyncio.run(
            discovery.discover_models(
                profile(), environment(), authorize_network=True, transport=transport
            )
        )
        assert result.status == "unavailable"
    else:
        adapter = RunPodProvider(profile(), environment(), transport)
        result = asyncio.run(adapter.generate(request()))
        assert result.error.category == "invalid_response"
        assert result.error.billing_uncertain and not adapter.tasks
    assert body.reads == 0 and body.closed


def test_accepted_claim_needs_no_reassessment_without_new_material(controller):
    run = prepare(controller, calls=3)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def accept(actor, phase, manifest):
        body = json.loads(default(actor, phase, manifest))
        action = body["research_action"]
        if action["operation"] == "challenge":
            body["research_action"] = {
                "operation": "assess",
                "claim_id": action["claim_id"],
                "stance": "accept",
                "reason": "Offline fixture accepts the scoped claim.",
                "source_ids": action["source_ids"],
            }
        return json.dumps(body)

    runtime.synthetic_answer = accept
    bundle = asyncio.run(runtime.execute_debate(DebateExecution()))
    outcome = next(p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome))
    assert outcome.execution_status == "concluded" and outcome.turns == 3
    assert any(isinstance(p, RunState) for e in bundle.events for p in e.payload)


@pytest.mark.parametrize("failure_type", [ReviewEvaluate, ReviewCheckpoint])
def test_finalization_failure_does_not_publish_success(controller, monkeypatch, failure_type):
    run = prepare(controller)
    original = controller.review_command

    def fail(run_id, branch, command):
        if isinstance(command, failure_type):
            raise ValueError("injected finalization failure")
        return original(run_id, branch, command)

    monkeypatch.setattr(controller, "review_command", fail)
    with pytest.raises(ValueError, match="injected finalization failure"):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    bundle = controller.inspect(run.id)
    assert bundle.run.status == "failed"
    outcomes = [p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome)]
    assert len(outcomes) == 1 and outcomes[0].execution_status == "failed"
    terminal = bundle.events[-1]
    assert any(isinstance(p, ResearchOutcome) for p in terminal.payload)
    assert any(isinstance(p, RunState) and p.status == "failed" for p in terminal.payload)


def test_wrong_stage_output_is_rejected_before_claim_commit(controller):
    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    default = runtime.synthetic_answer

    def wrong_stage(actor, phase, manifest):
        if phase.endswith("stage:cross_criticism"):
            return json.dumps(
                {
                    "research_action": {
                        "operation": "claim",
                        "proposition": "Wrong-stage fixture",
                        "source_ids": [],
                    }
                }
            )
        return default(actor, phase, manifest)

    runtime.synthetic_answer = wrong_stage
    with pytest.raises(ValueError, match="stage"):
        asyncio.run(runtime.execute_debate(DebateExecution()))
    claims = [
        p for e in controller.inspect(run.id).events for p in e.payload if isinstance(p, Claim)
    ]
    assert len(claims) == 1 and claims[0].proposition != "Wrong-stage fixture"


def test_plain_claims_escape_controls_without_rewriting_records(controller):
    from typer.testing import CliRunner

    from doxa.cli.main import app
    from doxa.core.models import EventType

    run = prepare(controller)
    runtime = DebateRuntime(controller, run.id)
    text = "Claim\x1b[2J\rhidden\x08\x9b31m\x1b]0;false title\x07"
    claim = Claim(**runtime.scope(), proposition=text)
    runtime.emit("terminal-control-fixture", EventType.CLAIM_PROPOSED, (claim,))
    before = controller.inspect(run.id).model_dump_json()
    runner = CliRunner()
    args = ["claims", str(run.id), "--data-dir", str(controller.settings.data_dir)]
    plain = runner.invoke(app, args, color=True)
    assert plain.exit_code == 0, plain.exception
    assert all(c not in plain.stdout for c in ("\x1b", "\r", "\x08", "\x9b", "\x07"))
    assert "\\x1b[2J" in plain.stdout
    encoded = runner.invoke(app, [*args, "--json"])
    assert encoded.exit_code == 0 and json.loads(encoded.stdout)[0]["proposition"] == text
    assert controller.inspect(run.id).model_dump_json() == before


def test_cli_metadata_check_never_uses_http_or_requires_api_credentials():
    from doxa.core.profiles import ModelProfile

    cli_profile = ModelProfile(
        id="codex-session",
        provider="codex_cli",
        transport="cli_session",
        authentication="cli_session",
        credential_env=None,
        model_id="unknown-fixture-model",
    )
    report = asyncio.run(
        discovery.discover_models(
            cli_profile, {}, transport=httpx.MockTransport(lambda req: pytest.fail("No HTTP"))
        )
    )
    assert report.status == "connection_unverified" and not report.generation_verified
    assert "Check installed CLIs" in report.detail


@pytest.mark.parametrize("operation", ["discovery", "generation"])
def test_deep_invalid_json_becomes_safe_provider_error(operation):
    body = Body([b"[" * 10000 + b"0" + b"]" * 10000])
    transport = httpx.MockTransport(lambda req: httpx.Response(200, stream=body))
    if operation == "discovery":
        report = asyncio.run(
            discovery.discover_models(
                profile(), environment(), authorize_network=True, transport=transport
            )
        )
        assert report.status == "unavailable"
    else:
        report = asyncio.run(
            RunPodProvider(profile(), environment(), transport).generate(request())
        )
        assert report.error.category == "invalid_response" and report.error.billing_uncertain
    assert body.closed


def test_web_switch_uses_workspace_not_launch_directory(controller, monkeypatch, tmp_path):
    from test_workbench import tool_council

    from doxa.core.web_tools import ToolRequest, ToolResult, use_tool

    run, actor = tool_council(controller)
    (controller.settings.data_dir / ".env").write_text("DOXA_WEB_ENABLED=true\n")
    other = tmp_path / "unrelated-launch-directory"
    other.mkdir()
    (other / ".env").write_text("DOXA_WEB_ENABLED=false\n")
    monkeypatch.chdir(other)
    monkeypatch.delenv("DOXA_ENV_FILE", raising=False)
    monkeypatch.delenv("DOXA_WEB_ENABLED", raising=False)

    class OfflineTransportFixture:
        name, synthetic = "offline-boundary-fixture", False

        async def invoke(self, command, domains):
            return ToolResult("Offline local fixture; no network request.", ())

    audit = asyncio.run(
        use_tool(
            controller,
            run.id,
            ToolRequest(
                agent_id=actor.id,
                tool="web_fetch",
                query_or_url="https://example.org/paper",
                authorize_external=True,
                idempotency_key="workspace-switch",
            ),
            OfflineTransportFixture(),
        )
    )
    assert audit.status == "completed"


def test_terminal_outcome_and_state_roll_back_together(controller, monkeypatch):
    from doxa.core.models import EventType

    run = prepare(controller)
    original = controller.ledger.append

    def fail_once(event):
        if event.type == EventType.RUN_CLOSED:
            assert any(isinstance(p, ResearchOutcome) for p in event.payload)
            raise OSError("injected outcome publication failure")
        return original(event)

    monkeypatch.setattr(controller.ledger, "append", fail_once)
    with pytest.raises(OSError, match="publication failure"):
        asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    bundle = controller.inspect(run.id)
    assert bundle.run.status == "failed"
    outcomes = [p for e in bundle.events for p in e.payload if isinstance(p, ResearchOutcome)]
    assert len(outcomes) == 1 and outcomes[0].execution_status == "failed"


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-be"])
def test_docx_dtd_policy_cannot_be_bypassed_by_xml_encoding(encoding):
    import io
    import zipfile

    from doxa.retrieval.documents import extract_document

    xml = (
        '<!DOCTYPE w:document [<!ENTITY fixture "harmless internal entity">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>&fixture;</w:t></w:r></w:p></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml.encode(encoding))
    with pytest.raises(ValueError):
        extract_document("encoding-fixture.docx", buffer.getvalue())


def test_selected_stage_accepts_equivalent_uuid_spelling():
    from uuid import uuid4

    from doxa.core.investigation import validate_stage_action

    target = uuid4()
    validate_stage_action(
        {"operation": "assess", "claim_id": str(target).upper()},
        f"investigation:1:target:{target}:challenge:none:stage:cross_criticism",
    )
