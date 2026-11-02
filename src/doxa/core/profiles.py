from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from doxa.core.model_artifacts import ModelArtifact
from doxa.core.models import Agent, Contract
from doxa.providers.contracts import Capabilities


class PricingMetadata(Contract):
    version: str = Field(min_length=1)
    source: str = Field(min_length=1, max_length=500)
    kind: Literal["token", "complete_operation"]
    input_usd_per_million: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_usd_per_million: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    complete_operation_upper_bound_usd: Decimal | None = Field(default=None, gt=0, le=75)

    @model_validator(mode="after")
    def rates(self) -> Self:
        if self.kind == "token" and (
            self.input_usd_per_million is None or self.output_usd_per_million is None
        ):
            raise ValueError("Token pricing requires both rates")
        if self.kind == "complete_operation" and self.complete_operation_upper_bound_usd is None:
            raise ValueError("Complete operation pricing requires a documented upper bound")
        return self


class ModelProfile(Contract):
    request_protocol: Literal["default", "responses"] = "default"
    # Explicit, capability-declared wire parameters, never arbitrary HTTP fields.
    generation_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    reasoning: dict[str, JsonValue] = Field(default_factory=dict)
    omit_temperature: bool = False
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    version: int = Field(default=1, gt=0)
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    adapter: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_-]*$")
    local: bool = False
    authentication: Literal["bearer", "none"] = "bearer"
    model_id: str = Field(min_length=1)
    repository_id: str | None = None
    artifact: ModelArtifact | None = None
    endpoint_id: str | None = None
    base_url: str | None = None
    credential_env: str = Field(default="RUNPOD_API_KEY", pattern=r"^[A-Z][A-Z0-9_]*$")
    enabled: bool = False
    capabilities: Capabilities = Field(default_factory=Capabilities)
    temperature: float = Field(default=0, ge=0, le=2)
    max_output_tokens: int = Field(default=256, ge=1, le=16384)
    max_context_tokens: int = Field(default=4096, ge=1, le=131072)
    max_input_bytes: int = Field(default=4096, ge=1, le=524288)
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    retries: int = Field(default=0, ge=0, le=3)
    concurrency: int = Field(default=1, ge=1, le=8)
    pricing: PricingMetadata | None = None

    @property
    def runtime(self) -> str:
        return self.adapter or self.provider


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
