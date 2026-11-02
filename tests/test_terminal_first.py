import asyncio
import json
from pathlib import Path

import httpx
import pytest

from doxa.core.models import CouncilLimits, Experiment, ModelCall, Role, TaskSpecification
from doxa.core.profiles import CouncilConfig, ModelProfile
from doxa.core.workbench import (
    DebateExecution,
    DebateRuntime,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
)
from doxa.providers.runpod import RunPodProvider, endpoint_url


def test_arbitrary_local_model_uses_mocked_compatible_endpoint_without_credential(controller):
    profile = ModelProfile(
        id="local",
        provider="my-lab-engine",
        adapter="openai_compatible",
        model_id="previously-unknown-model-42",
        base_url="http://127.0.0.1:11434/v1",
        local=True,
        authentication="none",
        enabled=True,
    )
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    template = add_agent(
        controller,
        NewAgent(
            display_name="Skeptic",
            role=Role.SKEPTIC,
            instructions="Inspect supplied evidence.",
            profile_id=profile.id,
            profile_version=1,
            remote_inference=True,
        ),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Local inference mock",
            execution_kind="live",
            task=TaskSpecification(
                question="What is supported?",
                council=CouncilLimits(rounds=1, scheduling="round_parallel", concurrency=2),
            ),
            participants=(ParticipantGroup(agent_id=template.id, count=2),),
            idempotency_key="local",
        ),
    )
    calls = []

    def respond(request):
        assert "authorization" not in request.headers
        assert json.loads(request.content)["model"] == profile.model_id
        calls.append(request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Unverified argument."}}]}
        )

    provider = RunPodProvider(profile, {}, httpx.MockTransport(respond))
    controller.providers.create = lambda *a, **k: provider
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    assert len(calls) == 2 and bundle.run.status == "completed"
    records = [p for e in bundle.events for p in e.payload if isinstance(p, ModelCall)]
    assert len([p for p in records if p.status == "started"]) == 2
    assert len([p for p in records if p.status == "completed"]) == 2
    assert len({p.agent_id for p in records}) == 2
    assert not bundle.accounting
    assert all(p.usage.billed_usd is None for p in records)
    assert isinstance(controller.ledger.get(run.experiment_id), Experiment)


def test_local_endpoint_policy_does_not_allow_remote_plaintext():
    profile = ModelProfile(
        id="local",
        provider="openai_compatible",
        local=True,
        base_url="http://127.0.0.1:8080/v1",
        model_id="any-model",
        authentication="none",
    )
    assert endpoint_url(profile, {}) == profile.base_url
    for url in ("http://example.org/v1", "https://example.org/v1", "http://127.0.0.1@evil.test/v1"):
        with pytest.raises(ValueError):
            endpoint_url(profile.model_copy(update={"base_url": url}), {})


