"""Read-only launch planning. Never contact an endpoint, reserve money or create records."""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field, JsonValue

from doxa.core.models import Contract, Experiment
from doxa.core.profiles import ModelProfile
from doxa.core.secrets import workspace_env
from doxa.providers.registry import provider_environment, readiness, spending_allowance
from doxa.providers.runpod import endpoint_url
from doxa.storage.configurations import ConfigurationStore

if TYPE_CHECKING:
    from doxa.core.controller import Controller


class Preflight(Contract):
    experiment_id: UUID
    run_id: UUID
    execution_kind: str
    eligible: bool
    blockers: tuple[str, ...]
    participants: tuple[dict[str, JsonValue], ...]
    limits: dict[str, JsonValue]
    planned_rounds: int
    planned_requests_upper_bound: int
    permitted_tools: tuple[str, ...]
    authorization_required: tuple[str, ...]
    endpoint_reachable: None = None
    inference_verified: bool = False
    caveat: str = "Offline configuration inspection; eligibility does not verify inference."


class LaunchAuthorization(Contract):
    report: Preflight
    authorize_paid: bool
    authorize_external: bool
    authorize_quota: bool = False
    upper_bound_usd_per_attempt: Decimal | None = Field(default=None, gt=0, le=25)
    profile_allowances_usd: dict[str, str]
    uncertain_outcome_policy: str = "retain_reservation_no_replay"


def preflight(controller: "Controller", run_id: UUID) -> Preflight:
    bundle = controller.inspect(run_id)
    experiment = controller.ledger.get(bundle.run.experiment_id)
    assert isinstance(experiment, Experiment)
    task = experiment.task
    blockers: list[str] = []
    if bundle.run.execution_kind == "replay":
        blockers.append("Replay records are inspection-only; live inference is unavailable")
    if not task or task.task_type != "research_debate":
        blockers.append("This launch path requires a research-debate task")
    if bundle.run.status != "configured":
        blockers.append("Only a configured attempt can launch; create another attempt to continue")
    if not experiment.agents:
        blockers.append("Assign at least one participant")
    env = workspace_env(controller.settings.data_dir)
    participants: list[dict[str, JsonValue]] = []
    remote = False
    quota = False
    requests = 0
    rounds = 1 if bundle.run.mode.value == "solo_direct" else task.council.rounds if task else 0
    for actor in experiment.agents:
        row: dict[str, JsonValue] = dict(
            agent_id=str(actor.id),
            name=actor.display_name,
            role=actor.role.value,
            profile_id=actor.model_profile_id,
            profile_version=actor.model_profile_version,
            tools=list(actor.permissions.allowed_tools),
        )
        attempts = 1
        if bundle.run.execution_kind == "live":
            try:
                if not actor.model_profile_id or not actor.model:
                    raise ValueError("Pinned profile and model assignment are required")
                profile = ConfigurationStore(controller.settings.database_path).get(
                    "profile", actor.model_profile_id, actor.model_profile_version
                )
                assert isinstance(profile, ModelProfile)
                ready = readiness(profile, env)
                row.update(
                    model_id=profile.model_id,
                    adapter=profile.runtime,
                    credential_present=ready.credential_present,
                    status=ready.status,
                    issues=list(ready.issues),
                    endpoint=None
                    if profile.transport == "cli_session"
                    else endpoint_url(profile, env),
                    transport=profile.transport,
                    accounting_basis="subscription_quota"
                    if profile.transport == "cli_session"
                    else "local_unbilled"
                    if profile.local
                    else "api_usd",
                )
                if profile.transport == "cli_session":
                    row["reasoning_effort"] = profile.reasoning.get("effort")
                    row["reasoning_source"] = (
                        "explicit_profile" if profile.reasoning else "CLI_default_unverified"
                    )
                if ready.status != "ready_for_authorized_test":
                    blockers.append(
                        actor.display_name + ": " + ("; ".join(ready.issues) or "disabled")
                    )
                if not actor.permissions.remote_inference:
                    blockers.append(actor.display_name + ": inference permission is disabled")
                if (
                    actor.model.model_id != profile.model_id
                    or actor.model.provider != profile.provider
                ):
                    blockers.append(actor.display_name + ": assignment differs from pinned profile")
                if (
                    task
                    and task.structured_actions
                    and profile.capabilities.structured_output not in {"native", "prompted"}
                ):
                    blockers.append(
                        actor.display_name + ": declare prompted structured-action support"
                    )
                attempts += min(profile.retries, experiment.budget.max_retries)
                quota |= profile.transport == "cli_session"
                remote |= not profile.local and profile.transport != "cli_session"
            except (ValueError, KeyError):
                blockers.append(actor.display_name + ": profile or endpoint is invalid/unavailable")
                row["status"] = "unavailable"
        requests += rounds * attempts * (1 + task.max_tool_rounds if task else 1)
        participants.append(row)
    if task and task.research_protocol == "investigation":
        requests = min(task.council.max_calls, experiment.budget.max_model_calls)
    cap = min(experiment.budget.max_model_calls, task.council.max_calls) if task else 0
    if requests > cap:
        blockers.append("Planned turns including retries and tools exceed the model-call ceiling")
    required = (
        ("authorize_external", "authorize_paid", "complete_per_attempt_cost_bound")
        if remote
        else ()
    )
    if quota:
        required = tuple(dict.fromkeys((*required, "authorize_external", "authorize_quota")))
    limits = experiment.budget.model_dump(mode="json")
    if task:
        limits["council"] = task.council.model_dump(mode="json")
        limits["network_mode"] = task.network_mode
        limits["max_fetches"] = task.max_fetches
        limits["max_searches"] = task.max_searches
        limits["allowed_domains"] = list(task.allowed_domains)
    return Preflight(
        experiment_id=experiment.id,
        run_id=run_id,
        execution_kind=bundle.run.execution_kind,
        eligible=not blockers,
        blockers=tuple(blockers),
        participants=tuple(participants),
        limits=limits,
        planned_rounds=rounds,
        planned_requests_upper_bound=requests,
        permitted_tools=tuple(
            sorted({t for a in experiment.agents for t in a.permissions.allowed_tools})
        ),
        authorization_required=required,
    )


