"""Read-only Live Council projection; inputs are already scoped to one trajectory."""

from dataclasses import dataclass
from uuid import UUID

from doxa.core.models import (
    Agent,
    Challenge,
    Checkpoint,
    Claim,
    ClaimAssessment,
    ContextManifest,
    Decision,
    Event,
    ModelCall,
    ProviderActivity,
    Record,
    ReflectionDecision,
    ResearchOutcome,
    ResponseNormalization,
    RunState,
)

Research = Claim | Challenge | ClaimAssessment | Decision | ResearchOutcome | ReflectionDecision
Milestone = ModelCall | ProviderActivity | ResponseNormalization | RunState | Checkpoint


def short(identity: UUID) -> str:
    return identity.hex[:10]


@dataclass(frozen=True)
class Part:
    record: Research | Milestone
    actor: UUID | None
    action: str
    text: str
    claim: UUID | None = None
    target: UUID | None = None
    evidence: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class Contribution:
    event: Event
    parts: tuple[Part, ...]
    operational: bool = False

    @property
    def key(self) -> tuple[UUID, bool]:
        return (self.event.id, self.operational)


class CouncilFeed:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.events: list[Event] = []
        self.rows: list[Contribution] = []
        self.records: dict[UUID, Record] = {}
        self.record_events: dict[UUID, Event] = {}
        self.agents: dict[UUID, Agent] = {}
        self.lineages: dict[UUID, UUID] = {}
        self.versions: dict[UUID, int] = {}
        self.superseded: set[UUID] = set()
        self.answered: set[UUID] = set()
        self.related: dict[UUID, list[Part]] = {}

    def sync(self, events: list[Event], agents: tuple[Agent, ...]) -> None:
        n = len(self.events)
        if n > len(events) or (n and events[n - 1].id != self.events[-1].id):
            self.reset()
            n = 0
        self.agents = {a.id: a for a in agents}
        for event in events[n:]:
            self.add(event)

    def add(self, event: Event) -> None:
        self.events.append(event)
        for record in event.payload:
            self.records[record.id] = record
            self.record_events[record.id] = event
            if isinstance(record, Claim):
                prior = record.revises_id
                self.lineages[record.id] = (
                    self.lineages.get(prior, prior) if prior else record.commitment_id or record.id
                )
                self.versions[record.id] = self.versions.get(prior, 0) + 1 if prior else 1
                if prior:
                    self.superseded.add(prior)
            elif isinstance(record, Challenge) and record.responds_to_id:
                self.answered.add(record.responds_to_id)
        research, operational = [], []
        for record in event.payload:
            part = self.part(record)
            if part is not None:
                if isinstance(
                    record,
                    (ModelCall, ProviderActivity, ResponseNormalization, RunState, Checkpoint),
                ):
                    operational.append(part)
                else:
                    research.append(part)
                    if part.claim:
                        self.related.setdefault(part.claim, []).append(part)
        if research:
            self.rows.append(Contribution(event, tuple(research)))
        if operational:
            self.rows.append(Contribution(event, tuple(operational), True))

    def responder(self, response: Challenge) -> UUID | None:
        """Use persisted authorship, never the original critic or presumed claim author."""
        event = self.record_events[response.id]
        actors = {event.actor_id} if event.actor_id else set()
        for record in event.payload:
            if isinstance(record, ResponseNormalization) and record.disposition == "accepted":
                context = self.records.get(record.context_id)
                if isinstance(context, ContextManifest) and context.agent_id == record.agent_id:
                    actors.add(record.agent_id)
        # Conflicting provenance is not permission to guess a speaker.
        return next(iter(actors)) if len(actors) == 1 else None

    def part(self, p: Record) -> Part | None:
        if isinstance(p, Claim):
            return Part(
                p,
                p.author_id,
                "Revision" if p.revises_id else "Claim",
                p.proposition,
                p.id,
                p.revises_id,
                p.evidence_ids,
            )
        if isinstance(p, Challenge):
            action = f"Response: {p.response or 'recorded'}" if p.responds_to_id else "Criticism"
            text = p.objection
            if p.requested_correction:
                text += "\n\nRequested correction: " + p.requested_correction
            if p.proposed_revision:
                text += "\n\nProposed wording: " + p.proposed_revision
            return Part(
                p,
                self.responder(p) if p.responds_to_id else p.critic_id,
                action,
                text,
                p.claim_id,
                p.responds_to_id or p.target_decision_id,
                p.evidence_ids,
            )
        if isinstance(p, (Decision, ClaimAssessment)):
            if isinstance(p, Decision):
                actor, action = p.adjudicator_id, f"Judgment: {p.outcome}"
            else:
                actor, action = p.agent_id, f"Reassessment: {p.stance}"
            return Part(p, actor, action, p.reason, p.claim_id, p.challenge_id, p.evidence_ids)
        if isinstance(p, ResearchOutcome):
            return Part(p, None, f"Outcome: {p.epistemic_outcome}", p.reason)
        if isinstance(p, ReflectionDecision):
            return Part(
                p, None, f"Reflection: {'skipped' if p.skipped else p.action}", p.reason_code
            )
        if isinstance(p, ProviderActivity):
            return Part(p, p.agent_id, "Provider", p.stage.replace("_", " "), target=p.call_id)
        if isinstance(p, ModelCall):
            text = f"{p.assignment.model_id} · {p.status}"
            if p.error_category:
                text += f" · {p.error_category}"
            return Part(p, p.agent_id, "Model call", text, target=p.call_id)
        if isinstance(p, RunState):
            return Part(p, None, f"Run: {p.status}", p.reason_code)
        if isinstance(p, Checkpoint):
            return Part(p, None, "Checkpoint", f"Saved cursor {short(p.event_cursor)}")
        if isinstance(p, ResponseNormalization) and p.disposition != "accepted":
            return Part(p, p.agent_id, "Response rejected", p.reason_code, target=p.model_call_id)
        return None

    def threads(self, part: Part) -> set[UUID]:
        if part.claim in self.lineages:
            assert part.claim is not None
            return {self.lineages[part.claim]}
        if isinstance(part.record, ResearchOutcome):
            return {
                self.lineages[d.claim_id]
                for identity in part.record.decision_ids
                if isinstance(d := self.records.get(identity), Decision)
                and d.claim_id in self.lineages
            }
        return set()

    def filtered(
        self,
        *,
        all_activity: bool,
        agent: UUID | None,
        thread: UUID | None,
    ) -> list[Contribution]:
        if all_activity and not agent and not thread:
            return self.rows[:]
        result = []
        for row in self.rows:
            if row.operational and not all_activity:
                continue
            parts = tuple(
                p
                for p in row.parts
                if (agent is None or p.actor == agent)
                and (thread is None or thread in self.threads(p))
            )
            if parts:
                result.append(Contribution(row.event, parts, row.operational))
        return result

    def claim_label(self, identity: UUID) -> str:
        if identity not in self.lineages:
            return f"claim {short(identity)} (outside this projection)"
        return f"C-{short(self.lineages[identity])} v{self.versions[identity]}"

    def subject(self, p: Part) -> str:
        title = p.action
        if isinstance(p.record, Challenge) and not p.record.responds_to_id:
            title += f" [{short(p.record.id)}]"
        if p.claim:
            title += " · " + self.claim_label(p.claim)
        if p.target:
            target = self.records.get(p.target)
            if isinstance(target, Claim):
                if isinstance(p.record, Claim):
                    title += ", revises v" + str(self.versions[target.id])
                else:
                    title += " → " + self.claim_label(target.id)
            elif isinstance(target, Challenge):
                title += " → criticism " + short(target.id)
            elif isinstance(target, Decision):
                title += " → judgment " + short(target.id)
        return title

    def status(self, p: Part) -> str:
        if isinstance(p.record, Claim):
            if p.record.id in self.superseded or p.record.status == "superseded":
                return "superseded here"
            return f"current here · {p.record.status}"
        if isinstance(p.record, Challenge) and not p.record.responds_to_id:
            return "response recorded" if p.record.id in self.answered else "response pending"
        if isinstance(p.record, (Decision, ClaimAssessment)) and p.claim:
            return "prior version" if p.claim in self.superseded else "targets current version"
        return ""

    def speaker(self, p: Part) -> str:
        a = self.agents.get(p.actor) if p.actor else None
        if a:
            return f"{a.display_name} ({a.role.value})"
        if isinstance(p.record, (ResearchOutcome, RunState, ReflectionDecision, Checkpoint)):
            return "System"
        if p.actor:
            return f"Unknown participant {short(p.actor)}"
        if isinstance(p.record, Challenge) and p.record.responds_to_id:
            return "Unknown responder (authorship not established)"
        return "Unknown author"