def test_workspace_selection_and_original_moss_file_resolution(tmp_path, monkeypatch):
    from doxa.core.config import Settings
    from doxa.core.controller import Controller
    from doxa.core.secrets import workspace_env
    from doxa.core.workspaces import default_workspace, remember_workspace

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))
    monkeypatch.delenv("DOXA_DATA_DIR", raising=False)
    monkeypatch.delenv("DOXA_ENV_FILE", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    workspace = project / ".doxa"
    Controller(Settings(data_dir=workspace)).initialize()
    (project / ".env").write_text("MOSS_PROJECT_ID=fixture-id\nMOSS_PROJECT_KEY=fixture-value\n")
    original = (project / ".env").read_bytes()
    remember_workspace(workspace)
    monkeypatch.chdir(tmp_path)
    assert default_workspace() == workspace.resolve()
    assert workspace_env(workspace)["MOSS_PROJECT_KEY"] == "fixture-value"
    assert (project / ".env").read_bytes() == original
    assert not (workspace / ".env").exists()


def test_dpapi_credential_never_stored_plaintext_or_replaced(tmp_path):
    import os

    if os.name != "nt":
        pytest.skip("Windows DPAPI")
    from doxa.core.credential_store import load_credentials, save_credential

    secret = "offline-credential-fixture-only"
    save_credential(tmp_path, "FIXTURE_KEY", secret)
    assert secret.encode() not in (tmp_path / "credentials/FIXTURE_KEY.dpapi").read_bytes()
    assert load_credentials(tmp_path)["FIXTURE_KEY"] == secret
    with pytest.raises(FileExistsError):
        save_credential(tmp_path, "FIXTURE_KEY", "replacement-forbidden")


def test_terminal_inspection_and_export_at_narrow_dimensions(controller, tmp_path):
    from textual.widgets import Input, Select, TabbedContent, TextArea

    from doxa.cli.console import ResearchConsole
    from doxa.core.workbench_demo import demonstrate

    result = asyncio.run(demonstrate(controller))

    async def interact():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.query_one(TabbedContent).active = "inspect"
            app.query_one("#record-kind", Select).value = "Claims"
            await pilot.pause()
            assert len(app.record_map) == 8
            app.selected_record = next(iter(app.record_map.values()))
            app.show_record()
            assert "Synthetic" in app.query_one("#inspector", TextArea).text
            app.action_export()
            await pilot.pause()
            app.screen.query_one("#export-path", Input).value = str(tmp_path / "export.json")
            await pilot.click("#export-save")
            await pilot.pause()
            exported = json.loads((tmp_path / "export.json").read_text())
            assert exported["run"]["id"] == str(result["run_id"])
            await pilot.click("#export-close")
            await pilot.resize_terminal(110, 32)
            await pilot.press("q")

    asyncio.run(interact())


def test_structured_multiagent_criticism_revision_and_model_adjudication(controller):
    from doxa.core.models import Challenge, Claim, Decision, Provenance
    from doxa.core.workbench import ImportSource, import_source

    profile = ModelProfile(
        capabilities={"structured_output": "prompted"},
        id="structured",
        provider="custom-lab",
        adapter="openai_compatible",
        local=True,
        authentication="none",
        enabled=True,
        model_id="unknown-debate-model",
        base_url="http://127.0.0.1:8080/v1",
        max_context_tokens=12000,
        max_input_bytes=12000,
    )
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    groups = []
    for role in (Role.EXECUTOR, Role.SKEPTIC, Role.ARCHIVIST):
        template = add_agent(
            controller,
            NewAgent(
                display_name=role.value,
                role=role,
                instructions=role.value + ": inspect sources.",
                profile_id=profile.id,
                profile_version=1,
                remote_inference=True,
            ),
        )
        groups.append(
            ParticipantGroup(agent_id=template.id, count=2 if role == Role.SKEPTIC else 1)
        )
    from doxa.core.models import BudgetPolicy

    run = create_experiment(
        controller,
        NewExperiment(
            name="Structured mock research",
            execution_kind="live",
            task=TaskSpecification(
                question="Which claim is supported?",
                structured_actions=True,
                council=CouncilLimits(rounds=2, per_agent_tokens=100000, total_tokens=500000),
            ),
            participants=tuple(groups),
            budget=BudgetPolicy(max_context_tokens=12000),
            idempotency_key="structured",
        ),
    )
    source = import_source(
        controller,
        run.id,
        ImportSource(
            title="Source evidence",
            text="Supplied evidence is incomplete and requires explicit qualification.",
            idempotency_key="paper",
        ),
    )

    def respond(request):
        payload = json.loads(request.content)
        role = payload["messages"][0]["content"].split(":", 1)[0]
        snippets = []
        for line in payload["messages"][1]["content"].splitlines()[1:]:
            item = json.loads(line)
            try:
                record = json.loads(item["untrusted_content"])
            except (ValueError, TypeError):
                continue
            if isinstance(record, dict):
                snippets.append(record)
        claims = [r for r in snippets if r.get("kind") == "claim"]
        challenges = [
            r for r in snippets if r.get("kind") == "challenge" and not r.get("responds_to_id")
        ]
        if role == "executor" and challenges:
            action = dict(
                operation="respond",
                challenge_id=challenges[0]["id"],
                response="qualify",
                reason="Evidence does not justify certainty.",
                revised_proposition="A qualified unverified conclusion.",
            )
        elif role == "skeptic" and claims:
            action = dict(
                operation="challenge",
                claim_id=claims[0]["id"],
                objection="Insufficient evidence.",
                source_ids=[str(source.id)],
            )
        elif role == "archivist" and challenges:
            action = dict(
                operation="adjudicate",
                challenge_id=challenges[0]["id"],
                outcome="investigate",
                reason="Unresolved; this is a model opinion.",
            )
        else:
            action = dict(
                operation="claim",
                proposition="Initial unverified conclusion.",
                source_ids=[str(source.id)],
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"research_action": action})}}]},
        )

    controller.providers.create = lambda *a, **k: RunPodProvider(
        profile, {}, httpx.MockTransport(respond)
    )
    bundle = asyncio.run(DebateRuntime(controller, run.id).execute_debate(DebateExecution()))
    records = [p for e in bundle.events for p in e.payload]
    assert bundle.run.status == "completed"
    assert any(isinstance(p, Challenge) and p.responds_to_id for p in records)
    assert any(isinstance(p, Claim) and p.revises_id and p.evidence_ids for p in records)
    decisions = [p for p in records if isinstance(p, Decision)]
    assert decisions and all(
        p.provenance == Provenance.LLM_EVALUATOR and not p.verification_ids for p in decisions
    )
    calls = [p for p in records if isinstance(p, ModelCall) and p.status == "completed"]
    assert len(calls) == 8 and len({p.agent_id for p in calls}) == 4


