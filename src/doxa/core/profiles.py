from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from doxa.core.models import Agent, Contract
from doxa.providers.contracts import Capabilities


class ModelProfile(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    version: int = Field(default=1, gt=0)
    provider: Literal["runpod", "openai_compatible"]
    model_id: str = Field(min_length=1)
    endpoint_id: str | None = None
    base_url: str | None = None
    credential_env: str = Field(default="RUNPOD_API_KEY", pattern=r"^[A-Z][A-Z0-9_]*$")
    enabled: bool = False
    capabilities: Capabilities = Field(default_factory=Capabilities)
    temperature: float = Field(default=0, ge=0, le=2)
    max_output_tokens: int = Field(default=256, ge=1, le=16384)
    max_context_tokens: int = Field(default=4096, ge=1, le=131072)
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    retries: int = Field(default=0, ge=0, le=3)
    concurrency: int = Field(default=1, ge=1, le=8)


class AgentDefinition(Contract):
    id: UUID
    version: int = Field(default=1, gt=0)
    display_name: str = Field(min_length=1)
    agent: Agent
    model_profile_id: str | None = None
    model_profile_version: int | None = None
    enabled: bool = True
    instruction_version: str = "1"

    @model_validator(mode="after")
    def identity(self) -> Self:
        if self.id != self.agent.id:
            raise ValueError("Definition ID must match stable agent ID")
        if (self.model_profile_id is None) != (self.model_profile_version is None):
            raise ValueError("Profile ID and version must be pinned together")
        return self


class CouncilConfig(Contract):
    profiles: tuple[ModelProfile, ...] = ()
    agents: tuple[AgentDefinition, ...] = ()
