"""Live and replay share this terminal renderer and the committed branch projection."""

from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import UUID

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import DescendantBlur, DescendantFocus, Key, Resize
from textual.widgets import Button, Select, Static, TextArea

from doxa.cli.council_feed import Contribution, CouncilFeed, Part, short
from doxa.cli.plain_text import terminal_text
from doxa.cli.turn_evidence import describe_turn_evidence, evidence_summary
from doxa.core.controller import Controller
from doxa.core.models import (
    Challenge,
    Checkpoint,
    Claim,
    ContextManifest,
    Event,
    Experiment,
    Provenance,
)
from doxa.core.models import ResponseNormalization as Normalization
from doxa.storage.artifacts import ArtifactStore

PAGE = 80
WIDE = 136
KeyId = tuple[UUID, bool]

HELP = """Live Council · keyboard and reading

With the feed focused:
  ↑/↓ select   Enter inspect   Space expand   T full/preview
  F follow claim   D compare versions   V citations   U turn input   B branch
  L select latest   Page Up/Down scroll   Esc back (inspector, filter, then prior tab)
  Ctrl+G return focus to feed from filters or Inspector

Use Tab or Shift+Tab to reach filters and buttons. The agent filter uses
recorded authorship. Research Feed is the conversation; All Activity adds
observed milestones. Research does not stop when you scroll up.
Press F1 again from this help to open the full command reference.

The observer sees the branch's records. Individual agents may have received
different sources. Ctrl+J opens the exact selected event. A branch requires a
verified checkpoint and creates analysis history only."""


class FeedScroll(VerticalScroll, can_focus=True):
    pass


class CouncilCard(Static):
    def __init__(self, key: KeyId):
        super().__init__(markup=False)
        self.key = key
        self.render_key: object = None

    async def on_click(self) -> None:
        owner = self.query_ancestor(LiveCouncil)
        await owner.select(self.key)
        owner.query_one(FeedScroll).focus()


@dataclass(frozen=True)
class ViewPosition:
    key: KeyId | None
    start: int
    end: int
    scroll: float
    agent: UUID | None


