"""Backend-only resolution and defense against accidental secret persistence."""

import os
import re
from pathlib import Path

from dotenv import dotenv_values


def local_env() -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(Path(".env")).items() if v is not None}
    return {**values, **os.environ}


def secret_values() -> tuple[str, ...]:
    return tuple(
        v
        for k, v in local_env().items()
        if (k.endswith("_KEY") or k.endswith("_TOKEN")) and len(v) >= 12 and v != "replace_me"
    )


def safe_text(text: str) -> str:
    for value in secret_values():
        text = text.replace(value, "[REDACTED]")
    return re.sub(r"moss_[A-Za-z0-9]{24,}", "[REDACTED]", text)


def reject_secrets(text: str) -> None:
    if safe_text(text) != text:
        raise ValueError("Secret-bearing data cannot be persisted or exported")
