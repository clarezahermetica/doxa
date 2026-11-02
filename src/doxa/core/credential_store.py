"""Windows current-user DPAPI store. No credential value enters a contract."""

import ctypes
import os
import re
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _protect(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise ValueError(
            "OS-backed credential entry currently requires Windows; use an environment reference"
        )
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    function = (
        ctypes.windll.crypt32.CryptUnprotectData
        if decrypt
        else ctypes.windll.crypt32.CryptProtectData
    )
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError("Windows could not protect or read this credential")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def save_credential(directory: Path, reference: str, value: str) -> None:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", reference) or not value:
        raise ValueError("A credential reference and value are required")
    encrypted = _protect(value.encode())
    target = directory / "credentials"
    target.mkdir(exist_ok=True)
    from doxa.core.local_files import atomic_write

    # Do not publish a partial ciphertext or replace a credential. Rotation is separate.
    atomic_write(target / (reference + ".dpapi"), encrypted, replace=False)


def load_credentials(directory: Path) -> dict[str, str]:
    result = {}
    for path in (directory / "credentials").glob("*.dpapi"):
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", path.stem):
            result[path.stem] = _protect(path.read_bytes(), decrypt=True).decode()
    return result
