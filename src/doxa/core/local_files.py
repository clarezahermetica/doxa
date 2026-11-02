"""Atomic operational files; never a second source of experimental history."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.stat().st_size > 65536:
        raise ValueError("Settings file exceeds the supported size; existing file preserved")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Settings must be an object; existing file preserved")
    return value


def atomic_write(path: Path, data: bytes, *, replace: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + "-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # Publish the complete encrypted file exclusively; never replace a credential.
            os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
