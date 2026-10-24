"""No-spend installation diagnostics composed from local configuration only."""

from doxa.core.controller import Controller
from doxa.core.models import Contract
from doxa.environments.sandbox import SandboxStatus, sandbox_status
from doxa.providers.registry import ConfigurationReport, ProviderDescriptor


class InstallationReadiness(Contract):
    mode: str = "local_only"
    configuration: ConfigurationReport
    providers: tuple[ProviderDescriptor, ...]
    sandbox: SandboxStatus
    external_probe_performed: bool = False


def inspect_readiness(controller: Controller) -> InstallationReadiness:
    return InstallationReadiness(
        configuration=controller.validate_configuration(),
        providers=controller.provider_catalog(),
        sandbox=sandbox_status(),
    )
