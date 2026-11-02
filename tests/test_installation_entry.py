"""One CLI, independent of the working directory; no real provider requests."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from doxa.cli.main import app
from doxa.core.workspaces import default_workspace


def test_version_is_available_without_opening_the_console(monkeypatch):
    from doxa.cli.console import ResearchConsole

    monkeypatch.setattr(
        ResearchConsole,
        "run",
        lambda self: (_ for _ in ()).throw(AssertionError("Version must not open the viewer")),
    )
    result = CliRunner().invoke(app, ["--version"])
    from doxa.version import TERMINAL_BUILD

    assert result.exit_code == 0 and TERMINAL_BUILD in result.stdout


def test_publication_metadata_and_help_expose_only_terminal_clients():
    import tomllib

    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["scripts"] == {"doxa": "doxa.cli.main:app"}
    assert "desktop" not in metadata["project"]["optional-dependencies"]
    help_text = CliRunner().invoke(app, ["--help"]).stdout
    assert "desktop" not in help_text.lower() and "studio" not in help_text.lower()


def test_unselected_workspace_is_not_inferred_from_current_directory(
    controller, tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "new-client"))
    monkeypatch.delenv("DOXA_DATA_DIR", raising=False)
    project = tmp_path / "unrelated-project"
    project.mkdir()
    (project / ".doxa").mkdir()
    (project / ".doxa/ledger.sqlite3").write_bytes(controller.settings.database_path.read_bytes())
    monkeypatch.chdir(project)
    assert default_workspace() == tmp_path / "new-client/DOXA/workspace"
    assert not default_workspace().exists()


def test_default_command_opens_the_existing_console_without_changing_history(
    controller, monkeypatch
):
    from doxa.cli.console import ResearchConsole

    monkeypatch.setenv("DOXA_DATA_DIR", str(controller.settings.data_dir))
    opened = []
    monkeypatch.setattr(
        ResearchConsole, "run", lambda self: opened.append(self.controller.settings.data_dir)
    )
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0 and opened == [controller.settings.data_dir]
    assert not controller.list_runs()
    assert CliRunner().invoke(app, ["--help"]).exit_code == 0


@pytest.fixture
def windows_package(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows per-user installation")
    import shutil
    import winreg

    root = Path(__file__).resolve().parents[1]
    package = tmp_path / "release files"
    (package / "DOXA").mkdir(parents=True)
    (package / "DOXA/doxa.exe").write_bytes(b"owned test payload; never executed")
    for name in ("Install-DOXA.ps1", "Uninstall-DOXA.ps1", "DOXA-InstallCommon.ps1"):
        shutil.copyfile(root / "scripts/windows" / name, package / name)
    (package / "INSTALLATION.md").write_text("Isolated installation test")
    files = [
        {
            "path": p.relative_to(package).as_posix(),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in package.rglob("*")
        if p.is_file()
    ]
    (package / "package-manifest.json").write_text(
        json.dumps({"application": "DOXA", "format": 1, "build": "v16", "files": files})
    )
    key_name = "Software\\DOXA\\InstallTests\\" + uuid4().hex + "\\Environment"
    original = r"C:\ExistingTools;%SystemRoot%\System32"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_name) as key:
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, original)
    yield package, tmp_path / "Installed app Ω", key_name, original
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name, 0, winreg.KEY_SET_VALUE) as key:
        winreg.DeleteValue(key, "Path")
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_name)
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_name.rsplit("\\", 1)[0])


def installation_script(package, script, *arguments, extra_path=""):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    env = dict(os.environ)
    env["PATH"] = (
        extra_path
        + os.pathsep
        + str(powershell.parent)
        + os.pathsep
        + str(Path(os.environ["SystemRoot"]) / "System32")
    )
    return subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(package / script),
            *map(str, arguments),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        env=env,
    )


def test_installation_is_idempotent_and_uninstall_preserves_user_data(
    windows_package, controller, command
):
    import winreg

    package, installed, registry, before = windows_package
    run = controller.configure_run(command)
    history = controller.inspect(run.id)
    for _ in range(2):
        result = installation_script(
            package,
            "Install-DOXA.ps1",
            "-PackageRoot",
            package,
            "-InstallRoot",
            installed,
            "-EnvironmentKey",
            registry,
            "-AddToPath",
        )
        assert result.returncode == 0, result.stdout + result.stderr
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry) as key:
        path, kind = winreg.QueryValueEx(key, "Path")
        assert path == before + ";" + str(installed / "bin") and kind == winreg.REG_EXPAND_SZ
    unknown = installed / "user-exports/keep.txt"
    unknown.parent.mkdir()
    unknown.write_text("user-owned research export")
    result = installation_script(installed, "Uninstall-DOXA.ps1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert unknown.read_text() == "user-owned research export"
    assert not (installed / "bin/doxa.cmd").exists()
    assert not (installed / "versions/v16/DOXA/doxa.exe").exists()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry) as key:
        assert winreg.QueryValueEx(key, "Path") == (before, winreg.REG_EXPAND_SZ)
    assert controller.inspect(run.id) == history


def test_existing_doxa_command_blocks_registration(windows_package, tmp_path):
    package, installed, registry, _ = windows_package
    conflict = tmp_path / "existing-command"
    conflict.mkdir()
    (conflict / "doxa.cmd").write_text("@exit /b 0")
    result = installation_script(
        package,
        "Install-DOXA.ps1",
        "-InstallRoot",
        installed,
        "-EnvironmentKey",
        registry,
        "-AddToPath",
        extra_path=str(conflict),
    )
    assert result.returncode != 0 and "Another command" in result.stderr
    assert not installed.exists()


def test_modified_installed_files_block_uninstall_before_path_change(windows_package):
    import winreg

    package, installed, registry, _ = windows_package
    result = installation_script(
        package,
        "Install-DOXA.ps1",
        "-InstallRoot",
        installed,
        "-EnvironmentKey",
        registry,
        "-AddToPath",
    )
    assert result.returncode == 0, result.stderr
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry) as key:
        before = winreg.QueryValueEx(key, "Path")
    executable = installed / "versions/v16/DOXA/doxa.exe"
    executable.write_bytes(b"user-modified installed file")
    result = installation_script(installed, "Uninstall-DOXA.ps1")
    assert result.returncode != 0 and "Modified installation files" in result.stderr
    assert executable.read_bytes() == b"user-modified installed file"
    assert (installed / "install-manifest.json").is_file()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry) as key:
        assert winreg.QueryValueEx(key, "Path") == before


def test_corrupt_package_and_unrelated_destination_are_preserved(windows_package):
    package, installed, registry, _ = windows_package
    installed.mkdir()
    (installed / "keep.txt").write_text("unrelated")
    result = installation_script(
        package, "Install-DOXA.ps1", "-InstallRoot", installed, "-EnvironmentKey", registry
    )
    assert result.returncode != 0 and (installed / "keep.txt").read_text() == "unrelated"
    (package / "DOXA/doxa.exe").write_bytes(b"tampered payload")
    result = installation_script(
        package, "Install-DOXA.ps1", "-InstallRoot", installed, "-EnvironmentKey", registry
    )
    assert result.returncode != 0 and "integrity" in result.stderr
    assert (installed / "keep.txt").read_text() == "unrelated"
