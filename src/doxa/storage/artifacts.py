import hashlib
import os
import tempfile
from pathlib import Path

from doxa.core.models import ArtifactRef


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def put(self, content: bytes, media_type: str = "application/octet-stream") -> ArtifactRef:
        digest = hashlib.sha256(content).hexdigest()
        ref = ArtifactRef(
            sha256=digest,
            relative_path=f"sha256/{digest[:2]}/{digest}",
            size_bytes=len(content),
            media_type=media_type,
        )
        target = self.root / ref.relative_path
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Artifact target escapes storage root")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            descriptor, temporary = tempfile.mkstemp(dir=target.parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        self.get(ref)
        return ref

    def get(self, ref: ArtifactRef) -> bytes:
        expected = f"sha256/{ref.sha256[:2]}/{ref.sha256}"
        target = (self.root / ref.relative_path).resolve()
        if ref.relative_path != expected or not target.is_relative_to(self.root):
            raise ValueError("Artifact path does not match content address")
        content = target.read_bytes()
        if len(content) != ref.size_bytes or hashlib.sha256(content).hexdigest() != ref.sha256:
            raise ValueError("Artifact integrity check failed")
        return content