def test_model_discovery_is_explicit_bounded_and_never_generates():
    from doxa.providers.discovery import discover_models

    p = ModelProfile(
        id="local",
        provider="openai_compatible",
        local=True,
        model_id="new",
        base_url="http://127.0.0.1:8080/v1",
        authentication="none",
    )
    calls = []

    def respond(request):
        calls.append(request)
        assert request.method == "GET" and request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "new-model"}]})

    with pytest.raises(PermissionError):
        asyncio.run(discover_models(p, {}, transport=httpx.MockTransport(respond)))
    result = asyncio.run(
        discover_models(p, {}, authorize_network=True, transport=httpx.MockTransport(respond))
    )
    assert result.model_ids == ("new-model",) and not result.generation_verified
    assert len(calls) == 1


def test_adapter_extensions_and_model_artifacts_do_not_load_model_code(
    controller, tmp_path, monkeypatch
):
    from doxa.providers.contracts import Capabilities
    from doxa.providers.registry import ADAPTERS, AdapterRegistration

    sentinel = object()
    monkeypatch.setitem(
        ADAPTERS,
        "fixture-existing",
        AdapterRegistration(
            lambda *a: sentinel,
            lambda *a: None,
            Capabilities(),
            "DOXA_FIXTURE_ENABLED",
            "DOXA_FIXTURE_ALLOWANCE_USD",
        ),
    )
    profile = ModelProfile(
        id="extension",
        provider="brand-new-adapter",
        adapter="fixture-existing",
        model_id="any-repo/new-model",
    )
    assert controller.providers.create(profile, {}) is sentinel
    from doxa.core.model_artifacts import inspect_model_artifact

    path = tmp_path / "fixture.gguf"
    path.write_bytes(b"GGUF" + (3).to_bytes(4, "little") + b"test-only")
    artifact = inspect_model_artifact(path)
    assert artifact.sha256 and not artifact.execution_verified
    with pytest.raises(ValueError):
        inspect_model_artifact(Path(__file__))


