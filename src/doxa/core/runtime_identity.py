"""Read-only launch identity. Never execute an installed binary to inspect it."""

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from doxa.version import TERMINAL_BUILD, VERSION


def runtime_identity(workspace: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    installed = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs/DOXA/bin/doxa.cmd"
    )
    build = None
    if installed.is_file():
        match = re.search(r"versions[\\/]([^\\/]+)[\\/]", installed.read_text(errors="replace"))
        build = match[1] if match else None
    commit = None
    git = root / ".git"
    if not getattr(sys, "frozen", False) and git.is_dir():
        try:
            head = (git / "HEAD").read_text().strip()
            if head.startswith("ref: "):
                ref = head[5:]
                candidate = (git / ref).resolve()
                if candidate.is_relative_to(git.resolve()) and candidate.is_file():
                    commit = candidate.read_text().strip()
                elif (git / "packed-refs").is_file():
                    commit = next(
                        (
                            line.split()[0]
                            for line in (git / "packed-refs").read_text().splitlines()
                            if line.endswith(" " + ref)
                        ),
                        None,
                    )
            elif re.fullmatch(r"[0-9a-f]{40}", head):
                commit = head
        except (OSError, ValueError):
            pass
    return {
        "application_version": VERSION,
        "terminal_build": TERMINAL_BUILD,
        "source_commit": commit,
        "python_version": sys.version.split()[0],
        "executable": str(Path(sys.executable).resolve()),
        "command_on_path": shutil.which("doxa"),
        "working_directory": str(Path.cwd()),
        "workspace": str(workspace.resolve()),
        "frozen": bool(getattr(sys, "frozen", False)),
        "installed_launcher": str(installed) if installed.is_file() else None,
        "installed_build": build,
        "warning": (
            f"Installed command targets {build}; this runtime is {TERMINAL_BUILD}. "
            "Use the explicit development launcher for source changes."
        )
        if build and build != TERMINAL_BUILD
        else None,
    }
