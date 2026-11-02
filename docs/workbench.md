# DOXA terminal research workbench

This is a terminal-only local research prototype. See [audit](workbench-audit.md)
for the baseline and [status](status.md) for acceptance limits.

## Models and agents

GPT and Claude can power Council participants through direct APIs. Runpod is optional
for a served Qwen (or another supported text-chat model). An agent template carries
identity, instructions, permissions and a pinned model-profile version. An experiment
creates separately identified instances with template ID/version and exact assignments.
Several instances may share a role, profile and credential. This is not independent
source corroboration.

The terminal's Ctrl+P actions create and revise templates/profiles without UUID
editing. Revisions append immutable configuration versions; old experiments retain their
snapshots. Saving a profile makes no external request. Keys are never returned by the API.
Use exact model IDs from your own provider account; no model name or price is invented.

Native OpenAI uses text Chat Completions with `max_completion_tokens` and `store:false`.
It omits temperature because support varies by model; non-default profile temperatures
are rejected. Claude uses text Messages with `anthropic-version: 2023-06-01` and no
extended thinking/tools. Streaming, native structured output and multimodal requests
remain unsupported. A compatible model ID is still required: these are not universal
adapters for every model/API feature.

In the selected workspace's private `.env` (preserve existing Moss/Runpod keys):

```dotenv
OPENAI_API_KEY=replace_me
ANTHROPIC_API_KEY=replace_me
DOXA_OPENAI_ENABLED=false
DOXA_OPENAI_ALLOWANCE_USD=0
DOXA_CLAUDE_ENABLED=false
DOXA_CLAUDE_ALLOWANCE_USD=0
DOXA_WEB_ENABLED=false
```

Credential references: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `RUNPOD_API_KEY`.
A live run requires an enabled profile, provider switch, positive allowance, assigned
agent permission, explicit paid and external-disclosure authorization, and a complete
per-attempt bound or applicable configured pricing. Run/global/provider ceilings and
uncertain-billing holds still apply. No inference was used for this implementation.

## Open the terminal

Follow the source installation in README.md, then run `doxa`. Choose an existing
workspace or explicitly create a new one. F1 opens help; Ctrl+P opens research actions.
The selected workspace holds the canonical ledger and artifacts outside application
files. Closing the viewer does not cancel a detached experiment worker. Inspect, cancel
and recover interrupted work explicitly; never replay ambiguous paid operations.

## Offline workflow

Open Ctrl+P and choose **Run offline demonstration**. It creates four synthetic
participants (one Researcher and three Skeptics), imports a labeled source, runs two
rounds and records eight contexts plus proposed claims and descriptive evaluation.
No model call, search request or Moss upload occurs. Inspect the timeline, Epistemic Git,
Memory & Evidence context manifests and Evaluations. Human revisions append new claims.
The JSON inspector and export retain all original records.

To create your own fixture experiment: add agent templates, create a question, choose
participants/counts, protocol, rounds and limits; import text in Memory & Evidence;
then start the synthetic run. The default answers are clearly labeled generic fixtures,
not meaningful model arguments. You can supply per-instance fixture text via the typed
execution contract. Live run configuration does not start inference.

```powershell
.\.venv\Scripts\doxa.exe demo
.\.venv\Scripts\doxa.exe demo --json
.\.venv\Scripts\doxa.exe agent-add --name 'Skeptic' --role skeptic --instructions 'Check evidence.'
.\.venv\Scripts\doxa.exe experiment new --name 'Review' --question 'What follows?' --member 'Skeptic:3'
.\.venv\Scripts\doxa.exe run start <run-id>
.\.venv\Scripts\doxa.exe run watch <run-id>
.\.venv\Scripts\doxa.exe evidence-import <configured-run-id> .\sources\paper.md
.\.venv\Scripts\doxa.exe console
```

`doxa` with no arguments opens Textual; `q` exits only the viewer. Its revision form
appends a human proposal. Existing JSON commands remain compatibility interfaces;
new workbench commands are readable, with `--json` on `models` and `demo`. The complete
legacy CLI has not been redesigned into command groups. Use `doxa --help` for exact syntax.

Browser development remains `doxa serve` plus `npm.cmd --prefix studio run dev`.
Only that CLI server enables the explicit development origin `http://127.0.0.1:5173`;
the packaged desktop has no development-origin exception or CORS wildcard.

## Scheduling and context

Solo Direct uses one participant/turn. Solo Deliberative uses one participant over
configured reconsideration rounds. Collaborative scheduling puts Researchers before
Executors, then Skeptics and Archivists. Adversarial scheduling starts with Executors,
then Researchers/Skeptics/Archivists and prompts challenges/responses across rounds.
These are bounded text protocols; no debate conclusion receives an oracle verdict.
Within a role, instance ID provides stable order. Sequential turns see earlier committed
messages. Parallel rounds share a fixed initial history cursor; completion order is
recorded and may vary. A global semaphore respects the Council limit and the smallest
assigned profile concurrency. SQLite serializes financial admission and commits.

Agent/round/call/time limits, conservative per-agent/aggregate token admission and the
existing durable spending guard bound execution. Retry capacity is charged conservatively
before admission. Exact message artifacts, instruction/profile/task versions, permitted
source IDs, eligible memory IDs and visible history IDs reconstruct context. UTF-8 byte
counts are conservative admission bounds, **not measured tokenizer usage**. Actual usage
and costs remain null when the provider does not report them.