def test_complete_offline_workflow_through_existing_terminal(controller, tmp_path, monkeypatch):
    from textual.widgets import Checkbox, Input, Select, SelectionList, TextArea

    from doxa.cli.console import ResearchConsole
    from doxa.core.models import Checkpoint, Claim, ContextManifest, SourceDocument, Trajectory

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ui-preferences"))
    paper = tmp_path / "paper.md"
    paper.write_text("Source evidence: conclusions require explicit qualification.")

    async def interact():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(100, 36)) as pilot:

            async def click(identifier):
                app.screen.query_one(identifier).scroll_visible(
                    immediate=True, animate=False, force=True
                )
                await pilot.pause()
                await pilot.click(identifier)
                await pilot.pause()

            app.action_model()
            await pilot.pause()
            app.screen.query_one("#model-connection", Select).value = "vllm"
            await pilot.pause()
            app.screen.query_one("#model-name", Input).value = "arbitrary-local"
            app.screen.query_one("#model-id", Input).value = "never-before-seen-model"
            app.screen.query_one("#model-url", Input).value = "http://127.0.0.1:8080/v1"
            app.screen.query_one("#model-local", Checkbox).value = True
            app.screen.query_one("#model-auth", Select).value = "none"
            await click("#model-save")
            assert controller.configuration().profiles[0].model_id == "never-before-seen-model"
            app.action_agent()
            await pilot.pause()
            app.screen.query_one("#setup-name", Input).value = "Evidence reader"
            app.screen.query_one("#setup-text", TextArea).load_text(
                "Use evidence and state uncertainty."
            )
            app.screen.query_one("#setup-profile", Select).value = "arbitrary-local"
            await click("#setup-save")
            app.action_new()
            await pilot.pause()
            app.screen.query_one("#setup-name", Input).value = "Terminal-only acceptance"
            app.screen.query_one("#setup-text", TextArea).load_text(
                "What does the evidence support?"
            )
            app.screen.query_one("#setup-members", Input).value = "Evidence reader:2"
            app.screen.query_one("#setup-execution", Select).value = "synthetic"
            await click("#setup-save")
            assert app.selected is not None
            app.action_import_source()
            await pilot.pause()
            app.screen.query_one("#file", Input).value = str(paper)
            await click("#import-save")
            app.action_start()
            await pilot.pause()
            await click("#start-save")
            for _ in range(150):
                await asyncio.sleep(0.1)
                if controller.inspect(app.selected).run.status == "completed":
                    break
            assert controller.inspect(app.selected).run.status == "completed"
            app.poll()
            bundle = controller.inspect(app.selected)
            records = [p for e in bundle.events for p in e.payload]
            claim = next(p for p in records if isinstance(p, Claim))
            source = next(p for p in records if isinstance(p, SourceDocument))
            assert any(isinstance(p, ContextManifest) for p in records)
            app.action_review()
            await pilot.pause()
            app.screen.query_one("#review-action", Select).value = "claim"
            await pilot.pause()
            app.screen.query_one("#review-target", Select).value = str(claim.id)
            app.screen.query_one("#review-actor", Select).value = str(claim.author_id)
            app.screen.query_one("#review-text", TextArea).load_text(
                "Revised with explicit evidence and uncertainty."
            )
            app.screen.query_one("#review-sources", SelectionList).select(str(source.id))
            await click("#review-save")
            revisions = [
                p
                for e in controller.inspect(app.selected).events
                for p in e.payload
                if isinstance(p, Claim) and p.revises_id
            ]
            assert revisions and revisions[-1].evidence_ids
            for operation in ("evaluate", "checkpoint"):
                app.action_review()
                await pilot.pause()
                app.screen.query_one("#review-action", Select).value = operation
                await click("#review-save")
            checkpoint = next(
                p
                for e in controller.inspect(app.selected).events
                for p in e.payload
                if isinstance(p, Checkpoint)
            )
            app.action_review()
            await pilot.pause()
            app.screen.query_one("#review-action", Select).value = "fork"
            await pilot.pause()
            app.screen.query_one("#review-target", Select).value = str(checkpoint.id)
            app.screen.query_one("#review-text", TextArea).load_text(
                "Offline test branch comparison."
            )
            await click("#review-save")
            branches = [
                p
                for e in controller.inspect(app.selected).events
                for p in e.payload
                if isinstance(p, Trajectory)
            ]
            assert len(branches) == 2
            app.action_compare()
            await pilot.pause()
            app.screen.query_one("#tool-left", Select).value = str(branches[0].id)
            app.screen.query_one("#tool-right", Select).value = str(branches[1].id)
            await click("#tool-run")
            assert "Descriptive" in app.screen.query_one("#tool-result", TextArea).text
            await click("#tool-close")
            app.action_export()
            await pilot.pause()
            app.screen.query_one("#export-path", Input).value = str(
                tmp_path / "terminal-export.json"
            )
            await click("#export-save")
            assert (
                json.loads((tmp_path / "terminal-export.json").read_text())["run"]["status"]
                == "completed"
            )
            await click("#export-close")
            await pilot.press("q")

    asyncio.run(interact())


