"""Shared source/frozen identity. No package metadata lookup or network request."""

import re

VERSION = "0.1.0a1"
# Installer directory identity; never use this as the public product version.
TERMINAL_BUILD = "v30"


def readable_version() -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)a(\d+)", VERSION)
    return f"DOXA {match[1]} Alpha {int(match[2])}" if match else f"DOXA {VERSION}"


DISPLAY_VERSION = readable_version()
ARCHIVE_NAME = f"DOXA-{VERSION}-Windows.zip"
WINDOWS_VERSION = tuple(int(n) for n in re.findall(r"\d+", VERSION))


def version_string() -> str:
    return DISPLAY_VERSION
