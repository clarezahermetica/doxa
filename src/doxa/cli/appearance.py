"""Per-user appearance is committed on change, independent of viewer shutdown."""

import json
from pathlib import Path
from typing import Any

from doxa.core.local_files import atomic_write, read_json_object
from doxa.core.workspaces import preferences_path


def appearance_path() -> Path:
    return preferences_path().parent / "appearance.json"


def read_appearance() -> dict[str, Any]:
    value = read_json_object(appearance_path())
    if value and (
        value.get("version") != 1
        or not isinstance(value.get("theme"), str)
        or not 1 <= len(value["theme"]) <= 128
    ):
        raise ValueError("Appearance settings need review; existing file preserved")
    return value


def save_theme(theme: str) -> None:
    values = read_appearance()
    values.update(version=1, theme=theme)
    atomic_write(appearance_path(), json.dumps(values, sort_keys=True).encode())