class LiveCouncil(Vertical):
    DEFAULT_CSS = """
    LiveCouncil { height: 1fr; }
    LiveCouncil #council-filters { height: 3; }
    LiveCouncil #council-mode { width: 1fr; }
    LiveCouncil #council-agent { width: 2fr; }
    LiveCouncil #council-layout { height: 1fr; }
    LiveCouncil #council-stream { width: 1fr; height: 1fr; }
    LiveCouncil CouncilCard { height: auto; padding: 0 1; margin-bottom: 1; }
    LiveCouncil CouncilCard.-selected { background: $boost; }
    LiveCouncil #council-inspector { display: none; width: 1fr; height: 1fr; }
    LiveCouncil.-inspecting #council-inspector,
    LiveCouncil.-wide #council-inspector { display: block; }
    LiveCouncil.-inspecting.-narrow #council-stream { display: none; }
    LiveCouncil.-wide #council-inspector { width: 42; border-left: solid $primary; }
    LiveCouncil #council-details { height: 1fr; border: none; }
    LiveCouncil #council-stream:focus { border-left: solid $primary; }
    LiveCouncil #council-details:focus { border-left: solid $primary; }
    LiveCouncil #council-commands, LiveCouncil #council-inspect-actions { height: 1; }
    LiveCouncil Button.compact { height: 1; min-height: 1; min-width: 1; padding: 0 1; }
    LiveCouncil #council-failure { height: auto; max-height: 2; display: none; }
    LiveCouncil #council-status { height: 1; color: $text; }
    """

    def __init__(self) -> None:
        super().__init__(id="live-council", classes="-narrow")
        self.projection = CouncilFeed()
        self.controller: Controller | None = None
        self.branch: UUID | None = None
        self.scope: tuple[UUID, UUID] | None = None
        self.mode = False
        self.agent: UUID | None = None
        self.followed: UUID | None = None
        self.return_position: ViewPosition | None = None
        self.selected: KeyId | None = None
        self.expanded: set[KeyId] = set()
        self.full_text = False
        self.rows: list[Contribution] = []
        self.cards: dict[KeyId, CouncilCard] = {}
        self.start = self.end = 0
        self.run_status = ""
        self.live_status = ""
        self.inspector_mode = "record"
        self.details_text = ""
        self.agent_options: tuple[UUID, ...] = ()
        self._head: UUID | None = None
        self.inspector_scroll: float | None = None
        self.unseen = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="council-failure", markup=False)
        with Horizontal(id="council-filters"):
            yield Select(
                [("Research Feed", "research"), ("All Activity", "all")],
                value="research",
                allow_blank=False,
                id="council-mode",
            )
            yield Select([("All agents", "")], value="", allow_blank=False, id="council-agent")
        with Horizontal(id="council-layout"):
            yield FeedScroll(id="council-stream")
            with Vertical(id="council-inspector"):
                yield TextArea(read_only=True, id="council-details")
                with Horizontal(id="council-inspect-actions"):
                    yield Button("Thread", id="council-thread", classes="compact")
                    yield Button("Diff", id="council-diff", classes="compact")
                    yield Button("Sources", id="council-sources", classes="compact")
                    yield Button("Branch", id="council-branch", classes="compact")
                    yield Button("Back", id="council-back", classes="compact")
        with Horizontal(id="council-commands"):
            yield Button("Run status", id="council-run-status", classes="compact")
            yield Button("Inspect", id="council-open", classes="compact")
            yield Button("Turn input", id="council-turn", classes="compact")
            yield Button("Follow claim", id="council-follow", classes="compact")
            yield Button("Full text", id="council-full", classes="compact")
            yield Button("Earlier", id="council-earlier", classes="compact")
            yield Button("Later", id="council-later", classes="compact")
            yield Button("Jump to latest", id="council-latest", classes="compact")
        yield Static(
            "Select a run to see its committed contributions.", id="council-status", markup=False
        )

    def on_resize(self, event: Resize) -> None:
        self.set_class(event.size.width >= WIDE, "-wide")
        self.set_class(event.size.width < WIDE, "-narrow")
        if self.cards:
            self.paint_cards()

    def row(self) -> Contribution | None:
        return next(
            (row for row in self.rows[self.start : self.end] if row.key == self.selected), None
        )

    async def clear_run(self) -> None:
        self.query_one("#council-failure", Static).display = False
        self.scope = None
        self.controller = None
        self.branch = None
        self.projection = CouncilFeed()
        self._head = None
        self.rows = []
        self.start = self.end = 0
        self.selected = None
        self.unseen = 0
        self.run_status = self.live_status = ""
        await self.render_page(reset=True)
        self.update_status()

    async def load(
        self,
        controller: Controller,
        branch: UUID,
        events: list[Event],
        exp: Experiment,
        status: str,
        live_status: str,
    ) -> None:
        if not events:
            return
        scope = (events[0].run_id, branch)
        new_scope = scope != self.scope or controller is not self.controller
        self.run_status, self.live_status = status, live_status
        failure = self.query_one("#council-failure", Static)
        failed = status.partition(" · ")[0] == "failed"
        failure.display = failed
        if failed:
            states = [r for e in events for r in e.payload if r.kind == "run_state"]
            reason = (
                getattr(states[-1], "reason_code", "not recorded") if states else "not recorded"
            )
            failure.update(
                terminal_text(f"Failure: {reason} · Run status: committed work and next actions")
            )
        if new_scope:
            self.scope, self.branch, self.controller = scope, branch, controller
            self.projection = CouncilFeed()
            self._head = None
            self.followed = None
            self.return_position = None
            self.selected = None
            self.expanded.clear()
            self.inspector_mode = "record"
            self.remove_class("-inspecting")
            self.inspector_scroll = None
            self.unseen = 0
            self.query_one("#council-agent", Select).disabled = False
            self.query_one("#council-mode", Select).disabled = False
        ids = tuple(a.id for a in exp.agents)
        if ids != self.agent_options:
            self.agent_options = ids
            self.agent = None
            picker = self.query_one("#council-agent", Select)
            picker.set_options(
                [
                    ("All agents", ""),
                    *(
                        (Text(terminal_text(f"{a.display_name} ({a.role.value})")), str(a.id))
                        for a in exp.agents
                    ),
                ]
            )
            picker.value = ""
        if events[-1].id != self._head:
            stream = self.query_one(FeedScroll)
            following = new_scope or (
                not self.has_class("-inspecting")
                and self.end == len(self.rows)
                and stream.scroll_y >= stream.max_scroll_y - 0.5
            )
            self.projection.sync(events, exp.agents)
            self._head = events[-1].id
            old_size = len(self.rows)
            self.rows = self.filtered()
            if new_scope and status.partition(" · ")[0] in {"completed", "failed", "cancelled"}:
                self.start, self.end = 0, min(PAGE, len(self.rows))
                self.selected = self.rows[0].key if self.rows else None
                await self.render_page(reset=True)
                self.call_after_refresh(stream.scroll_home, animate=False)
            elif new_scope or (following and len(self.rows) != old_size):
                await self.latest()
            else:
                self.unseen += max(0, len(self.rows) - old_size)
                self.paint_cards()
                self.inspect_selected()
        self.update_status()

    def filtered(self) -> list[Contribution]:
        return self.projection.filtered(
            all_activity=self.mode, agent=self.agent, thread=self.followed
        )

    async def render_page(self, *, reset: bool = False) -> None:
        stream = self.query_one(FeedScroll)
        visible = self.rows[self.start : self.end]
        keys = [row.key for row in visible]
        existing = list(self.cards)
        if reset or keys[: len(existing)] != existing:
            await stream.remove_children()
            self.cards.clear()
        new_cards = [CouncilCard(key) for key in keys if key not in self.cards]
        if new_cards:
            await stream.mount(*new_cards)
            self.cards.update((card.key, card) for card in new_cards)
        self.paint_cards()
        self.inspect_selected()
        self.update_status()

    def paint_cards(self) -> None:
        width = max(28, self.query_one(FeedScroll).size.width - 4)
        console = self.app.console
        for row in self.rows[self.start : self.end]:
            card = self.cards.get(row.key)
            if card is None:
                continue
            selected = row.key == self.selected
            full = self.full_text or row.key in self.expanded
            headings = tuple(self.heading(part) for part in row.parts)
            render_key = (width, selected, full, headings, row.parts)
            if card.render_key == render_key:
                continue
            text = Text(
                f"{'›' if selected else ' '} {row.event.timestamp:%H:%M:%S}Z"
                f" #{row.event.sequence} · {short(row.event.trajectory_id)}"
                + (" · activity" if row.operational else ""),
                style="bold" if selected else "",
            )
            if len(row.parts) > 1:
                text.append(f" · {len(row.parts)} records, one commit")
            preview_lines = max(1, 5 // len(row.parts))
            for p, heading in zip(row.parts, headings, strict=True):
                text.append("\n  " + terminal_text(heading), style="bold")
                body = Text(terminal_text(p.text))
                if not full:
                    lines = body.wrap(console, width)
                    body = Text("\n").join(list(lines)[:preview_lines])
                    if len(lines) > preview_lines:
                        body.append("\n… more · Space", style="italic")
                text.append("\n")
                text.append_text(body)
            card.render_key = render_key
            card.update(text)
            card.set_class(selected, "-selected")

    def heading(self, part: Part) -> str:
        suffix = self.projection.status(part)
        provenance = {
            Provenance.HUMAN_ANNOTATION: "human review",
            Provenance.LLM_EVALUATOR: "model review",
        }.get(part.record.provenance)
        return (
            f"{self.projection.speaker(part)} · {self.projection.subject(part)}"
            + (f" · {suffix}" if suffix else "")
            + (f" · {provenance}" if provenance else "")
        )

    def update_status(self) -> None:
        count = len(self.rows)
        remaining = count - self.end
        scope = (
            f"Following C-{short(self.followed)} · Esc clears · "
            if self.followed is not None
            else ""
        )
        if not self.scope:
            text = "Select a run to see its committed contributions."
        else:
            page = f"{self.start + 1}–{self.end}/{count}" if count else "No matching contributions"
            text = f"{scope}{page} · {self.run_status}"
            if self.unseen:
                text += f" · +{self.unseen} new · L jumps"
            elif remaining:
                text += f" · {remaining} later · L jumps"
            elif count and self.query_one(FeedScroll).scroll_y < (
                self.query_one(FeedScroll).max_scroll_y - 0.5
            ):
                text += " · Reading earlier · L jumps"
            if self.live_status:
                text += " · " + self.live_status
        focused = self.app.focused
        focus = (
            "Feed"
            if isinstance(focused, FeedScroll)
            else "Inspector"
            if (focused is not None and any(n.id == "council-inspector" for n in focused.ancestors))
            else "Controls"
        )
        # Focus and pending arrivals must remain visible in an 80-column footer.
        prefix = f"Focus: {focus}" + ("" if focus == "Feed" else " · Ctrl+G feed")
        if self.unseen:
            prefix += f" · +{self.unseen} new"
        text = prefix + " | " + text
        self.query_one("#council-status", Static).update(terminal_text(text))
        self.query_one("#council-earlier", Button).disabled = self.start == 0
        self.query_one("#council-later", Button).disabled = self.end >= count
        row = self.row()
        self.query_one("#council-open", Button).disabled = row is None
        self.query_one("#council-turn", Button).disabled = row is None
        follow = self.query_one("#council-follow", Button)
        follow.label = "Show Council" if self.followed else "Follow claim"
        follow.disabled = self.followed is None and (row is None or not self.choices(row))

    def choices(self, row: Contribution) -> set[UUID]:
        return set().union(*(self.projection.threads(part) for part in row.parts))

    async def latest(self) -> None:
        self.unseen = 0
        self.end = len(self.rows)
        self.start = max(0, self.end - PAGE)
        self.selected = self.rows[-1].key if self.rows else None
        self.inspector_mode = "record"
        await self.render_page()
        self.call_after_refresh(self.query_one(FeedScroll).scroll_end, animate=False)

    async def page(self, direction: int) -> None:
        if direction < 0:
            self.end = self.start
            self.start = max(0, self.end - PAGE)
        else:
            self.start = self.end
            self.end = min(self.start + PAGE, len(self.rows))
        self.selected = self.rows[self.start].key if self.start < self.end else None
        await self.render_page()
        self.query_one(FeedScroll).scroll_home(animate=False)

    async def select(self, key: KeyId) -> None:
        if key not in self.cards:
            return
        self.selected = key
        self.inspector_mode = "record"
        self.paint_cards()
        self.inspect_selected()
        self.update_status()

    async def follow(self) -> None:
        if self.followed is not None:
            await self.unfollow()
            return
        row = self.row()
        if row is None:
            return
        choices = self.choices(row)
        if len(choices) != 1:
            self.notify("Select a contribution that targets one claim lineage.")
            return
        stream = self.query_one(FeedScroll)
        self.return_position = ViewPosition(
            self.selected, self.start, self.end, stream.scroll_y, self.agent
        )
        self.followed = next(iter(choices))
        self.agent = None
        self.query_one("#council-agent", Select).disabled = True
        self.query_one("#council-mode", Select).disabled = True
        self.rows = self.filtered()
        index = next(i for i, candidate in enumerate(self.rows) if candidate.key == row.key)
        self.start = (index // PAGE) * PAGE
        self.end = min(self.start + PAGE, len(self.rows))
        if self.end == len(self.rows):
            self.unseen = 0
        await self.render_page(reset=True)
        self.call_after_refresh(self.cards[row.key].scroll_visible, animate=False, force=True)

    async def unfollow(self) -> None:
        saved = self.return_position
        if not self.followed or not saved:
            return
        self.followed = self.return_position = None
        self.agent = saved.agent
        self.query_one("#council-agent", Select).disabled = False
        self.query_one("#council-mode", Select).disabled = False
        self.rows = self.filtered()
        self.selected, self.start, self.end = saved.key, saved.start, saved.end
        await self.render_page(reset=True)
        self.call_after_refresh(
            self.query_one(FeedScroll).scroll_to, y=saved.scroll, animate=False, force=True
        )

    def claim(self, row: Contribution) -> Claim | None:
        for part in reversed(row.parts):
            if part.claim and isinstance(claim := self.projection.records.get(part.claim), Claim):
                return claim
        return None

    def evidence(self, row: Contribution) -> tuple[UUID, ...]:
        return tuple(dict.fromkeys(identity for p in row.parts for identity in p.evidence))

    def context(self, row: Contribution) -> ContextManifest | None:
        for audit in row.event.payload:
            if isinstance(audit, Normalization):
                record = self.projection.records.get(audit.context_id)
                if isinstance(record, ContextManifest):
                    return record
        return None

    def compare_text(self, claim: Claim) -> str:
        projection = self.projection
        before = projection.records.get(claim.revises_id) if claim.revises_id else None
        after = claim
        if not isinstance(before, Claim):
            before = claim
            root = projection.lineages.get(claim.id)
            candidates = [
                record
                for record in projection.records.values()
                if isinstance(record, Claim)
                and record.id != claim.id
                and projection.lineages.get(record.id) == root
            ]
            if not candidates:
                return "No other version of this claim is visible on this trajectory."
            after = candidates[-1]
        words, changed = before.proposition.split(), after.proposition.split()
        chunks = []
        for tag, a, b, c, d in SequenceMatcher(a=words, b=changed).get_opcodes():
            if tag in {"delete", "replace"}:
                chunks.append("− " + " ".join(words[a:b]))
            if tag in {"insert", "replace"}:
                chunks.append("+ " + " ".join(changed[c:d]))
        return (
            f"{projection.claim_label(before.id)} → {projection.claim_label(after.id)}\n\n"
            + ("\n".join(chunks) or "No word changes.")
            + f"\n\nOriginal exact text:\n{before.proposition}"
            + f"\n\nRevised exact text:\n{after.proposition}"
        )

    def inspect_selected(self) -> None:
        row = self.row()
        if row is None:
            text = "Select a contribution to inspect it."
            claim = None
        else:
            claim = self.claim(row)
            if self.inspector_mode == "diff" and claim:
                text = self.compare_text(claim)
            elif self.inspector_mode == "turn":
                manifest = self.context(row)
                if manifest and self.controller:
                    text = describe_turn_evidence(
                        manifest, ArtifactStore(self.controller.settings.data_dir / "artifacts")
                    )
                else:
                    text = (
                        "No explicit context link was saved for this contribution. "
                        "Its citations do not show what this turn received."
                    )
            else:
                text = self.describe(row, claim)
        if text != self.details_text:
            self.details_text = text
            self.query_one("#council-details", TextArea).load_text(terminal_text(text))
        self.query_one("#council-thread", Button).disabled = claim is None
        self.query_one("#council-diff", Button).disabled = claim is None
        self.query_one("#council-sources", Button).disabled = row is None or not self.evidence(row)
        self.query_one("#council-branch", Button).disabled = row is None or claim is None

    def describe(self, row: Contribution, claim: Claim | None) -> str:
        text = (
            f"Event #{row.event.sequence} · {row.event.id}\nTrajectory {row.event.trajectory_id}\n"
        )
        if row.event.trajectory_id != self.branch:
            text += "Inherited prefix of this trajectory.\n"
        if claim:
            text += f"Selected version: {self.projection.claim_label(claim.id)} · {claim.id}\n"
            if claim.dependency_ids:
                text += (
                    "Dependencies: "
                    + ", ".join(self.projection.claim_label(i) for i in claim.dependency_ids)
                    + "\n"
                )
            related = [
                p
                for p in self.projection.related.get(claim.id, [])
                if p.action.startswith(("Criticism", "Judgment"))
            ]
            text += (
                "\n".join(
                    f"{p.action} {short(p.record.id)} · {self.projection.status(p)}"
                    for p in related
                )
                + "\n"
            )
        manifest = self.context(row)
        if manifest:
            text += (
                f"Turn context {manifest.id}: {len(manifest.source_ids)} source(s), "
                f"{len(manifest.source_passages)} located excerpt(s)"
                " · Turn input opens saved text\n"
            )
            text += evidence_summary(manifest) + "\n"
        else:
            text += "No explicit context link on this event.\n"
        if self.evidence(row):
            text += f"{len(self.evidence(row))} attached evidence record(s) · Sources\n"
        if claim:
            checkpoints = sum(
                isinstance(p, Checkpoint) and p.trajectory_id == row.event.trajectory_id
                for p in self.projection.records.values()
            )
            text += (
                f"Recorded checkpoints on event trajectory: {checkpoints}"
                " · Branch checks eligibility\n"
            )
        text += "\nObserver view; participants may have seen different evidence.\n"
        for part in row.parts:
            if isinstance(part.record, Challenge) and part.record.responds_to_id:
                critic = (
                    self.projection.agents.get(part.record.critic_id)
                    if part.record.critic_id
                    else None
                )
                text += (
                    "\nOriginal critic: "
                    + (f"{critic.display_name} ({critic.role.value})" if critic else "unknown")
                    + "\n"
                )
            text += f"\n{self.heading(part)}\n{part.record.provenance.value}\n{part.text}\n"
        return text

    def inspect(self, mode: str = "record") -> None:
        if self.row() is None:
            return
        if not self.has_class("-inspecting"):
            self.inspector_scroll = self.query_one(FeedScroll).scroll_y
        self.inspector_mode = mode
        self.add_class("-inspecting")
        self.inspect_selected()
        self.query_one("#council-details", TextArea).focus(scroll_visible=False)

    def close_inspector(self) -> None:
        self.remove_class("-inspecting")
        self.inspector_mode = "record"
        self.inspect_selected()
        self.query_one(FeedScroll).focus(scroll_visible=False)
        if self.inspector_scroll is not None and not self.has_class("-wide"):
            self.call_after_refresh(
                self.query_one(FeedScroll).scroll_to,
                y=self.inspector_scroll,
                animate=False,
                force=True,
                immediate=True,
            )
        self.inspector_scroll = None

    def open_sources(self) -> None:
        from doxa.cli.research_view import CitationScreen

        row = self.row()
        if row and self.controller and (refs := self.evidence(row)):
            self.app.push_screen(CitationScreen(self.controller, refs, self.describe(row, None)))

    def open_thread(self) -> None:
        from doxa.cli.research_view import ThreadScreen
        from doxa.core.investigation import claim_threads_from_events
        from doxa.core.quality_labels import human_correction_labels

        row = self.row()
        if row is None or self.branch is None or (claim := self.claim(row)) is None:
            return
        # Thread rendering receives the original full run from the parent below; the
        # selected version remains explicit even if it is no longer current.
        from doxa.cli.console import ResearchConsole

        if not isinstance(self.app, ResearchConsole) or self.app.current_bundle is None:
            return
        threads = claim_threads_from_events(list(self.app.current_bundle.events), self.branch)
        matching = next((t for t in threads if claim in t.versions), None)
        if matching and self.controller:
            self.app.push_screen(
                ThreadScreen(
                    self.controller,
                    matching,
                    {a.id: a.display_name for a in self.projection.agents.values()},
                    set(human_correction_labels(list(self.projection.records.values()))),
                    initial_claim_id=claim.id,
                )
            )

    def prepare_branch(self) -> None:
        from doxa.cli.console import ResearchConsole
        from doxa.cli.council_branch import CouncilBranch

        row = self.row()
        if row is None or self.claim(row) is None or not self.branch or not self.controller:
            return

        def created(branch: UUID | None) -> None:
            if branch is not None and isinstance(self.app, ResearchConsole):
                self.app.branch_id = branch
                self.app.action_refresh()

        self.app.push_screen(CouncilBranch(self.controller, self.branch, row.event), created)

    def raw(self) -> None:
        from doxa.cli.inspectors import DetailScreen

        row = self.row()
        if row:
            self.app.push_screen(
                DetailScreen("Exact committed event", row.event.model_dump_json(indent=2))
            )

    async def on_select_changed(self, event: Select.Changed) -> None:
        if not isinstance(event.value, str):
            return
        if event.select.id == "council-mode":
            mode = event.value == "all"
            if mode == self.mode:
                return
            self.mode = mode
        elif event.select.id == "council-agent" and self.followed is None:
            agent = UUID(event.value) if event.value else None
            if self.agent == agent:
                return
            self.agent = agent
        else:
            return
        self.rows = self.filtered()
        await self.latest()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = (event.button.id or "").removeprefix("council-")
        if action:
            event.stop()
        await self.command(action)

    async def command(self, action: str) -> None:
        if action == "run-status":
            from doxa.cli.console import ResearchConsole

            if isinstance(self.app, ResearchConsole):
                self.app.action_run_summary()
        elif action == "open":
            self.inspect()
        elif action == "turn":
            self.inspect("turn")
        elif action == "back":
            self.close_inspector()
        elif action == "sources":
            self.open_sources()
        elif action == "thread":
            self.open_thread()
        elif action == "branch":
            self.prepare_branch()
        elif action == "diff":
            self.inspect("diff")
        elif action == "follow":
            await self.follow()
        elif action == "latest":
            await self.latest()
            self.query_one(FeedScroll).focus(scroll_visible=False)
        elif action == "earlier" and self.start:
            await self.page(-1)
        elif action == "later" and self.end < len(self.rows):
            await self.page(1)
        elif action == "full":
            self.full_text = not self.full_text
            self.query_one("#council-full", Button).label = (
                "Previews" if self.full_text else "Full text"
            )
            self.paint_cards()
        elif action == "expand" and self.selected:
            if self.selected in self.expanded:
                self.expanded.remove(self.selected)
            else:
                self.expanded.add(self.selected)
            self.paint_cards()

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        self.call_after_refresh(self.update_status)

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        self.call_after_refresh(self.update_status)

    async def on_key(self, event: Key) -> None:
        if event.key == "ctrl+g":
            event.stop()
            event.prevent_default()
            self.close_inspector()
            return
        focused = self.app.focused
        inspector_focused = focused is not None and any(
            node.id == "council-inspector" for node in focused.ancestors
        )
        if (
            event.key == "escape"
            and self.has_class("-inspecting")
            and (inspector_focused or isinstance(focused, FeedScroll))
        ):
            event.stop()
            event.prevent_default()
            self.close_inspector()
            return
        if not isinstance(focused, FeedScroll):
            return
        commands = {
            "enter": "open",
            "space": "expand",
            "f": "follow",
            "d": "diff",
            "v": "sources",
            "u": "turn",
            "b": "branch",
            "l": "latest",
            "t": "full",
        }
        if event.key in commands:
            event.stop()
            event.prevent_default()
            await self.command(commands[event.key])
        elif event.key == "escape" and self.followed:
            event.stop()
            await self.unfollow()
        elif event.key == "escape":
            from doxa.cli.console import ResearchConsole

            if isinstance(self.app, ResearchConsole):
                event.stop()
                self.app.leave_council()
        elif event.key in {"up", "down"} and self.cards:
            event.stop()
            event.prevent_default()
            keys = list(self.cards)
            index = keys.index(self.selected) if self.selected in keys else 0
            index += 1 if event.key == "down" else -1
            key = keys[min(max(index, 0), len(keys) - 1)]
            await self.select(key)
            self.cards[key].scroll_visible(animate=False)
