# October 24 backend verification

Environment: Windows, Python 3.14.7, Node.js 24.20.0. Python 3.12 and hosted CI were not
run locally. The installed JavaScript and Python Moss SDKs are 1.21.0; Python's native
Windows wheel imports successfully. No model was invoked during offline validation.

| Boundary / check | Observed result |
| --- | --- |
| pytest | 57 passed, including the original 24 foundation tests. |
| Ruff | Passed after formatting. |
| strict mypy | Passed, 43 source files. |
| API schema → generated TypeScript | Regenerated successfully; Studio build passed. |
| Old database compatibility | Test upgrades revision 0001 → 0002 and verifies original event bytes remain unchanged. |
| Four protocols | Actual local oracle/state flows execute with supplied synthetic answers; distinct 1/3/2/2 proposal phase counts. |
| Negative criticism | Passing candidate is retained against failing alternative; invalid criticism remains recorded. |
| Checkpoint / branch | Observable state roundtrip and corrupted snapshot rejection; parent history retained. |
| Memory fixture | Private A/B, verified shared, quarantined false, revoked and corrected/superseded records tested. |
| Stale/unavailable Moss boundary | Hostile candidate IDs filtered after await; in-flight revocation wins; failure falls back locally. |
| RunPod HTTP | Mocked request/usage/error/secret tests and retry/accounting integration; no real RunPod call. |
| Cancellation / accounting | In-flight mocked cancellation leaves an uncertain operation and null billing. Dispatch cannot be repeated after restart; reconciliation is explicit. |
| API / CLI / data | Shared controller and ledger; API execution matches persisted inspection; export parity retained. |
| Browser | Studio lists original configured fixture plus four completed synthetic runs; selected adversarial run shows 25 actual persisted events. |
| Browser limitation | Vite HMR WebSocket reports a connection error in the in-app browser. Manual reload and API data inspection work; automatic HMR is not verified. |
| Private GitHub repository | Connector read-back reports `visibility: private`, repository size 0, and the expected owner. Remote configured; no code uploaded. |
| Credential storage | Root `.env` is ignored by Git; root JS SDK is not a Studio dependency. Request validation does not echo submitted secrets. |

The installed Starlette TestClient emits one deprecation warning about its httpx
compatibility path. No warning was suppressed. Scope and remaining work are recorded
in `docs/backend-stage.md`; these checks do not establish a full DOXA release.

## Subsequent user-authorized JavaScript Moss smoke test

Exact requested index/query/topK: `agent-memory-context` / `how to sleep` / `3`.
One actual SDK attempt timed out after 60 seconds without documents. The local process
was stopped, the run marked failed, and billing left unknown with a $1 reservation held.
No live index mutation, synchronization, retry, or RunPod deployment/call occurred.
The outcome is `.doxa/moss-live-lookup.json` (ignored, local only), with corresponding
events and a content-hashed diagnostic artifact in the canonical ledger.
