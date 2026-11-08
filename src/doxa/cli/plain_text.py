"""Presentation escaping for plain terminal output; canonical research stays unchanged."""


def terminal_text(value: str) -> str:
    return "".join(
        f"\\x{ord(char):02x}"
        if (ord(char) < 32 and char not in "\n\t") or 127 <= ord(char) <= 159
        else char
        for char in value
    )
