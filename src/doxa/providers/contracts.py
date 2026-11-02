from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from doxa.core.models import Contract, ModelAssignment, Usage


class ProviderConfig(Contract):
    provider: str
    model_id: str
    base_url: str | None = None
    credential_env: str | None = None  # Name only; credentials never enter contracts.
    remote_opt_in: bool = False


class Capabilities(Contract):
    text_generation: Literal["available", "unavailable", "unknown"] = "unknown"
    images: Literal["available", "unavailable", "unknown"] = "unknown"
    embeddings: Literal["available", "unavailable", "unknown"] = "unknown"
    sampling_parameters: tuple[str, ...] = ()
    structured_output: Literal["native", "prompted", "unavailable", "unknown"] = "unknown"
    tool_calling: Literal["native", "emulated", "unavailable", "unknown"] = "unknown"
    streaming: bool = False
    usage_reporting: bool = False
    seed_control: bool = False
    cancellation: bool = False
    context_limit: int | None = Field(default=None, gt=0)
    cost_metadata_version: str | None = None


class ModelMessage(Contract):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ModelRequest(Contract):
    experiment_id: UUID | None = None
    profile_id: str | None = None
    profile_version: int | None = None
    adapter: str | None = None
    turn_id: str | None = None
    context_id: UUID | None = None
    reservation_id: UUID | None = None
    call_id: UUID
    run_id: UUID
    trajectory_id: UUID
    agent_id: UUID
    assignment: ModelAssignment
    messages: tuple[ModelMessage, ...]
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)
    response_schema: dict[str, JsonValue] | None = None
    tools: tuple[dict[str, JsonValue], ...] = ()


class OutputBlock(Contract):
    type: str
    data: dict[str, JsonValue]


class ProviderError(Contract):
    category: Literal[
        "authentication",
        "quota",
        "timeout",
        "transport",
        "invalid_response",
        "configuration",
        "unsupported",
        "invalid_request",
    ]
    retryable: bool
    safe_message: str  # Sanitized category text, not a raw provider response or headers.
    billing_uncertain: bool = True


class ModelResponse(Contract):
    call_id: UUID
    assignment: ModelAssignment
    text: str | None = None
    error: ProviderError | None = None
    usage: Usage = Field(default_factory=Usage)
    execution_kind: Literal["live", "synthetic", "replay"]
    response_id: str | None = None
    reported_model_id: str | None = None
    provider_request_id: str | None = None
    blocks: tuple[OutputBlock, ...] = ()
    tool_requests: tuple[dict[str, JsonValue], ...] = ()
    finish_reason: str | None = None
    completion_state: Literal["completed", "incomplete", "tool_request", "refused"] = "completed"
    raw_response: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def result_or_error(self) -> Self:
        if (self.text is None) == (self.error is None):
            raise ValueError("A model response requires exactly one of text or error")
        return self


class ModelProvider(Protocol):
    def validate_request(self, request: ModelRequest) -> None: ...
    def capabilities(self, config: ProviderConfig) -> Capabilities: ...
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
    async def cancel(self, call_id: UUID) -> bool: ...


SUPPORTED_PROVIDER_BOUNDARIES = ("openai", "gemini", "openai_compatible", "claude")
# These are planned adapter slots, not supported live inference backends.
