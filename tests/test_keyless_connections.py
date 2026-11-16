"""Connection setup uses dummy credentials and offline HTTP fixtures."""

import asyncio
import json
import sys
from importlib import import_module
from types import SimpleNamespace

import httpx
import pytest
from textual.widgets import Checkbox, Input, Select

from doxa.cli.model_setup import ModelScreen
from doxa.core import credential_store as store
from doxa.core.controller import Controller
from doxa.core.profiles import CouncilConfig, ModelProfile
from doxa.core.secrets import reject_secrets, safe_text, workspace_env
from doxa.providers.discovery import describe_connection, discover_models
from doxa.storage.configurations import ConfigurationStore

DUMMY = "unit-fixture-value-with-no-external-privilege"


def local_profile(provider="ollama", **updates):
    values = {
        "id": "fixture",
        "provider": provider,
        "adapter": "openai_compatible",
        "local": True,
        "base_url": "http://127.0.0.1:1234/v1",
        "model_id": "arbitrary/model:v123",
        "authentication": "none",
        "credential_env": None,
        **updates,
    }
    return ModelProfile.model_validate(values)


@pytest.mark.parametrize(
    ("runtime", "route", "payload"),
    [
        ("ollama", "/api/tags", {"models": [{"name": "arbitrary/model:v123"}]}),
        ("lmstudio", "/v1/models", {"data": [{"id": "arbitrary/model:v123"}]}),
        ("custom", "/v1/models", {"data": [{"id": "arbitrary/model:v123"}]}),
    ],
)
def test_discovery_keyless_metadata_only(runtime, route, payload):
    def handler(request):
        assert request.method == "GET" and request.url.path == route
        assert "Authorization" not in request.headers
        assert request.content == b""
        return httpx.Response(200, json=payload)

    report = asyncio.run(
        discover_models(
            local_profile(runtime),
            {},
            authorize_network=True,
            transport=httpx.MockTransport(handler),
        )
    )
    assert report.runtime_reachable and report.model_listed
    assert report.credential_status == "not_required"
    assert not report.generation_verified
    assert "Inference untested" in describe_connection(report)


@pytest.mark.parametrize(
    "url",
    [
        "http://192.0.2.1/v1",
        "http://@127.0.0.1/v1",
        "http://localhost:invalid/v1",
        "http://127.0.0.1/v1?",
        "http://localhost/v1#",
        "http://localhost/v1" + chr(92) + "other",
    ],
)
def test_invalid_loopback_endpoints_never_send_request(url):
    report = asyncio.run(
        discover_models(
            local_profile(base_url=url),
            {},
            authorize_network=True,
            transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected request")),
        )
    )
    assert report.status == "unavailable" and report.runtime_reachable is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "https://redirect.invalid/"}),
        httpx.Response(200, json={"models": {"not": "a list"}}),
        httpx.Response(200, json={"models": [{"name": "terminal" + chr(27)}]}),
    ],
)
def test_redirect_or_bad_metadata_is_not_listed(response):
    attempts = []

    def handler(request):
        attempts.append(request.url.host)
        return response

    report = asyncio.run(
        discover_models(
            local_profile(), {}, authorize_network=True, transport=httpx.MockTransport(handler)
        )
    )
    assert attempts == ["127.0.0.1"]
    assert report.status == "unavailable" and report.runtime_reachable
    assert not report.model_ids


def test_connection_failure_and_credential_echo_are_safe():
    def unavailable(request):
        raise httpx.ConnectError(DUMMY, request=request)

    profile = local_profile(authentication="bearer", credential_env="CUSTOM_AUTH")
    env = {"CUSTOM_AUTH": DUMMY}

    def check(handler):
        return asyncio.run(
            discover_models(
                profile, env, authorize_network=True, transport=httpx.MockTransport(handler)
            )
        )

    report = check(unavailable)
    assert not report.runtime_reachable and DUMMY not in report.model_dump_json()
    report = check(
        lambda request: httpx.Response(
            200, json={"models": [{"name": request.headers["Authorization"]}]}
        )
    )
    assert report.runtime_reachable and not report.model_ids


class FakeVault:
    __module__ = "keyring.backends.SecretService"
    priority = 5
    entries = {}

    def get_password(self, service, username):
        return self.entries.get((service, username))

    def set_password(self, service, username, value):
        self.entries[service, username] = value

    def delete_password(self, service, username):
        del self.entries[service, username]