def test_local_admission_counts_same_profile_across_instruction_versions(controller):
    from uuid import uuid4

    from doxa.core.models import Event, EventType, ModelAssignment, Trajectory
    from doxa.storage.local_dispatch import admit_local

    template = add_agent(
        controller, NewAgent(display_name="Shared", role=Role.SKEPTIC, instructions="Inspect")
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Admission",
            task=TaskSpecification(question="Inspect"),
            participants=(ParticipantGroup(agent_id=template.id, count=2),),
            idempotency_key="admission",
        ),
    )
    experiment = controller.ledger.get(run.experiment_id)
    assert isinstance(experiment, Experiment)
    branch = next(
        p.id
        for e in controller.inspect(run.id).events
        for p in e.payload
        if isinstance(p, Trajectory)
    )

    def event(index):
        assignment = ModelAssignment(
            provider="lab",
            model_id="same-model",
            settings={"profile_id": "shared", "profile_version": 1},
            instruction_version=str(index),
        )
        call = ModelCall(
            experiment_id=experiment.id,
            run_id=run.id,
            trajectory_id=branch,
            agent_id=experiment.agents[index].id,
            assignment=assignment,
            call_id=uuid4(),
            status="started",
            provenance="system_inference",
        )
        return Event(
            experiment_id=experiment.id,
            run_id=run.id,
            trajectory_id=branch,
            sequence=1,
            type=EventType.ACTION_REQUESTED,
            payload=(call,),
            idempotency_key=str(uuid4()),
            parent_event_ids=(controller.inspect(run.id).events[-1].id,),
        )

    admit_local(controller.ledger, event(0), concurrency=1, max_calls=20)
    with pytest.raises(ValueError, match="concurrency"):
        admit_local(controller.ledger, event(1), concurrency=1, max_calls=20)


def test_protected_credentials_cannot_be_put_in_profiles(controller):
    import os

    if os.name != "nt":
        pytest.skip("Windows DPAPI")
    from doxa.core.credential_store import save_credential

    secret = "synthetic-private-credential-for-test"
    save_credential(controller.settings.data_dir, "PRIVATE_TEST_KEY", secret)
    with pytest.raises(ValueError, match="Secret-bearing"):
        controller.save_configuration(
            CouncilConfig(profiles=(ModelProfile(id="bad", provider="openai", model_id=secret),))
        )


def test_long_evidence_uses_relevant_bounded_excerpt(controller):
    from uuid import uuid4

    from doxa.retrieval.excerpts import evidence_excerpt

    text = (
        "Unrelated background material. " * 100
    ) + "\n\nSpecific evidence about counterfactual revocation."
    excerpt = evidence_excerpt(
        controller.settings.database_path, uuid4(), text, "counterfactual revocation"
    )
    assert "counterfactual revocation" in excerpt and len(excerpt) < 1200
    assert "Excerpt" in excerpt


def test_unknown_required_capabilities_reject_before_creating_run(controller):
    profile = ModelProfile(
        id="text",
        provider="openai_compatible",
        local=True,
        authentication="none",
        model_id="arbitrary",
        base_url="http://127.0.0.1:8080/v1",
    )
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    template = add_agent(
        controller,
        NewAgent(
            display_name="Reader",
            role=Role.RESEARCHER,
            instructions="Inspect",
            profile_id="text",
            profile_version=1,
            remote_inference=True,
        ),
    )
    with pytest.raises(ValueError, match="capability images"):
        create_experiment(
            controller,
            NewExperiment(
                name="Unsupported modality",
                execution_kind="live",
                task=TaskSpecification(question="Inspect", required_capabilities=("images",)),
                participants=(ParticipantGroup(agent_id=template.id),),
                idempotency_key="unsupported",
            ),
        )
    assert not controller.list_runs()


