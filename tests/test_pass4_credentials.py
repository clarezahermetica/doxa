"""Dummy credentials with arbitrary authentication references must not enter research history."""

import json
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest

from doxa.core.memory_commands import ProposeMemory
from doxa.core.models import Agent, Role, TaskSpecification
from doxa.core.profiles import AgentDefinition, CouncilConfig, ModelProfile
from doxa.core.secrets import reject_secrets, safe_text, secret_values
from doxa.core.workbench import (
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)

DUMMY = "pass4-fake-authentication-value-not-a-real-credential"


@pytest.mark.parametrize("decrypt", [False, True])
def test_os_credentials_refuse_non_windows_without_touching_native_apis(monkeypatch, decrypt):
    from doxa.core import credential_store

    with monkeypatch.context() as platform:
        platform.setattr(credential_store.sys, "platform", "linux")
        with pytest.raises(ValueError, match="requires Windows"):
            credential_store._protect(b"synthetic-credential", decrypt=decrypt)


def credential_file(controller):
    path = controller.settings.data_dir / ".env"
    path.write_text("CANONICAL_AUTH=" + DUMMY + "\n")
    return ModelProfile(
        id="custom-auth",
        provider="openai",
        model_id="unverified-fixture",
        credential_env="CANONICAL_AUTH",
        enabled=False,
    )


@pytest.mark.parametrize("surface", ["source", "memory"])
def test_custom_credential_reference_is_protected_at_research_persistence_boundary(
    controller, surface
):
    profile = credential_file(controller)
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    actor = add_agent(
        controller,
        NewAgent(display_name="Reader", role=Role.RESEARCHER, instructions="Read evidence."),
    )
    run = create_experiment(
        controller,
        NewExperiment(
            name="Credential boundary",
            task=TaskSpecification(question="Offline question"),
            participants=(ParticipantGroup(agent_id=actor.id),),
            idempotency_key="secret-boundary",
        ),
    )
    before = controller.inspect(run.id).model_dump_json()
    with pytest.raises(ValueError, match="Secret-bearing"):
        if surface == "source":
            import_source(
                controller,
                run.id,
                ImportSource(title="Untrusted input", text=DUMMY, idempotency_key="reject-secret"),
            )
        else:
            controller.propose_memory(
                run.id, ProposeMemory(text=DUMMY, scope="shared", idempotency_key="reject-secret")
            )
    assert controller.inspect(run.id).model_dump_json() == before


def test_incoming_configuration_auth_reference_is_checked_before_first_profile_save(controller):
    profile = credential_file(controller)
    actor = Agent(role=Role.RESEARCHER, instructions=DUMMY)
    definition = AgentDefinition(id=actor.id, display_name="Unsafe instructions", agent=actor)
    with pytest.raises(ValueError, match="Secret-bearing"):
        controller.save_configuration(CouncilConfig(profiles=(profile,), agents=(definition,)))
    assert not controller.configuration().profiles and not controller.configuration().agents


def test_historical_short_alias_shadowed_values_and_json_encodings(controller, monkeypatch):
    directory = controller.settings.data_dir
    old = ModelProfile(
        id="historical-auth",
        provider="openai",
        model_id="unknown",
        credential_env="OLD_AUTH",
        enabled=False,
    )
    controller.save_configuration(CouncilConfig(profiles=(old,)))
    controller.save_configuration(
        CouncilConfig(
            profiles=(old.model_copy(update={"version": 2, "credential_env": "NEW_AUTH"}),)
        )
    )
    directory.joinpath(".env").write_text("OLD_AUTH=short!\nNEW_AUTH=dotenv-pass4-dummy\n")
    monkeypatch.setenv("NEW_AUTH", "environment-pass4-dummy")
    monkeypatch.setattr(
        "doxa.core.credential_store.load_credentials",
        lambda _: {"NEW_AUTH": "protected-pass4-dummy"},
    )
    values = secret_values(directory)
    for value in (
        "short!",
        "dotenv-pass4-dummy",
        "environment-pass4-dummy",
        "protected-pass4-dummy",
    ):
        assert value in values
        escaped = "".join(f"\\u{ord(char):04x}" for char in value)
        for representation in (
            value,
            json.dumps({"text": value}),
            '{"text":"' + escaped + '"}',
            json.dumps(json.dumps({"text": value})),
        ):
            with pytest.raises(ValueError, match="Secret-bearing"):
                reject_secrets(representation, directory)
            assert value not in safe_text(representation, directory=directory)
    control = '{ "question": "Research evidence", "unknown_usage": null, "nested": [1, true] }'
    reject_secrets(control, directory)
    assert safe_text(control, directory=directory) == control


