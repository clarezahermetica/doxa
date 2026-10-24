"""Optional OpenAI-compatible HTTP adapter. Construction performs no network I/O."""

import asyncio
import time
from collections.abc import Mapping
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from doxa.core.models import Usage
from doxa.core.profiles import ModelProfile
from doxa.core.secrets import safe_text
from doxa.providers.contracts import (
    Capabilities,
    ModelRequest,
    ModelResponse,
    ProviderConfig,
    ProviderError,
)


def endpoint_url(profile: ModelProfile, env: Mapping[str, str]) -> str:
    endpoint = profile.endpoint_id or env.get("RUNPOD_ENDPOINT_ID", "")
    override = profile.base_url or env.get("RUNPOD_BASE_URL", "")
    url = override or f"https://api.runpod.ai/v2/{endpoint}/openai/v1"
    parsed = urlsplit(url)
    if profile.provider == "runpod":
        import re

        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.runpod.ai"
            or (
                parsed.port is not None
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or not re.fullmatch(r"/v2/[A-Za-z0-9_-]+/openai/v1", parsed.path)
            )
        ):
            raise ValueError("Invalid RunPod base URL; expected official vLLM endpoint")
    elif (
        parsed.scheme != "https"
        or not parsed.hostname
        or (parsed.username or parsed.password or parsed.query or parsed.fragment)
    ):
        raise ValueError("Compatible endpoints require an explicit HTTPS URL without credentials")
    return url.rstrip("/")


class RunPodProvider:
    def __init__(
        self,
        profile: ModelProfile,
        env: Mapping[str, str],
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.profile = profile
        self.env = env
        self.transport = transport
        self.tasks: dict[UUID, asyncio.Task[ModelResponse]] = {}

    def capabilities(self, config: ProviderConfig) -> Capabilities:
        return self.profile.capabilities

    async def generate(self, request: ModelRequest) -> ModelResponse:
        task = asyncio.create_task(self._generate(request))
        self.tasks[request.call_id] = task
        try:
            return await task
        finally:
            self.tasks.pop(request.call_id, None)

    async def cancel(self, call_id: UUID) -> bool:
        task = self.tasks.get(call_id)
        if task is None:
            return False
        task.cancel()
        return True  # Cancels local wait, not a guarantee of remote job/billing cancellation.

    async def _generate(self, request: ModelRequest) -> ModelResponse:
        start = time.monotonic()
        category = "transport"
        retryable = False
        try:
            if (
                not self.profile.enabled
                or self.env.get("DOXA_RUNPOD_ENABLED", "false").lower() != "true"
            ):
                raise ValueError("RunPod disabled")
            key = self.env.get(self.profile.credential_env)
            if not key or key == "replace_me":
                raise ValueError("Missing backend credential")
            if request.assignment.model_id != self.profile.model_id:
                raise ValueError("Request model differs from pinned profile")
            if request.max_output_tokens > self.profile.max_output_tokens:
                raise ValueError("Output token cap exceeded")
            # Conservative byte bound for byte-level tokenizers; no heuristic undercount.
            size = sum(len(m.content.encode("utf-8")) + 32 for m in request.messages)
            if size + request.max_output_tokens > self.profile.max_context_tokens:
                raise ValueError("Context cap exceeded")
            body: dict[str, object] = dict(
                model=self.profile.model_id,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                max_tokens=request.max_output_tokens,
                temperature=self.profile.temperature,
                stream=False,
            )
            async with httpx.AsyncClient(
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
                timeout=min(request.timeout_seconds, self.profile.timeout_seconds),
            ) as client:
                response = await client.post(
                    endpoint_url(self.profile, self.env) + "/chat/completions",
                    headers={"Authorization": "Bearer " + key},
                    json=body,
                )
            if response.status_code in {401, 403}:
                category = "authentication"
            elif response.status_code == 429:
                category = "quota"
            elif response.status_code >= 500:
                retryable = True
            response.raise_for_status()
            category = "invalid_response"
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
            if not isinstance(text, str):
                raise ValueError("Invalid completion content")
            usage = payload.get("usage") or {}
            return ModelResponse(
                call_id=request.call_id,
                assignment=request.assignment,
                text=safe_text(text),
                execution_kind="live",
                response_id=payload.get("id"),
                reported_model_id=payload.get("model"),
                usage=Usage(
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                    latency_seconds=time.monotonic() - start,
                ),
            )
        except httpx.TimeoutException:
            category = "timeout"
            retryable = True
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            pass
        return ModelResponse(
            call_id=request.call_id,
            assignment=request.assignment,
            execution_kind="live",
            error=ProviderError.model_validate(
                dict(
                    category=category,
                    retryable=retryable,
                    safe_message="Provider request failed ("
                    + category
                    + "); raw response suppressed",
                )
            ),
            usage=Usage(latency_seconds=time.monotonic() - start),
        )
