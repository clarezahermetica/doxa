# Terminal workbench

Install and launch using [README](../README.md). The existing Textual application is
the primary interface; CLI commands use the same controller and workspace.

## Begin an experiment

1. Open `doxa`. Select an existing workspace or explicitly create a new empty one.
   `W` opens workspace selection; Settings shows its canonical path. Changing the
   shell directory does not select another research history.
2. Press Ctrl+P and choose **Add agent template**. Define the role, instructions,
   permissions and memory scope. Multiple instances can share a template or model.
3. For an offline exercise, leave model assignment optional and select synthetic
   execution. For future live work, **Choose model and connection** saves a versioned
   profile without making an inference request. Use the exact model ID and capabilities
   supported by your endpoint; credentials are masked references, not agent names.
4. Choose **Create experiment**, supply the research question, participants, protocol
   and resource limits, then **Import evidence** into that configured experiment.
5. Inspect launch preflight. **Start selected run** distinguishes synthetic execution
   from explicitly authorized live inference. Completed runs cannot simply restart;
   another attempt is an explicit operation with new history.
6. Inspect Activity, Claims, Sources, Contexts and Evaluations. **Review branch and
   revise claims** supports immutable human proposals, challenges, responses and review.
   **Compare trajectories** and **Export experiment history** inspect/export real records.

F1 opens searchable guidance and Ctrl+P opens commands. Unavailable actions explain
which prerequisite or run state blocks them. Raw JSON is an optional inspector.

Follow the [complete offline exercise](canonical-research.md) for source files, staged
criticism, revisions, comparisons and an independently inspectable export. Follow
[separate live acceptance](live-acceptance.md) only with a named provider/model and
explicit spending/disclosure approval. Saving a profile is not connection verification.

For an existing Codex account session, select **Local account CLIs / Codex CLI** in
Connection setup. **Check installed CLIs** reports safe local readiness without inference.
See [CLI setup](cli-providers.md) for the distinct quota acknowledgment and limits;
this path uses no API credential or positive USD allowance.

## What a run records

Every participant has an instance ID, template/instruction versions and a pinned model
assignment. Sequential turns see earlier committed messages; parallel rounds start from
a fixed history cursor, with actual completion order retained. Calls, rounds, concurrency,
time and token admission are bounded alongside durable spending controls.

Context manifests identify the actual permitted sources, history and eligible memories
supplied to a request. Private, revoked and quarantined material cannot become eligible
just because a search adapter returns it. Shared model identity remains visible; several
agents agreeing does not establish independent corroboration or objective truth.

Claims and revisions retain exact evidence/version links. Human judgments, model
adjudication and deterministic checks remain different record types/provenance. Citation
linkage or a valid source span does not establish entailment. Text-analysis checkpoints
and forks restore recorded history; they do not restore a model's hidden state, replay
paid calls or automatically resume inference.

## Evidence and retrieval

TXT, Markdown, JSON, text PDFs and DOCX are supported subject to import/extraction bounds.
Original bytes and extracted text have separate hashes and parser provenance. PDF/DOCX
parsing has a 12-second wall timeout, 512 MiB memory and 6-second CPU limits through
Windows Job Objects or Unix resource limits. Archive expansion and extracted text are
bounded. OCR, embedded-object execution and layout fidelity are not provided.

Uploading retains the complete original; it does not imply every call received it.
Context assembly includes full authorized source text when its budget share permits.
Otherwise it supplies multiple ranked excerpts with original character ranges and PDF
page locations, records partial coverage in the context manifest, and retains the
full source artifact. Eligible memory/history receive reserved context room. Inspect
the persisted context messages to determine exactly which text an agent received.

SQLite FTS5/BM25 and optional Moss snapshots search authorized material; they do not own
experimental truth or memory trust. Moss cache reuse remains scoped by project, run and
participant, with eligibility rechecked after retrieval. Live Moss acceptance and remote
cloud synchronization are unverified. See [provider support](provider-support.md).

Web research requires explicit run/agent permissions, authorization and quotas. Approved
fetches use allowlisted HTTPS domains, validated public DNS, TLS, no redirects/proxies,
a cumulative I/O deadline and a 256 KiB response bound. DNS runs in a credential-filtered
child process that can be terminated on timeout. Synthetic tools return labeled fixtures;
no live search provider is configured. Generated code receives no network capability.

## Supervision and automation

Closing the viewer leaves detached execution separate from inspection. Reopen the same
workspace to follow committed events. Cancellation does not establish remote termination
or final billing. Use [recovery](recovery.md) for interrupted calls and held reservations.

Use `doxa --help` for exact CLI syntax. Common entry points include `models`, `agents`,
`experiment new`, `run preflight`, `run start`, `run watch`, `run cancel`, `claims`,
`compare` and `export`; list/inspection commands offer readable output and `--json` where
supported. The optional loopback API is started with `doxa serve`; it is not a graphical UI.

Legacy cache-policy CLI examples remain in `examples/council.json`, `backend-run.json`,
`execute-offline.json` and `memory-query.json`. They are explicit synthetic fixtures for
compatibility scripting, not live research results or required terminal setup.
