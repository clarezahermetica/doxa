"""Offline catalog/configuration acceptance, with network transports forbidden."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from textual.widgets import Checkbox, DataTable, Input, Label, Select

from doxa.cli.console import ResearchConsole
from doxa.cli.model_catalog import catalog_entries, catalog_notes, save_catalog_note, search_catalog
from doxa.cli.model_setup import ModelScreen
from doxa.cli.onboarding import GettingStarted


async def click(pilot, selector):
    from textual.css.query import NoMatches

    # A pushed screen can become active before its composed children finish mounting.
    for _ in range(200):
        await pilot.pause(0.05)
        try:
            widget = pilot.app.screen.query_one(selector)
        except NoMatches:
            continue
        if widget.is_mounted:
            break
    else:
        raise AssertionError(f"Control did not mount: {selector}")
    widget.scroll_visible(immediate=True, animate=False, force=True)
    await pilot.pause()
    assert await pilot.click(selector)
    await pilot.pause(0.35)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Model setup must not perform network requests")

    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)


def test_catalog_families_current_ids_custom_search_and_preservation(controller):
    entries = catalog_entries(controller.settings.data_dir)
    assert {
        "OpenAI",
        "Anthropic",
        "Google",
        "xAI",
        "DeepSeek",
        "Alibaba",
        "Meta",
        "Mistral AI",
        "Cohere",
        "Moonshot AI",
        "Z.ai",
        "MiniMax",
    } <= {e.developer for e in entries}
    assert any(e.kind == "family" and not e.model_id for e in entries)
    assert search_catalog(entries, "Alibaba Qwen3")[0].model_id == "Qwen/Qwen3-32B"
    assert search_catalog(entries, "claude-opus-5-5")
    assert any("retired" in e.status for e in entries)
    note = {
        "identity": {
            "developer": "My lab",
            "family": "Unusual reasoning",
            "model_id": "lab/new-checkpoint@r27",
            "display_name": "First custom checkpoint",
        },
        "registration_only": True,
    }
    save_catalog_note(controller.settings.data_dir, note)
    assert (
        search_catalog(catalog_entries(controller.settings.data_dir), "custom checkpoint")[
            0
        ].model_id
        == "lab/new-checkpoint@r27"
    )
    assert catalog_notes(controller.settings.data_dir) == [note]
    assert not controller.configuration().profiles


def test_catalog_concurrent_append_and_corruption_preserves_entries(controller):
    directory = controller.settings.data_dir
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda i: save_catalog_note(
                    directory,
                    {
                        "identity": {
                            "developer": "Lab",
                            "family": "Custom",
                            "model_id": f"checkpoint-{i}",
                        }
                    },
                ),
                range(12),
            )
        )
    assert len(catalog_notes(directory)) == 12
    path = directory / "model-catalog.json"
    path.write_text("{broken")
    with pytest.raises(ValueError):
        save_catalog_note(directory, {"identity": {}})
    assert path.read_text() == "{broken"


@pytest.mark.parametrize("size", [(80, 24), (120, 40), (160, 50)])
def test_catalog_selection_conditional_fields_fixed_actions_and_custom_save(
    controller, tmp_path, monkeypatch, size
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=size) as pilot:
            app.action_model()
            await pilot.pause(0.35)
            screen = app.screen
            assert isinstance(screen, ModelScreen)
            screen.query_one("#catalog-search", Input).value = "OpenAI gpt-6-astra"
            await pilot.pause()
            screen.query_one("#catalog-list", DataTable).focus()
            await pilot.press("enter")
            assert screen.input("model-id") == "gpt-6-astra"
            await click(pilot, "#model-next")
            screen.query_one("#model-connection", Select).value = "openai"
            await pilot.pause()
            assert not screen.query_one("#url-fields").display
            assert not screen.query_one("#artifact-fields").display
            assert not screen.query_one("#temperature-fields").display
            assert "Credentials required" in str(screen.query_one("#model-status", Label).render())
            screen.query_one("#model-connection", Select).value = "vllm"
            await pilot.pause()
            assert screen.query_one("#url-fields").display
            assert not screen.query_one("#artifact-fields").display  # proprietary selection
            await click(pilot, "#model-back")
            screen.query_one("#catalog-search", Input).value = "Other / Custom"
            await pilot.pause()
            screen.query_one("#catalog-list", DataTable).focus()
            await pilot.press("enter")
            screen.query_one("#model-id", Input).value = "unlisted/custom-checkpoint-v14"
            await click(pilot, "#model-next")
            screen.query_one("#model-name", Input).value = "local-custom"
            screen.query_one("#model-url", Input).value = "http://127.0.0.1:8098/v1"
            assert screen.query_one("#artifact-fields").display
            assert screen.can_view_entire(screen.query_one("#model-save"))
            assert screen.can_view_entire(screen.query_one("#model-cancel"))
            await click(pilot, "#model-save")
            assert len(app.screen_stack) == 1
            profile = controller.configuration().profiles[0]
            assert profile.model_id == "unlisted/custom-checkpoint-v14"
            assert profile.runtime == "openai_compatible" and profile.local and not profile.enabled
            assert not controller.ledger.records("model_call")
            assert not controller.list_runs()
            await pilot.press("q")

    asyncio.run(interaction())


def test_unsupported_native_registration_and_invalid_protocol_never_create_profile(
    controller, tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.action_model()
            await pilot.pause(0.35)
            screen = app.screen
            screen.query_one("#model-id", Input).value = "unsupported-native-model"
            await click(pilot, "#model-next")
            screen.query_one("#model-name", Input).value = "google-registration"
            screen.query_one("#model-connection", Select).value = "cohere"
            await pilot.pause()
            assert "Unsupported transport" in str(screen.query_one("#model-status", Label).render())
            assert not screen.query_one("#model-secret").display
            assert not screen.query_one("#enable-fields").display
            # A stale/tampered protocol must not silently turn a native choice into compatibility.
            screen.query_one("#model-provider", Select).value = "openai_compatible"
            await pilot.pause()
            await click(pilot, "#model-save")
            assert app.screen is screen and not controller.configuration().profiles
            screen.query_one("#model-provider", Select).value = "cohere"
            await pilot.pause()
            await click(pilot, "#model-save")
            assert not controller.configuration().profiles
            notes = catalog_notes(controller.settings.data_dir)
            assert notes[0]["registration_only"] and notes[0]["protocol"] == "cohere"
            assert not (controller.settings.data_dir / "credentials").exists()
            await pilot.press("q")

    asyncio.run(interaction())


def test_model_setup_returns_to_original_general_guide_after_save_cancel_escape(
    controller, tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "prefs"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await click(pilot, "#guide-research")
            await click(pilot, "#guide-next")
            guide = app.screen
            guide.query_one("#guide-mode", Select).value = "live"
            await pilot.pause()
            assert isinstance(guide, GettingStarted) and guide.step == 1
            await click(pilot, "#guide-do")
            await click(pilot, "#model-cancel")
            assert app.screen is guide and guide.step == 1
            await click(pilot, "#guide-do")
            await pilot.press("escape")
            assert app.screen is guide and guide.step == 1
            await click(pilot, "#guide-do")
            screen = app.screen
            screen.query_one("#model-id", Input).value = "my-lab/model"
            await click(pilot, "#model-next")
            screen.query_one("#model-name", Input).value = "lab-model"
            screen.query_one("#model-connection", Select).value = "vllm"
            await pilot.pause()
            screen.query_one("#model-url", Input).value = "http://localhost:8080/v1"
            await click(pilot, "#model-save")
            assert app.screen is guide and guide.step == 1 and guide.execution == "live"
            assert not controller.configuration().profiles[0].enabled
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_existing_workspace_checkbox_cannot_be_armed(controller):
    from doxa.cli.workspace_screen import WorkspaceScreen

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            app.action_workspace()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WorkspaceScreen)
            checkbox = screen.query_one("#workspace-create", Checkbox)
            assert checkbox.disabled and not checkbox.value
            await pilot.press("escape", "q")

    asyncio.run(interaction())


def test_same_model_different_deployments_and_pinned_same_role_assignments(controller):
    from doxa.core.models import Role, TaskSpecification
    from doxa.core.workbench import (
        NewAgent,
        NewExperiment,
        ParticipantGroup,
        add_agent,
        create_experiment,
    )
    from doxa.storage.configurations import ConfigurationStore

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with app.run_test(size=(80, 24)) as pilot:
            for index in (1, 2):
                app.action_model()
                await pilot.pause(0.35)
                screen = app.screen
                screen.query_one("#model-id", Input).value = "my-lab/same-open-weights@checkpoint7"
                await click(pilot, "#model-next")
                screen.query_one("#model-name", Input).value = f"deployment-{index}"
                screen.query_one("#model-connection", Select).value = "vllm"
                await pilot.pause()
                screen.query_one("#model-url", Input).value = f"http://localhost:80{index}0/v1"
                await click(pilot, "#model-save")
            profiles = controller.configuration().profiles
            assert len(profiles) == 2 and len({p.model_id for p in profiles}) == 1
            assert len({p.base_url for p in profiles}) == 2
            definitions = [
                add_agent(
                    controller,
                    NewAgent(
                        display_name="Researcher " + str(i),
                        role=Role.RESEARCHER,
                        instructions="Inspect supplied evidence.",
                        profile_id=p.id,
                        profile_version=p.version,
                        remote_inference=True,
                    ),
                )
                for i, p in enumerate(profiles)
            ]
            run = create_experiment(
                controller,
                NewExperiment(
                    name="Pinned shared model",
                    task=TaskSpecification(question="What is supported?"),
                    participants=tuple(
                        ParticipantGroup(agent_id=a.id, count=2) for a in definitions
                    ),
                    idempotency_key="same-model-distinct-connections",
                ),
            )
            experiment = controller.ledger.get(run.experiment_id)
            before = experiment.model_dump_json()
            app.selected_record = profiles[0]
            app.action_model()
            await pilot.pause(0.35)
            screen = app.screen
            assert screen.query_one("#model-connection", Select).value == "vllm"
            screen.query_one("#model-id", Input).value = "my-lab/a-new-checkpoint"
            await click(pilot, "#model-save")
            old = ConfigurationStore(controller.settings.database_path).get(
                "profile", profiles[0].id, 1
            )
            assert old == profiles[0]
            assert controller.ledger.get(experiment.id).model_dump_json() == before
            assert len(experiment.agents) == 4 and len({a.role for a in experiment.agents}) == 1
            assert {a.model_profile_version for a in experiment.agents} == {1}
            assert len({a.model_profile_id for a in experiment.agents}) == 2
            updated = controller.configuration().profiles[0]
            new_template = add_agent(
                controller,
                NewAgent(
                    display_name="Updated researcher",
                    role=Role.RESEARCHER,
                    instructions="Inspect evidence.",
                    profile_id=updated.id,
                    profile_version=updated.version,
                    remote_inference=True,
                ),
            )
            different = create_experiment(
                controller,
                NewExperiment(
                    name="Same role, different actual models",
                    task=TaskSpecification(question="Compare evidence"),
                    participants=(
                        ParticipantGroup(agent_id=new_template.id),
                        ParticipantGroup(agent_id=definitions[1].id),
                    ),
                    idempotency_key="same-role-different-model-identities",
                ),
            )
            participants = controller.ledger.get(different.experiment_id).agents
            assert len({a.model.model_id for a in participants}) == 2
            assert len({a.role for a in participants}) == 1
            assert controller.ledger.get(experiment.id).model_dump_json() == before
            assert not controller.ledger.records("model_call")
            await pilot.press("q")

    asyncio.run(interaction())
