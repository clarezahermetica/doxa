"""Provider composition and offline readiness. No health probe or credential is returned."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from doxa.core.models import Contract
from doxa.core.profiles import CouncilConfig, ModelProfile
from doxa.providers.contracts import Capabilities, ModelProvider, ModelRequest
from doxa.providers.runpod import RunPodProvider, endpoint_url


@dataclass(frozen=True)
class AdapterRegistration:
    factory: Callable[[ModelProfile, Mapping[str, str]], ModelProvider]
    validate: Callable[[ModelProfile, Mapping[str, str]], None]
    capabilities: Capabilities
    enabled_env: str
    allowance_env: str


ADAPTERS: dict[str, AdapterRegistration] = {}


def register_adapter(name: str, registration: AdapterRegistration) -> None:
    """Trusted Python extension entry point; never load code named by ledger data."""
    from doxa.providers.cli_session import CLI_NAMES

    if name in CLI_NAMES:
        raise ValueError("Account CLI identities are reserved for reviewed executable adapters")
    if name in {"runpod", "openai", "claude", "gemini", "openai_compatible"} or name in ADAPTERS:
        raise ValueError("Adapter identity is already registered")
    ADAPTERS[name] = registration


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
    credential_env: str | None
    credential_present: bool
    # Presence is not verification that a key/endpoint works or credits remain.
    remote_verified: Literal[False] = False
    credit_balance_usd: None = None


class ConfigurationReport(Contract):
    valid: bool
    issues: tuple[str, ...]
    profiles: tuple[ProfileReadiness, ...]


def provider_environment(provider: str) -> tuple[str, str]:
    if provider in ADAPTERS:
        return ADAPTERS[provider].enabled_env, ADAPTERS[provider].allowance_env
    if provider == "runpod":
        return "DOXA_RUNPOD_ENABLED", "DOXA_RUNPOD_ALLOWANCE_USD"
    if provider == "openai_compatible":
        return "DOXA_OPENAI_COMPATIBLE_ENABLED", "DOXA_OPENAI_COMPATIBLE_ALLOWANCE_USD"
    if provider in {"openai", "claude", "gemini"}:
        return f"DOXA_{provider.upper()}_ENABLED", f"DOXA_{provider.upper()}_ALLOWANCE_USD"
    raise ValueError("No implemented adapter for provider type")


def validate_profile(profile: ModelProfile, env: Mapping[str, str]) -> None:
    from doxa.providers.cli_session import CLI_NAMES, validate_cli_profile

    if profile.transport == "cli_session" or profile.runtime in CLI_NAMES:
        validate_cli_profile(profile)
        return
    if profile.local:
        from urllib.parse import urlsplit

        parsed = urlsplit(profile.base_url or "")
        if parsed.hostname not in {"127.0.0.1", "::1", "localhost"} or parsed.scheme not in {
            "http",
            "https",
        }:
            raise ValueError("Unbilled local dispatch requires an explicit loopback origin")
    if profile.runtime in ADAPTERS:
        ADAPTERS[profile.runtime].validate(profile, env)
        return
    endpoint_url(profile, env)
    if (
        profile.model_id.strip() in {"", "replace_me"}
        or profile.model_id != profile.model_id.strip()
    ):
        raise ValueError("Set an exact served model identifier")
    if profile.runtime == "openai" and profile.temperature != 0:
        raise ValueError("Native OpenAI adapter omits temperature; use the default profile value")
    from doxa.providers.wire import validate_parameters

    validate_parameters(profile)
    caps = profile.capabilities
    if caps.images == "available" or caps.embeddings == "available":
        raise ValueError(
            "This adapter only implements text; image and embedding requests are unavailable"
        )
    if caps.text_generation == "unavailable":
        raise ValueError("Model is configured without text-generation support")
    if caps.structured_output == "native" and not (
        profile.request_protocol == "responses" or profile.runtime == "gemini"
    ):
        raise ValueError("Native structured output is not implemented by this adapter")
    if (
        caps.tool_calling == "emulated"
        or (caps.tool_calling == "native" and profile.runtime == "runpod")
        or caps.streaming
        or caps.seed_control
    ):
        raise ValueError("Tool calling, streaming and seed controls are not implemented")
    if caps.context_limit and profile.max_context_tokens > caps.context_limit:
        raise ValueError("Configured context limit exceeds declared model context")
    if profile.max_output_tokens >= profile.max_context_tokens:
        raise ValueError("Output limit must leave space for input context")


def spending_allowance(profile: ModelProfile, env: Mapping[str, str]) -> Decimal:
    _, allowance_env = provider_environment(profile.runtime)
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
    if profile.transport == "cli_session":
        from doxa.providers.cli_session import CLI_RETRY_WARNING, cli_status

        check = cli_status(profile.runtime)
        issues = []
        try:
            validate_profile(profile, env)
        except ValueError as exc:
            issues.append(str(exc))
        if not check.ready:
            issues.append(check.detail)
        if profile.capabilities.structured_output == "native" and not check.schema_available:
            issues.append("This installed CLI has not verified native response-schema support")
        return ProfileReadiness(
            profile_id=profile.id,
            version=profile.version,
            provider=profile.provider,
            model_id=profile.model_id,
            credential_env=None,
            credential_present=check.authentication == "authenticated",
            issues=tuple(issues),
            warnings=(
                "Subscription quota consumption unknown; USD billing unavailable, not zero",
                CLI_RETRY_WARNING,
            ),
            status="disabled"
            if not profile.enabled
            else "not_ready"
            if issues
            else "ready_for_authorized_test",
        )
    switch, _ = provider_environment(profile.runtime)
    enabled = profile.enabled and (profile.local or env.get(switch, "false").lower() == "true")
    present = profile.authentication == "none" or bool(
        env.get(profile.credential_env or "") not in {None, "", "replace_me"}
    )
    issues = []
    try:
        validate_profile(profile, env)
    except ValueError as exc:
        # These messages are constants in validators, never raw URL/credential inputs.
        issues.append(str(exc))
    if not present:
        issues.append("Credential is missing; set the referenced backend environment variable")
    try:
        if not profile.local:
            spending_allowance(profile, env)
    except ValueError as exc:
        issues.append(str(exc))
    warnings = [
        "Local endpoint, hardware and served weights are unverified"
        if profile.local
        else "Offline inspection only; remote availability and credit balance are unverified"
    ]
    if profile.pricing is None and not profile.local:
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
        from doxa.providers.cli_session import CLI_CAPABILITIES, CLI_NAMES

        implemented = Capabilities(
            structured_output="prompted",
            tool_calling="unavailable",
            usage_reporting=True,
            cancellation=True,
        )
        return (
            tuple(
                ProviderDescriptor(
                    provider=name,
                    implemented=name
                    in {"runpod", "openai_compatible", "openai", "claude", "gemini"},
                    capabilities=implemented
                    if name in {"runpod", "openai_compatible", "openai", "claude", "gemini"}
                    else Capabilities(),
                )
                for name in ("runpod", "openai_compatible", "openai", "gemini", "claude")
            )
            + tuple(
                ProviderDescriptor(
                    provider=name,
                    implemented=name == "codex_cli",
                    capabilities=CLI_CAPABILITIES if name == "codex_cli" else Capabilities(),
                )
                for name in CLI_NAMES
            )
            + tuple(
                ProviderDescriptor(provider=name, implemented=True, capabilities=entry.capabilities)
                for name, entry in sorted(ADAPTERS.items())
            )
        )

    def create(
        self,
        profile: ModelProfile,
        env: Mapping[str, str],
        factory: Callable[[ModelProfile, Mapping[str, str]], ModelProvider] | None = None,
    ) -> ModelProvider:
        validate_profile(profile, env)
        if profile.transport == "cli_session":
            from doxa.providers.cli_session import CLI_ADAPTERS

            return CLI_ADAPTERS[profile.runtime](profile, env)
        provider_environment(profile.runtime)
        if profile.runtime in ADAPTERS:
            return ADAPTERS[profile.runtime].factory(profile, env)
        # The same tested HTTP wire adapter handles explicitly configured compatible URLs.
        return (factory or RunPodProvider)(profile, env)
