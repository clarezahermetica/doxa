from typing import Protocol

from pydantic import Field

from doxa.core.controller import CapabilityUnavailable
from doxa.core.models import ArtifactRef, Contract


class SandboxLimits(Contract):
    network: bool = False
    cpu_cores: float = Field(default=1, gt=0)
    memory_mb: int = Field(default=256, gt=0)
    timeout_seconds: int = Field(default=30, gt=0)
    writable_mb: int = Field(default=64, gt=0)
    read_only_root: bool = True


class Sandbox(Protocol):
    async def execute(self, source: ArtifactRef, limits: SandboxLimits) -> ArtifactRef: ...


class DisabledSandbox:
    async def execute(self, source: ArtifactRef, limits: SandboxLimits) -> ArtifactRef:
        raise CapabilityUnavailable(
            "No isolated execution backend is installed; execution disabled"
        )
