"""Workspace credentials backed by DPAPI or explicitly selected OS vaults."""

import ctypes
import re
import sys
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

from doxa.core.local_files import atomic_write

MANAGED_PREFIX = "DOXA_MANAGED_"
REFERENCE = re.compile(r"[A-Z][A-Z0-9_]{0,239}")
MAX_SECRET_BYTES = 8192
MAX_DPAPI_BYTES = 64 * 1024


class Vault(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


def _keyring_backend() -> Vault:
    # Instantiate the concrete built-in class, never keyring.get_keyring(), chainer,
    # environment overrides, entry-point discovery or third-party fallback.
    module = {"darwin": "macOS", "linux": "SecretService"}.get(sys.platform)
    if module is None:
        raise ValueError("No supported OS credential vault on this platform")
    try:
        backend_module = import_module("keyring.backends." + module)
        backend = backend_module.Keyring
        if not isinstance(backend, type) or backend.__module__ != "keyring.backends." + module:
            raise ValueError("Unexpected keyring backend")
        if backend_module.Keyring.priority <= 0:
            raise ValueError("Unavailable keyring backend")
        instance = backend()
        if module == "macOS":
            instance.keychain = None
        else:
            instance.__dict__.pop("preferred_collection", None)
        return cast(Vault, instance)
    except Exception:
        raise ValueError(
            "Secure storage unavailable; install DOXA with the os-credentials extra "
            "and unlock Keychain or Secret Service. No plaintext fallback is used."
        ) from None


class Blob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _protect(data: bytes, decrypt: bool = False) -> bytes:
    if sys.platform != "win32":
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


def _target(directory: Path, reference: str, suffix: str) -> Path:
    if not REFERENCE.fullmatch(reference):
        raise ValueError("Invalid credential reference")
    root = directory / "credentials"
    target = root / (reference + suffix)
    if root.is_symlink() or root.is_junction() or target.is_symlink() or target.is_junction():
        raise ValueError("Linked credential storage is not supported")
    return target


def _service(directory: Path) -> str:
    return "DOXA workspace " + sha256(str(directory.resolve()).encode()).hexdigest()


def _write_secret(directory: Path, reference: str, value: str, *, replace: bool) -> None:
    if (
        not value
        or value == "replace_me"
        or len(value.encode()) > MAX_SECRET_BYTES
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(
            "Enter a nonempty credential of at most 8192 bytes without control characters"
        )
    dpapi = _target(directory, reference, ".dpapi")
    marker = _target(directory, reference, ".keyring")
    if sys.platform == "win32" or dpapi.exists() or not reference.startswith(MANAGED_PREFIX):
        if replace and not dpapi.is_file():
            raise ValueError("No stored credential to replace")
        atomic_write(dpapi, _protect(value.encode()), replace=replace)
        return
    try:
        vault = _keyring_backend()
        service = _service(directory)
        if replace:
            if not marker.is_file() or vault.get_password(service, reference) is None:
                raise ValueError("No stored credential to replace")
        else:
            # Only an opaque reference marker is written to disk. Preserve it if the
            # external vault reports an uncertain write, so the entry can be checked.
            atomic_write(marker, b"", replace=False)
        vault.set_password(service, reference, value)
    except Exception:
        raise ValueError(
            "Secure credential could not be saved; check that the vault is available "
            "and unlocked, and that this operation matches the reference's state."
        ) from None


def save_credential(directory: Path, reference: str, value: str) -> None:
    """Create without overwriting; retained for existing DPAPI callers."""
    _write_secret(directory, reference, value, replace=False)


def create_credential(directory: Path, value: str) -> str:
    reference = MANAGED_PREFIX + uuid4().hex.upper()
    save_credential(directory, reference, value)
    return reference


def replace_credential(directory: Path, reference: str, value: str) -> None:
    _write_secret(directory, reference, value, replace=True)


def delete_credential(directory: Path, reference: str) -> None:
    """Delete only the local copy, never the issuing provider's key."""
    dpapi = _target(directory, reference, ".dpapi")
    marker = _target(directory, reference, ".keyring")
    try:
        if dpapi.is_file():
            dpapi.unlink()
        elif marker.is_file() and reference.startswith(MANAGED_PREFIX):
            _keyring_backend().delete_password(_service(directory), reference)
            marker.unlink()
        else:
            raise ValueError("No stored credential")
    except Exception:
        raise ValueError(
            "Local credential could not be removed; check the vault and reference"
        ) from None


def load_credentials(directory: Path) -> dict[str, str]:
    """Unreadable credentials are absent; callers must not fall back for managed aliases."""
    result: dict[str, str] = {}
    for path in (directory / "credentials").glob("*.dpapi"):
        try:
            target = _target(directory, path.stem, ".dpapi")
            with target.open("rb") as stream:
                body = stream.read(MAX_DPAPI_BYTES + 1)
            if len(body) <= MAX_DPAPI_BYTES:
                result[path.stem] = _protect(body, decrypt=True).decode()
        except (OSError, ValueError):
            continue
    if sys.platform in {"linux", "darwin"}:
        markers = list((directory / "credentials").glob(MANAGED_PREFIX + "*.keyring"))
        if markers:
            try:
                vault = _keyring_backend()
            except ValueError:
                return result
            service = _service(directory)
            for marker in markers:
                try:
                    _target(directory, marker.stem, ".keyring")
                    value = vault.get_password(service, marker.stem)
                    if value:
                        result[marker.stem] = value
                except Exception:
                    continue
    return result
