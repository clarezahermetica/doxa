# Architecture decisions

| Decision | Rationale / consequence |
| --- | --- |
| Preserve Python/FastAPI/Pydantic/SQLite/Alembic/Typer and React/TS/Vite | Locked stack; one local runtime, two thin clients. |
| Separate Experiment configuration, Run attempt and Trajectory branch | Makes repeated comparisons explicit without conflating branches with experiments. |
| Immutable typed record versions inside atomic event commits | Preserves disagreements and history; current-state projections will be explicit. |
| Canonical uppercase event enum | Preserves draft vocabulary; semantic additions and mappings documented in architecture. |
| Built-in sqlite3 plus Alembic/SQLAlchemy for migrations | Small explicit transaction surface; SQLAlchemy is migration plumbing, no second ORM model schema. |
| Packaged Alembic scripts | Installed CLI can initialize a ledger outside the checkout. |
| Integer micro-USD reservations, Decimal wire costs | Avoid binary float drift; retain unknown charges conservatively and never fabricate usage. |
| No provider SDKs or task runner yet | Current request is foundation only; defer external side effects until guards/contract tests exist. |
| Configuration-only controller and read-only Studio | Provides a real persisted inspection path while keeping unimplemented research visible. |
| No React Flow dependency yet | Add it when graph behavior is implemented, using persisted trajectory ancestry. |
| Source snapshots alongside a traceability register | Preserve the exact architecture consulted without editing Notion. |

The October 18 release lock describes the complete eventual release. The current user
request explicitly limits this implementation to its architecture foundation and does
not prioritize the flagship fixture. This is a deliberate phase boundary, not removal
of any locked release capability. No substantial architectural contradiction was found.

Still unresolved: exact provider/model IDs and prices, concrete container technology,
checkpoint manifest format beyond the shared minimum, memory validation policy,
rubric/evaluator metrics, experiment fixture selection and adapter execution semantics.
Those need narrow design/implementation decisions with independent checks. No invented
technical choice is presented as a preexisting Notion decision.

The pasted request ends at section 6 after “Experiments and runs”. Nothing beyond that
truncated point was assumed to be supplied. Shared entities were derived from the seven
accessible specifications and the visible requirements; unseen requirements remain unknown.

## Research stage addendum - October 24

- Preserve the finite stateful cache environment and keep generated code disabled;
  the user excludes infrastructure work and no secure container runner exists.
- Extend v1 records additively with historical defaults and a trajectory-state
  discriminator. Preserve all existing migration files and event names.
- Controller authorizes typed proposals; pure system projections/rules do not own
  persistence. Compare prepared branch cursors inside serialized writes.
- Restore/fork commits atomically; inspect failures without inventing successful
  restores. Replay is read-only; fresh continuations inherit only the pinned prefix.
- Rubric and deterministic metrics remain distinct; unknown costs stay null.
- README remains empty; research audit, reproduction and limitations live in docs.

## Backend infrastructure hardening - October 24

- Keep all six research-system algorithms and Moss governance/adapter code unchanged.
- Register only tested nonstreaming chat adapters: RunPod and explicitly configured
  HTTPS OpenAI-compatible. Unsupported capability declarations fail before sending.
- Readiness is local inspection; it never probes an endpoint, verifies a credential,
  checks credits or starts compute. No current profile/endpoint/model is invented.
- Retry only demonstrably pre-send connection failures. Post-send ambiguity retains
  reservations and blocks service dispatch until explicit operator reconciliation.
- Commit provider outcomes/known settlements and ledger response records atomically;
  recover interrupted states explicitly on terminal runs without resending work.
- Reuse existing JSON-backed configuration tables, normalize historical defaults for
  idempotent imports, and preserve earlier serialized rows. No SQL migration needed.
- Keep DisabledSandbox selected because WSL/container runtimes are unavailable. The
  concrete finite TaskEnvironment does not provide generated-code isolation.
- Keep README empty. Windows setup and full manual RunPod prerequisites live in docs.