def authorize(
    controller: "Controller",
    run_id: UUID,
    *,
    paid: bool,
    external: bool,
    upper_bound: Decimal | None,
    quota: bool = False,
) -> LaunchAuthorization:
    report = preflight(controller, run_id)
    if not report.eligible:
        raise ValueError("Preflight blocked: " + "; ".join(report.blockers))
    if "authorize_paid" in report.authorization_required and not (
        paid and external and upper_bound
    ):
        raise PermissionError(
            "Remote research requires disclosure, paid authorization and a cost bound"
        )
    if "authorize_quota" in report.authorization_required and not (quota and external):
        raise PermissionError("CLI inference requires quota acknowledgment and context disclosure")
    env = workspace_env(controller.settings.data_dir)
    allowances = {}
    for row in report.participants:
        if row.get("adapter") and row.get("endpoint") and report.execution_kind == "live":
            profile = ConfigurationStore(controller.settings.database_path).get(
                "profile", str(row["profile_id"]), int(str(row["profile_version"]))
            )
            assert isinstance(profile, ModelProfile)
            if not profile.local:
                provider_environment(profile.runtime)
                allowances[f"{profile.id}@{profile.version}"] = str(
                    spending_allowance(profile, env)
                )
    return LaunchAuthorization(
        report=report,
        authorize_paid=paid,
        authorize_external=external,
        authorize_quota=quota,
        upper_bound_usd_per_attempt=upper_bound,
        profile_allowances_usd=allowances,
    )


def format_preflight(report: Preflight) -> str:
    lines = [
        "Eligible for separately authorized launch" if report.eligible else "Launch blocked",
        f"{report.execution_kind} · {report.planned_rounds} rounds · "
        f"at most {report.planned_requests_upper_bound} "
        + (
            "DOXA invocations including DOXA retries/tools"
            if "authorize_quota" in report.authorization_required
            else "model requests including retries/tools"
        ),
    ]
    if "authorize_quota" in report.authorization_required:
        from doxa.providers.cli_session import CLI_RETRY_WARNING

        lines.append("Subscription quota: consumption unknown; USD billing unavailable, not zero")
        lines.append(CLI_RETRY_WARNING)
    if "authorize_quota" not in report.authorization_required or (
        "authorize_paid" in report.authorization_required
    ):
        lines.append(
            "Run spending ceiling USD: " + str(report.limits.get("run_cap_usd", "unknown"))
        )
    for row in report.participants:
        lines.append(
            f"{row.get('name')} · {row.get('role')} · "
            f"{row.get('profile_id')} v{row.get('profile_version')} · "
            f"{row.get('model_id', 'synthetic')} · {row.get('status', 'fixture')}"
        )
        if row.get("transport") == "cli_session":
            lines.append(
                "Reasoning requested: "
                + str(row.get("reasoning_effort") or "CLI default (unverified)")
            )
    lines.extend("Blocked: " + text for text in report.blockers)
    lines.append(
        "Authorization: " + (", ".join(report.authorization_required) or "no paid API requested")
    )
    lines.append(report.caveat)
    return "\n".join(lines)