Evidence imports accept UTF-8 text, Markdown and JSON up to 1 MB (JSON is source text,
not an executable document format). Each source is versioned, content-addressed and
private/shared scoped. Source revisions cannot broaden scope; import before starting
so a run's starting corpus is controlled. Workbench tasks capture type/version,
question/objective/criteria/artifact requirements, source IDs, network policy and Council
limits. Existing cache tasks retain their original path; code-repair declarations are
rejected until a real isolated runner exists.

FTS5/BM25 ranks already-authorized source/memory snapshots. This is a disposable derived
index, not another authoritative database. Migration 0003 stores a reusable FTS5 index in the canonical database. Immutable IDs
and content hashes detect accidental changes; only authorized IDs can be returned.
TXT, Markdown, JSON, text PDFs (up to 100 pages) and Word DOCX can be imported, up to
10 MB each with a 1 MB extracted-text bound. Original bytes and extracted text have
separate content hashes and a parser version. PDF/Word parsing uses a credential-free
subprocess, 12-second wall timeout, 512 MiB process memory and 6-second CPU limits
(Windows Job Objects; Unix resource limits). DOCX archive expansion is bounded.
There is no OCR, embedded-object execution or claim that extraction preserves layout. Memory Tribunal eligibility is rechecked separately. Moss
continues to authorize/reserve complete operations, filter stale/revoked results and
fall back locally. The optional Moss 1.21+ adapter saves local session snapshots in the selected data
workspace, scoped by project/run/participant. It restores a snapshot, enumerates its
actual IDs/text, removes ineligible IDs and adds only changed records before querying.
OS-held cache leases prevent concurrent writers and release after crashes. No cloud
push or automatic refresh is enabled. Legacy snapshots do not automatically re-embed.
Any load/SDK failure uses the existing local fallback; SQLite eligibility is still
rechecked after awaiting retrieval. This is local snapshot reuse, not verified remote
cloud synchronization. No live Moss request was made to verify these improvements.

## Bounded web tools

The typed `/api/workbench/runs/{run_id}/tools` command supports controller-directed
retrieval, independently of inference. Both agent `allowed_tools` and the task's exact
`approved_search` or `approved_fetch` mode must permit it, with explicit per-command
external authorization, domain allowlist and persistent quotas. Live fetching additionally
requires `DOXA_WEB_ENABLED=true`. It uses pinned public DNS addresses, original-host TLS
verification, no proxies/cookies/redirects, fixed HTTPS ports, 10-second I/O/12-second
outer timeout and 256 KiB response limit. DNS runs in a fixed credential-free child
process terminated on timeout; each underlying TLS/HTTP receive shares the remaining
absolute I/O budget. Incomplete declared-length responses are rejected. A request is
committed before dispatch; retries
return the persisted outcome rather than repeating external effects. Failures consume
quota. Result sources are private to the requesting participant until explicitly shared.
Tool timestamps, URLs, hashes, provider, outcomes and null unknown cost remain durable.

Search has offline fixture coverage but no selected live provider, pricing or paid-search
adapter. A task can opt into at most three structured tool follow-ups per participant
turn through `max_tool_rounds` (default zero). The controller validates the tool intent,
run/agent permissions, disclosure authorization, allowlisted domain and durable quota.
Context manifests record the retrieved source supplied on each follow-up. Call slots
and worst-case context/output tokens are reserved before the participant starts;
repeated tool requests beyond the cap fail rather than produce fabricated evidence.
Synthetic runs use only the offline mock adapter. Task configuration includes these policy fields;
creating a policy does not authorize a live request.
Generated-code execution remains disabled and receives no network capability.

## Rebuild and verify

Use `pip install -e ".[dev,packaging,moss]"` in the project's Python environment for
optional terminal build/test dependencies, then `scripts/build_terminal.ps1` for a
new, separately versioned internal terminal package. No binaries are published with
this proof-of-concept update. Run pytest, Ruff and strict mypy before distributing.
Never bundle private workspaces, credentials, research exports or model weights.

## Branch review and terminal operations

The terminal's review action use the same typed controller commands:
propose/revise a claim, challenge it, respond, record human adjudication, annotate named
rubric dimensions, save a text checkpoint and fork a history-pinned analysis branch.
Responses and accepted revisions remain unverified proposals. Human preference ratings
and source-reference counts are descriptive; objective correctness is null.

A text checkpoint verifies the exact canonical history, task and configuration artifacts.
Its child sees the pinned ancestor prefix, not later parent changes. This does not restore
external effects or replay paid calls; continuation is currently human analysis only.
Event streams keep following later review events after the model run has completed.
The local API supports explicit event-stream shutdown.

Terminal keys: N create experiment, A add agent, M add disabled model profile,
I import evidence, S start a configured synthetic run, X cancel an active run,
C review the selected branch, Q close the viewer. The offline worker runs in a separate
process and survives viewer exit. Live launch remains an explicitly authorized CLI or
terminal action. Common list/inspect/doctor commands default to readable output and
accept `--json`; low-level compatibility/serialized command tools remain available.
The frozen application includes the CLI: `.\DOXA.exe --cli console` or
`.\DOXA.exe --cli doctor --json`. `doxa studio` aliases the native desktop launcher.

Parser references: [pypdf extraction limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
Moss API behavior was checked against the installed 1.21 SDK and
[its official package documentation](https://pypi.org/project/moss/1.21.0/).