def test_json_escaped_quote_and_unicode_credentials(controller, monkeypatch):
    value = 'pass4-quote-"-slash-\\-line-\n-é'
    monkeypatch.setattr("doxa.core.credential_store.load_credentials", lambda _: {"AUTH": value})
    for ensure_ascii in (True, False):
        content = json.dumps({"text": value}, ensure_ascii=ensure_ascii)
        with pytest.raises(ValueError, match="Secret-bearing"):
            reject_secrets(content, controller.settings.data_dir)


def test_overwritten_json_members_cannot_hide_escaped_credentials(controller):
    profile = credential_file(controller)
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    escaped = "".join(f"\\u{ord(char):04x}" for char in DUMMY)
    content = '{"text":"' + escaped + '","text":"harmless"}'
    for representation in (content, json.dumps({"text": content})):
        with pytest.raises(ValueError, match="Secret-bearing"):
            reject_secrets(representation, controller.settings.data_dir)


@pytest.mark.parametrize("unsafe", [False, True])
def test_original_compressed_document_metadata_is_checked_before_artifact_write(
    controller, command, unsafe
):
    import base64
    import io
    import zipfile

    from doxa.core.secrets import reject_artifact_secrets
    from doxa.core.workbench import ImportDocument, import_document

    run = controller.configure_run(command)
    profile = credential_file(controller)
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Ordinary source</w:t></w:r></w:p></w:body></w:document>',
        )
        archive.writestr("docProps/core.xml", DUMMY if unsafe else "Ordinary document metadata")
    data = stream.getvalue()
    before = controller.inspect(run.id).model_dump_json()
    artifacts = set((controller.settings.data_dir / "artifacts").rglob("*"))
    instruction = ImportDocument(
        filename="paper.docx",
        data_base64=base64.b64encode(data).decode(),
        idempotency_key="compressed-credential",
    )
    if unsafe:
        with pytest.raises(ValueError, match="Secret-bearing"):
            import_document(controller, run.id, instruction)
        with pytest.raises(ValueError, match="Secret-bearing"):
            reject_artifact_secrets(data, controller.settings.data_dir)
        assert controller.inspect(run.id).model_dump_json() == before
        assert set((controller.settings.data_dir / "artifacts").rglob("*")) == artifacts
    else:
        assert import_document(controller, run.id, instruction).original is not None


def test_response_rejection_precedes_artifacts_and_accounting(controller):
    from doxa.core.execution import Runtime
    from doxa.core.models import ModelAssignment
    from doxa.providers.contracts import ModelResponse

    profile = credential_file(controller)
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    runtime = Runtime.__new__(Runtime)
    runtime.controller = controller
    runtime.store = Mock()
    runtime.calls = Mock()
    response = ModelResponse(
        call_id=uuid4(),
        assignment=ModelAssignment(provider="openai", model_id="unknown", instruction_version="1"),
        text=DUMMY,
        execution_kind="live",
    )
    with pytest.raises(ValueError, match="Secret-bearing"):
        runtime.record_response(
            response,
            Agent(role=Role.RESEARCHER, instructions="Guard fixture"),
            "guard",
            0,
            Decimal("0"),
            Mock(),
        )
    runtime.store.put.assert_not_called()
    assert not runtime.calls.mock_calls


@pytest.mark.parametrize("format", ["json", "jsonl"])
def test_legacy_export_refuses_current_credentials_without_rewriting_history(
    controller, command, tmp_path, format
):
    from doxa.core.exports import export_jsonl, export_run

    # A legacy record existed before this new alias was registered as a credential.
    run = controller.configure_run(
        command.model_copy(
            update={"experiment": command.experiment.model_copy(update={"name": DUMMY})}
        )
    )
    before = controller.inspect(run.id).model_dump_json()
    profile = credential_file(controller)
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    destination = tmp_path / ("unsafe-export." + format)
    with pytest.raises(ValueError, match="Secret-bearing"):
        (export_run if format == "json" else export_jsonl)(controller, run.id, destination)
    assert not destination.exists()
    assert controller.inspect(run.id).model_dump_json() == before
