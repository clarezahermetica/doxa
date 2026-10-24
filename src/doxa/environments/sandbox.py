import shutil
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
    max_processes: int = Field(default=32, ge=1, le=256)


class SandboxStatus(Contract):
    execution_enabled: bool = False
    runtime_detected: bool
    prerequisite: str


def sandbox_status() -> SandboxStatus:
    detected = bool(shutil.which("docker") or shutil.which("podman"))
    return SandboxStatus(
        runtime_detected=detected,
        prerequisite=(
            "An enforced and acceptance-tested container runner is not implemented"
            if detected
            else "Install/start Docker Desktop with Linux containers (WSL2), "
            "or an equivalent restricted runtime, then validate the container runner"
        ),
    )


class Sandbox(Protocol):
    async def execute(self, source: ArtifactRef, limits: SandboxLimits) -> ArtifactRef: ...


class DisabledSandbox:
    async def execute(self, source: ArtifactRef, limits: SandboxLimits) -> ArtifactRef:
        raise CapabilityUnavailable(
            "No isolated execution backend is installed; execution disabled"
        )