def test_os_vault_lifecycle_no_fallback_or_profile_rewrite(controller, monkeypatch):
    directory = controller.settings.data_dir
    FakeVault.entries = {}
    monkeypatch.setattr(store, "import_module", lambda _: SimpleNamespace(Keyring=FakeVault))
    # Only select the fake vault on the host; do not change pathlib's runtime platform.
    with monkeypatch.context() as platform:
        platform.setattr(store, "sys", SimpleNamespace(platform="linux"))
        reference = store.create_credential(directory, DUMMY)
        monkeypatch.setenv(reference, "untrusted-fallback-fixture")
        profile = ModelProfile(
            id="remote",
            provider="openai",
            model_id="arbitrary",
            credential_env=reference,
        )
        controller.save_configuration(CouncilConfig(profiles=(profile,)))
        assert workspace_env(directory)[reference] == DUMMY
        assert all(
            DUMMY.encode() not in path.read_bytes()
            for path in (directory / "credentials").iterdir()
        )
        assert safe_text(DUMMY, directory=directory) == "[REDACTED]"
        with pytest.raises(ValueError, match="Secret-bearing"):
            reject_secrets(json.dumps({"diagnostic": DUMMY}), directory)
        replacement = DUMMY + "-rotated"
        store.replace_credential(directory, reference, replacement)
        assert workspace_env(directory)[reference] == replacement
        store.delete_credential(directory, reference)
        assert reference not in workspace_env(directory)
        assert (
            ConfigurationStore(controller.settings.database_path).get(
                "profile", profile.id, profile.version
            )
            == profile
        )


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_unavailable_or_insecure_vault_cannot_store_plaintext(tmp_path, monkeypatch, platform):
    class Plaintext:
        priority = 10

        def set_password(self, *args):
            pytest.fail("Insecure fallback must not be called")

    monkeypatch.setattr(store, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(store, "import_module", lambda _: SimpleNamespace(Keyring=Plaintext))
    with pytest.raises(ValueError, match="Secure credential could not be saved"):
        store.create_credential(tmp_path, DUMMY)
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(
        store, "import_module", lambda _: import_module("malformed_fixture_package")
    )
    with pytest.raises(ValueError, match="Secure credential could not be saved"):
        store.create_credential(tmp_path, DUMMY)
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows DPAPI")
def test_windows_dummy_dpapi_rotation_and_delete(tmp_path):
    reference = store.create_credential(tmp_path, DUMMY)
    target = tmp_path / "credentials" / (reference + ".dpapi")
    assert DUMMY.encode() not in target.read_bytes()
    assert store.load_credentials(tmp_path)[reference] == DUMMY
    store.replace_credential(tmp_path, reference, DUMMY + "-new")
    assert store.load_credentials(tmp_path)[reference] == DUMMY + "-new"
    store.delete_credential(tmp_path, reference)
    assert reference not in store.load_credentials(tmp_path)
    assert not target.exists()


def test_loopback_terminal_picker_and_restart_without_vault(controller, monkeypatch):
    from textual.app import App

    async def discover(profile, env, **kwargs):
        return await discover_models(
            profile,
            env,
            **kwargs,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"models": [{"name": profile.model_id + ":7"}]})
            ),
        )

    monkeypatch.setattr("doxa.providers.discovery.discover_models", discover)

    class TestApp(App):
        def on_mount(self):
            self.push_screen(ModelScreen(controller))

    async def scenario():
        async with TestApp().run_test(size=(80, 24)) as pilot:
            screen = pilot.app.screen
            screen.query_one("#model-local-setup").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#model-connection", Select).value == "ollama"
            assert not screen.query_one("#credential-fields").display
            await screen.discover_local()
            screen.query_one("#model-discovered", Select).value = "unselected:7"
            await pilot.pause()
            assert screen.query_one("#model-id", Input).value == "unselected:7"
            await screen.save()
        reopened = Controller(controller.settings)
        (profile,) = reopened.configuration().profiles
        assert profile.local and profile.model_id == "unselected:7"
        assert profile.authentication == "none" and profile.credential_env is None
        assert not profile.enabled

    asyncio.run(scenario())


def test_corrupt_protected_file_does_not_block_local_setup(tmp_path):
    directory = tmp_path / "credentials"
    directory.mkdir()
    (directory / "BROKEN.dpapi").write_bytes(b"not-a-protected-value")
    assert "BROKEN" not in workspace_env(tmp_path)
    assert local_profile().authentication == "none"


def test_keychain_selection_uses_builtin_class(tmp_path, monkeypatch):
    class Keychain(FakeVault):
        __module__ = "keyring.backends.macOS"
        entries = {}

    monkeypatch.setattr(store, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(store, "import_module", lambda _: SimpleNamespace(Keyring=Keychain))
    ref = store.create_credential(tmp_path, DUMMY)
    assert store.load_credentials(tmp_path)[ref] == DUMMY
    store.delete_credential(tmp_path, ref)


def test_keyless_http_does_not_add_auth_header():
    from test_cli_session import request

    from doxa.providers.wire import serialize

    profile = local_profile()
    route, headers, body = serialize(profile, request(profile), "")
    assert route == "/chat/completions" and "Authorization" not in headers
    assert body["model"] == profile.model_id


def test_different_workspace_does_not_resolve_vault_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(store, "import_module", lambda _: SimpleNamespace(Keyring=FakeVault))
    reference = store.create_credential(tmp_path / "first", DUMMY)
    assert reference not in workspace_env(tmp_path / "second")


def test_cli_profile_inspection_never_infers_or_probes_implicitly(controller, monkeypatch):
    from typer.testing import CliRunner

    from doxa.cli.main import app

    profile = local_profile()
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    calls = []

    async def check(profile, env, **kwargs):
        calls.append(kwargs)
        return await discover_models(
            profile,
            env,
            **kwargs,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"models": [{"name": profile.model_id}]})
            ),
        )

    monkeypatch.setattr("doxa.providers.discovery.discover_models", check)
    base = [
        "models",
        "--check",
        profile.id,
        "--json",
        "--data-dir",
        str(controller.settings.data_dir),
    ]
    first = CliRunner().invoke(app, base)
    assert first.exit_code == 0, first.output
    report = json.loads(first.output)
    assert report["metadata"] is None and not report["execution_authorized"]
    assert not calls
    second = CliRunner().invoke(app, base + ["--authorize-network"])
    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["metadata"]["model_listed"]
    assert calls == [{"authorize_network": True}]


