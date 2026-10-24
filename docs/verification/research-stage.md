# Research-stage verification — October 24, 2026

Local Windows checks on Python 3.14.7 / Node 24.20.0:

- Complete pytest suite: 95 passing tests (57 existing plus 38 new cases).
- Ruff: clean. Strict mypy: clean, 49 Python source files.
- Domain JSON Schema / OpenAPI regenerated; Studio TypeScript types regenerated.
- Studio TypeScript and Vite production build: passed. This was a local build,
  not deployment. No new UI design or hosted CI result is claimed.
- Actual `doxa research-demo` CLI invocation: completed, 42 persisted events.
  A new controller loaded the completed run and compared both children: verified
  equal starting state, task success 1 versus 0, one approved retrieved memory
  before revocation and none afterward. Environment operations and verifier tests
  were real built-in finite-policy operations; agent inputs and review label were
  explicitly synthetic. Local output is ignored under `.doxa/`.
- Existing migration compatibility, provider mocks, stale retrieval and spending
  tests retained. The live Moss operation from an earlier task was not retried.

One existing warning remains: Starlette's TestClient deprecates its current httpx
integration. Tests passed; this task does not claim a dependency migration.

Reproduction and per-system events/tests/limitations: [research-systems.md](../research-systems.md).
The secure generated-code runner and locked code-repair flagship remain blocked.
No paid call, deployment or infrastructure configuration occurred in this task.
