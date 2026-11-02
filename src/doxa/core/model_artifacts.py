import hashlib
from pathlib import Path

from doxa.core.models import Contract


class ModelArtifact(Contract):
    path: str
    sha256: str
    bytes: int
    format: str = "gguf"
    execution_verified: bool = False


def inspect_model_artifact(path: Path) -> ModelArtifact:
    path = path.expanduser().resolve(strict=True)
    if path.suffix.lower() != ".gguf" or not path.is_file():
        raise ValueError("Only GGUF metadata registration is supported; no model code is loaded")
    with path.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("Not a GGUF file")
        version = int.from_bytes(stream.read(4), "little")
        if version not in {1, 2, 3}:
            raise ValueError("Unknown GGUF version")
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return ModelArtifact(path=str(path), sha256=digest, bytes=path.stat().st_size)
