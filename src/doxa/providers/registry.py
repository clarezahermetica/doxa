"""Provider composition and offline readiness. No health probe or credential is returned."""

from collections.abc import Callable, Mapping
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from doxa.core.models import Contract
from doxa.core.profiles import CouncilConfig, ModelProfile
from doxa.providers.contracts import Capabilities, ModelProvider, ModelRequest
from doxa.providers.runpod import RunPodProvider, endpoint_url


class ProviderDescriptor(Contract):
    provider: str
    implemented: bool
    capabilities: Capabilities


class ProfileReadiness(Contract):
    profile_id: str
    version: int
    provider: str
    model_id: str
    status: Literal["disabled", "not_ready", "ready_for_authorized_test"]
    issues: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    credential_env: str
    credential_present: bool
    # Presence is not verification that a key/endpoint works or credits remain.
    remote_verified: Literal[False] = False
    credit_balance_usd: None = None


class ConfigurationReport(Contract):
    valid: bool
    issues: tuple[str, ...]
    profiles: tuple[ProfileReadiness, ...]


def provider_environment(provider: str) -> tuple[str, str]:
    if provider == "runpod":
        return "DOXA_RUNPOD_ENABLED", "DOXA_RUNPOD_ALLOWANCE_USD"
    if provider == "openai_compatible":
        return "DOXA_OPENAI_COMPATIBLE_ENABLED", "DOXA_OPENAI_COMPATIBLE_ALLOWANCE_USD"
    raise ValueError("No implemented adapter for provider type")


def validate_profile(profile: ModelProfile, env: Mapping[str, str]) -> None:
    endpoint_url(profile, env)
    if (
        profile.model_id.strip() in {"", "replace_me"}
        or profile.model_id != profile.model_id.strip()
    ):
        raise ValueError("Set an exact served model identifier")
    caps = profile.capabilities
    if caps.structured_output == "native":
        raise ValueError("Native structured output is not implemented by this adapter")
    if caps.tool_calling in {"native", "emulated"} or caps.streaming or caps.seed_control:
        raise ValueError("Tool calling, streaming and seed controls are not implemented")
    if caps.context_limit and profile.max_context_tokens > caps.context_limit:
        raise ValueError("Configured context limit exceeds declared model context")
    if profile.max_output_tokens >= profile.max_context_tokens:
        raise ValueError("Output limit must leave space for input context")


def spending_allowance(profile: ModelProfile, env: Mapping[str, str]) -> Decimal:
    _, allowance_env = provider_environment(profile.provider)
    try:
        amount = Decimal(env.get(allowance_env, "0"))
        limit = Decimal(25 if profile.provider == "runpod" else 75)
        if not amount.is_finite() or amount <= 0 or amount > limit:
            raise ValueError
        if amount * 1_000_000 != int(amount * 1_000_000):
            raise ValueError
    except (ValueError, ArithmeticError):
        raise ValueError(
            "Set a positive allowance within the provider and aggregate caps"
        ) from None
    return amount


def readiness(profile: ModelProfile, env: Mapping[str, str]) -> ProfileReadiness:
    switch, _ = provider_environment(profile.provider)
    enabled = profile.enabled and env.get(switch, "false").lower() == "true"
    present = bool(env.get(profile.credential_env) not in {None, "", "replace_me"})
    issues = []
    try:
        validate_profile(profile, env)
    except ValueError as exc:
        # These messages are constants in validators, never raw URL/credential inputs.
        issues.append(str(exc))
    if not present:
        issues.append("Credential is missing; set the referenced backend environment variable")
    try:
        spending_allowance(profile, env)
    except ValueError as exc:
        issues.append(str(exc))
    warnings = ["Offline inspection only; remote availability and credit balance are unverified"]
    if profile.pricing is None:
        warnings.append("Pricing is unknown; each paid command needs a complete cost upper bound")
    return ProfileReadiness(
        profile_id=profile.id,
        version=profile.version,
        provider=profile.provider,
        model_id=profile.model_id,
        credential_env=profile.credential_env,
        credential_present=present,
        issues=tuple(issues),
        warnings=tuple(warnings),
        status="disabled"
        if not enabled
        else "not_ready"
        if issues
        else "ready_for_authorized_test",
    )


def validate_configuration(config: CouncilConfig, env: Mapping[str, str]) -> ConfigurationReport:
    profiles = {(p.id, p.version): p for p in config.profiles}
    issues = []
    for profile in config.profiles:
        try:
            validate_profile(profile, env)
        except ValueError as exc:
            issues.append(f"Profile {profile.id}: {exc}")
    for agent in config.agents:
        if (
            agent.model_profile_id
            and (agent.model_profile_id, agent.model_profile_version) not in profiles
        ):
            issues.append(
                f"Agent {agent.id}: pinned profile version is missing from validation input"
            )
    return ConfigurationReport(
        valid=not issues,
        issues=tuple(issues),
        profiles=tuple(readiness(p, env) for p in config.profiles),
    )


def reservation_upper_bound(
    profile: ModelProfile,
    request: ModelRequest,
    explicit: Decimal | None,
) -> Decimal:
    pricing = profile.pricing
    configured: Decimal | None = None
    if pricing:
        configured = pricing.complete_operation_upper_bound_usd
        if pricing.kind == "token" and profile.provider != "runpod":
            assert pricing.input_usd_per_million is not None
            assert pricing.output_usd_per_million is not None
            count = profile.max_context_tokens
            configured = (
                Decimal(count) * pricing.input_usd_per_million
                + request.max_output_tokens * pricing.output_usd_per_million
            ) / 1_000_000
    values = [value for value in (configured, explicit) if value is not None]
    if not values:
        raise ValueError("A complete per-attempt compute cost upper bound is required")
    upper = max(values).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
    if not upper.is_finite() or upper <= 0:
        raise ValueError("A positive complete operation upper bound is required")
    return upper


class ProviderRegistry:
    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        implemented = Capabilities(
            structured_output="prompted",
            tool_calling="unavailable",
            usage_reporting=True,
            cancellation=True,
        )
        return tuple(
            ProviderDescriptor(
                provider=name,
                implemented=name in {"runpod", "openai_compatible"},
                capabilities=implemented
                if name in {"runpod", "openai_compatible"}
                else Capabilities(),
            )
            for name in ("runpod", "openai_compatible", "openai", "gemini", "claude")
        )

    def create(
        self,
        profile: ModelProfile,
        env: Mapping[str, str],
        factory: Callable[[ModelProfile, Mapping[str, str]], ModelProvider] | None = None,
    ) -> ModelProvider:
        validate_profile(profile, env)
        provider_environment(profile.provider)
        # The same tested HTTP wire adapter handles explicitly configured compatible URLs.
        return (factory or RunPodProvider)(profile, env)
