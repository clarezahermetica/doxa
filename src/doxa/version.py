"""Shared source/frozen identity. No package metadata lookup or network request."""

VERSION = "0.1.0a0"
TERMINAL_BUILD = "v20"


def version_string() -> str:
    return f"DOXA {VERSION} (terminal {TERMINAL_BUILD})"
