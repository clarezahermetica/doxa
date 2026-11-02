"""Rendered Help, real command callbacks and appearance persistence; no inference."""

import asyncio
import json

import pytest
from textual.command import CommandPalette
from textual.widgets import Button, DataTable, Input, TextArea

from doxa.cli.console import ResearchConsole
from doxa.cli.reference import CommandReference, command_reference


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_rendered_help_theme_callback_and_reference_availability(
    controller, tmp_path, monkeypatch, size, theme
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "preferences"))

    async def interaction():
        app = ResearchConsole(controller.settings.data_dir, show_guide=False)
        app.theme = theme
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await pilot.press("f1")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandReference)
            entries = command_reference(app)
            assert all(e.description.strip() and e.detail.strip() for e in entries)
            assert not any("Textual" in e.detail for e in entries)
            screen.query_one(Input).value = "theme"
            await pilot.pause()
            entry = next(e for e in screen.matches if e.title == "Theme")
            screen.query_one(DataTable).move_cursor(row=screen.matches.index(entry))
            await pilot.pause()
            assert screen.current == entry
            detail = screen.query_one(TextArea).text
            assert "Change DOXA's color theme." in detail
            assert "Press Ctrl+P, select Theme, and choose a color scheme." in detail
            assert "Your selection is saved automatically." in detail
            assert entry.callback == app.action_change_theme
            button = screen.query_one("#reference-run", Button)
            assert not button.disabled
            assert button.region.bottom <= size[1]
            assert screen.query_one("#reference-dialog").region.height <= 23
            assert await pilot.click("#reference-run")
            await pilot.pause()
            assert isinstance(app.screen, CommandPalette)
            await pilot.press("n", "o", "r", "d")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.theme == "nord"
            appearance = tmp_path / "preferences/DOXA/appearance.json"
            assert json.loads(appearance.read_text())["theme"] == "nord"
            await pilot.press("f1")
            await pilot.pause()
            screen = app.screen
            screen.query_one(Input).value = "Start selected run"
            await pilot.pause()
            assert screen.current.unavailable
            assert screen.query_one("#reference-run", Button).disabled
            assert "Unavailable:" in screen.query_one(TextArea).text
            screen.query_one(Input).value = "doxa run start"
            await pilot.pause()
            assert screen.current.title == "doxa run start"
            assert screen.query_one("#reference-run", Button).disabled
            assert str(screen.query_one("#reference-run", Button).label) == "Reference only"
            assert "System shell only" in screen.query_one(TextArea).text
            await pilot.press("escape")
            await pilot.press("q")
        restarted = ResearchConsole(controller.settings.data_dir, show_guide=False)
        assert restarted.theme == "nord"

    asyncio.run(interaction())