def test_backup_refuses_preexisting_value_now_registered_as_credential(
    controller, tmp_path_factory, monkeypatch, command
):
    from doxa.storage.backup import backup_workspace

    experiment = command.experiment.model_copy(update={"name": DUMMY})
    controller.configure_run(command.model_copy(update={"experiment": experiment}))
    directory = controller.settings.data_dir
    profile = ModelProfile(
        id="legacy", provider="openai", model_id="arbitrary", credential_env="LEGACY_ALIAS"
    )
    controller.save_configuration(CouncilConfig(profiles=(profile,)))
    monkeypatch.setenv("LEGACY_ALIAS", DUMMY)
    target = tmp_path_factory.mktemp("isolated-keyless-backup") / "rejected"
    with pytest.raises(ValueError, match="Secret-bearing history"):
        backup_workspace(directory, target)
    assert not target.exists()
    assert controller.configuration().profiles == (profile,)


def test_ready_profile_edit_preserves_original_agent_assignment(controller, monkeypatch):
    from textual.app import App

    from doxa.core.models import Agent, Role
    from doxa.core.profiles import AgentDefinition

    directory = controller.settings.data_dir
    legacy = ModelProfile(id="api", provider="openai", model_id="custom/owned", enabled=False)
    agent = Agent(role=Role.RESEARCHER, instructions="Use fixture sources.")
    definition = AgentDefinition(
        id=agent.id,
        agent=agent,
        display_name="Fixture",
        model_profile_id=legacy.id,
        model_profile_version=1,
    )
    controller.save_configuration(CouncilConfig(profiles=(legacy,), agents=(definition,)))
    monkeypatch.setenv("RUNPOD_API_KEY", DUMMY)
    monkeypatch.setattr(store, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(store, "import_module", lambda _: SimpleNamespace(Keyring=FakeVault))

    class TestApp(App):
        def on_mount(self):
            self.push_screen(ModelScreen(controller, legacy))

    async def scenario():
        async with TestApp().run_test(size=(120, 40)) as pilot:
            screen = pilot.app.screen
            screen.query_one("#model-migrate-secret", Checkbox).value = True
            await screen.save()

    asyncio.run(scenario())
    reopened = Controller(controller.settings)
    (profile,) = reopened.configuration().profiles
    assert profile.version == 2 and profile.credential_env.startswith(store.MANAGED_PREFIX)
    assert workspace_env(directory)[profile.credential_env] == DUMMY
    assert workspace_env(directory)["RUNPOD_API_KEY"] == DUMMY
    assert ConfigurationStore(reopened.settings.database_path).get("profile", "api", 1) == legacy
    assert reopened.configuration().agents == (definition,)



def test_credential_input_never_copies_and_terminal_fatal_error_has_no_locals(
    controller, monkeypatch
):
    from textual.app import App

    from doxa.cli.console import ResearchConsole
    from doxa.cli.model_setup import SecretInput

    class TestApp(App):
        def compose(self):
            yield SecretInput(password=True)

    async def clipboard():
        async with TestApp().run_test() as pilot:
            field = pilot.app.query_one(SecretInput)
            field.value = DUMMY
            field.focus()
            field.action_select_all()
            field.action_copy()
            field.action_cut()
            assert DUMMY not in pilot.app.clipboard
            assert not field.value

    asyncio.run(clipboard())
    app = ResearchConsole(controller.settings.data_dir, show_guide=False)
    messages = []
    monkeypatch.setattr(app, "panic", lambda *parts: messages.extend(parts))
    try:
        raise RuntimeError(DUMMY)
    except RuntimeError:
        app._fatal_error()
    assert messages and DUMMY not in str(messages)



def test_invalid_httpx_hostname_is_a_safe_non_dispatch_error():
    profile = local_profile(
        "custom", local=False, base_url="https://" + chr(0x200D) + ".invalid/v1"
    )
    report = asyncio.run(
        discover_models(
            profile,
            {},
            authorize_network=True,
            transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected request")),
        )
    )
    assert report.status == "unavailable"
    assert report.runtime_reachable is None
