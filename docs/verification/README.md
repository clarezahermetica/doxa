# Foundation verification — October 23, 2026

Local verification on Windows with Python 3.14.7 and Node.js 24.20.0.
Python 3.12 is declared/syntax-targeted and included in CI, but was not executed locally.

| Check | Observed result |
| --- | --- |
| Foundation tests | 24 passed. |
| Ruff | Passed. |
| mypy strict | Passed, 30 source files. |
| TypeScript / Vite production build | Passed; generated API response types include server defaults. |
| Installable Python wheel | Built and inspected; packaged migration initialized revision 0001 successfully from an installed wheel copy. |
| Browser → API → SQLite → UI | CLI-created synthetic run listed and selected in Studio, with one persisted RUN_CREATED event. |
| Local API request logs | GET /api/runs and GET /api/runs/e34fd08e-cdf3-5170-bd5e-b7239c3ca96b both returned 200. |
| Browser console | No warning or error entries returned by the browser log reader. |
| CLI/API/export parity | Same parsed run/event bundle in integration test. |
| Safety boundary | All four protocol modes reject execution; DisabledSandbox raises before any code runs. |

Tests cover atomic rollback on duplicate records, concurrent sequences and shared
configuration, conflicting idempotency keys, immutable history, reload/migration,
ancestry checks, provenance, private-memory ownership/validation references, artifact
tampering, budget persistence/settlement/aggregate ceiling, missing runs, HTTP validation,
Host restriction, cross-origin preflight rejection, and interface parity.

One dependency deprecation warning is emitted by the installed Starlette TestClient
for its httpx compatibility path. It does not fail the tests. No warning was hidden.
Python 3.12, hosted CI, live providers, actual sandbox execution, checkpoint restoration,
research outcomes and eventual release acceptance remain unverified/unimplemented.

Historical graphical screenshots are retained locally and excluded from the terminal-only
proof-of-concept source tree.