def test_terminal_model_version_edit_preserves_connection_and_old_version(controller):
    from textual.widgets import Input

    from doxa.cli.console import ResearchConsole

    original = ModelProfile(
        id="versioned",
        provider="openai_compatible",
        model_id="old-model",
        repository_id="lab/model",
        local=True,
        authentication="none",
        base_url="http://127.0.0.1:8080/v1",
        temperature=0.3,
        max_context_tokens=6000,
    )
    controller.save_configuration(CouncilConfig(profiles=(original,)))

    async def interact():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(100, 36)) as pilot:
            app.selected_record = original
            app.action_model()
            await pilot.pause()
            app.screen.query_one("#model-id", Input).value = "new-model"
            app.screen.query_one("#model-save").scroll_visible(
                animate=False, immediate=True, force=True
            )
            await pilot.pause()
            await pilot.click("#model-save")
            await pilot.pause()
            latest = controller.configuration().profiles[0]
            assert latest.version == 2 and latest.model_id == "new-model"
            assert latest.repository_id == original.repository_id
            assert latest.base_url == original.base_url and latest.temperature == 0.3
            from doxa.storage.configurations import ConfigurationStore

            assert (
                ConfigurationStore(controller.settings.database_path).get("profile", "versioned", 1)
                == original
            )
            await pilot.press("q")

    asyncio.run(interact())


def test_large_history_remains_searchable_beyond_render_window(controller):
    from uuid import UUID, uuid4

    from textual.widgets import Input, Select, TabbedContent

    from doxa.cli.console import ResearchConsole
    from doxa.core.models import Claim, Event, EventType, Trajectory
    from doxa.core.workbench_demo import demonstrate

    result = asyncio.run(demonstrate(controller))
    run_id = UUID(str(result["run_id"]))
    bundle = controller.inspect(run_id)
    branch = next(p.id for e in bundle.events for p in e.payload if isinstance(p, Trajectory))
    experiment = controller.ledger.get(bundle.run.experiment_id)
    assert isinstance(experiment, Experiment)
    parent = bundle.events[-1].id
    events = []
    for index in range(1050):
        record = Claim(
            experiment_id=experiment.id,
            run_id=run_id,
            trajectory_id=branch,
            author_id=experiment.agents[0].id,
            proposition=f"history-marker-{index}: " + "Long response. " * 100,
            provenance="imported_source",
            status="proposed",
        )
        event = Event(
            experiment_id=experiment.id,
            run_id=run_id,
            trajectory_id=branch,
            sequence=1,
            type=EventType.CLAIM_PROPOSED,
            payload=(record,),
            idempotency_key="large-history:" + str(uuid4()),
            parent_event_ids=(parent,),
        )
        events.append(event)
        parent = event.id
    controller.ledger.append_batch(tuple(events))

    async def interact():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one(TabbedContent).active = "inspect"
            app.query_one("#record-kind", Select).value = "Claims"
            for _ in range(40):
                await asyncio.sleep(0.1)
                if len(app.record_map) == 1000:
                    break
            assert len(app.record_map) == 1000
            app.query_one("#filter", Input).value = "history-marker-0:"
            for _ in range(30):
                await asyncio.sleep(0.1)
                if len(app.record_map) == 1:
                    break
            assert len(app.record_map) == 1
            assert "history-marker-0:" in next(iter(app.record_map.values())).proposition
            await pilot.resize_terminal(120, 40)
            await pilot.press("q")

    asyncio.run(interact())


@pytest.mark.parametrize("provider", ["openai", "claude", "runpod"])
def test_native_remote_provider_cannot_bypass_spending_guards_with_local_flag(provider):
    from doxa.providers.registry import validate_profile

    profile = ModelProfile(
        id="guard", provider=provider, model_id="model", local=True, enabled=True
    )
    with pytest.raises(ValueError, match="loopback"):
        validate_profile(profile, {})
    with pytest.raises(ValueError, match="loopback"):
        endpoint_url(profile, {})


def test_default_research_details_are_readable_without_serialized_dictionaries():
    from doxa.cli.inspectors import readable_fields, readable_message

    summary = "\n".join(readable_fields({"citation_rate": {"value": None, "denominator": 0}}))
    assert "citation rate:" in summary and "value: unknown" in summary
    assert "denominator: 0" in summary and "{" not in summary
    message = readable_message(
        json.dumps(
            {"research_action": {"action": "claim", "proposition": "A qualified conclusion."}}
        )
    )
    assert "A qualified conclusion." in message and "{" not in message
    assert readable_message("Ordinary model prose.") == "Ordinary model prose."
