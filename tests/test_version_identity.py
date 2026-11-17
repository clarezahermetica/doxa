"""Public version labels share one source; iteration IDs remain diagnostic."""

import asyncio
import json
import tomllib
from pathlib import Path

import pytest
from textual.widgets import Label
from typer.testing import CliRunner

from doxa import __version__
from doxa.api.app import create_app
from doxa.cli.console import ResearchConsole
from doxa.cli.main import app
from doxa.cli.reference import CommandReference
from doxa.core.runtime_identity import runtime_identity
from doxa.version import ARCHIVE_NAME, DISPLAY_VERSION, TERMINAL_BUILD, VERSION, WINDOWS_VERSION


def test_public_and_machine_versions_have_one_source(tmp_path):
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert VERSION == __version__ == "0.1.0a1"
    assert "version" in metadata["project"]["dynamic"]
    assert "version" not in metadata["project"]
    assert metadata["tool"]["hatch"]["version"]["path"] == "src/doxa/version.py"
    assert DISPLAY_VERSION == "DOXA 0.1.0 Alpha 1"
    assert ARCHIVE_NAME == "DOXA-0.1.0a1-Windows.zip"
    assert WINDOWS_VERSION == (0, 1, 0, 1)
    assert create_app().openapi()["info"]["version"] == VERSION
    cli = CliRunner()
    assert cli.invoke(app, ["--version"]).stdout.strip() == DISPLAY_VERSION
    assert DISPLAY_VERSION in cli.invoke(app, ["--help"]).stdout
    diagnostics = runtime_identity(tmp_path)
    assert diagnostics["application_version"] == VERSION
    assert diagnostics["display_version"] == DISPLAY_VERSION
    assert diagnostics["terminal_build"] == TERMINAL_BUILD


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_terminal_about_and_help_use_public_label(controller, monkeypatch, tmp_path, size):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "client"))

    async def check():
        console = ResearchConsole(controller.settings.data_dir, show_guide=False)
        async with console.run_test(size=size) as pilot:
            await pilot.pause()
            assert DISPLAY_VERSION in console.title
            assert TERMINAL_BUILD not in console.title
            assert console.unavailable_reason("about") == ""
            console.action_about()
            await pilot.pause()
            assert DISPLAY_VERSION in console.screen.query_one(Label).render().plain
            await pilot.press("escape")
            console.action_help()
            await pilot.pause()
            assert isinstance(console.screen, CommandReference)
            assert (
                DISPLAY_VERSION
                in console.screen.query_one("#reference-title", Label).render().plain
            )

    asyncio.run(check())


def test_installer_keeps_legacy_layout_and_product_identity(windows_package):
    # Share the existing isolated Windows installer fixture without touching user PATH.
    from test_installation_entry import installation_script

    package, installed, registry, _ = windows_package
    manifest = package / "package-manifest.json"
    data = json.loads(manifest.read_text())
    data.update(version=VERSION, display_name=DISPLAY_VERSION)
    manifest.write_text(json.dumps(data))
    result = installation_script(
        package,
        "Install-DOXA.ps1",
        "-PackageRoot",
        package,
        "-InstallRoot",
        installed,
        "-EnvironmentKey",
        registry,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert DISPLAY_VERSION in result.stdout
    saved = json.loads((installed / "install-manifest.json").read_text(encoding="utf-8-sig"))
    assert saved["version"] == VERSION and saved["display_name"] == DISPLAY_VERSION
    assert saved["build"] == "v16"
    assert (installed / "versions/v16/DOXA/doxa.exe").exists()


# Fixtures are imported explicitly so this module also runs independently.
from test_installation_entry import windows_package as windows_package  # noqa: E402
