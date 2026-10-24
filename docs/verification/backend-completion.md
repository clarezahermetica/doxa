# Backend infrastructure verification — October 24, 2026

## Working implementation

- Provider registry and typed offline readiness/configuration reports; registered
  RunPod and explicit HTTPS OpenAI-compatible nonstreaming chat adapters.
- Persistent versioned model profiles and agent assignments, shared credential
  references, capability compatibility checks and historical configuration imports.
- Profile input/context/output/time/retry/concurrency limits; optional source/version
  pricing and complete-operation reservations with null unobserved billing.
- Enforced wall timeout, sanitized responses/metadata/errors, request fingerprints,
  safe pre-send retry bounds and conservative post-send uncertainty.
- Atomic provider outcome/settlement/event commits, explicit terminal-run recovery
  and operator-reported reconciliation with immutable audit events.
- Full finite TaskEnvironment port lifecycle and independent-verifier version/hash
  metadata. Generated-code execution remains disabled.
- CLI validation/catalog/agent/profile/doctor/recovery commands, typed API routes,
  Studio configuration/readiness/accounting inspection using the same backend.

## Checks and evidence

- **129 pytest cases pass**: the existing 95 plus 34 infrastructure cases. All
  provider HTTP calls in tests use mocks; no live inference was called.
- Ruff passes. Strict mypy passes on 52 Python source files, including a clean
  `--no-incremental --platform linux --python-version 3.12` check.
- Domain/OpenAPI schemas and Studio types regenerated. Studio TypeScript and Vite
  production build pass; it is a local build, not deployment.
- Fresh CLI initialization/inspection without credentials, pinned-profile reload,
  immutable historical serialized configuration, financial rollback on invalid
  event, timeout, cancellation, uncertain-call blocking, recovery and reconciliation
  are covered by tests.
- Local API `/api/health`, `/api/configuration`, `/api/readiness`, `/api/runs`
  returned HTTP 200. Responses were checked against configured secret values.
- Browser flow: Studio → local API → canonical SQLite → displayed three stored
  agents, no configured model profiles, eight persisted runs and a selected synthetic
  run's records. Profile absence is shown honestly, not filled with guessed models.
- The old running API could not read newer records (409) and lacked readiness (404).
  After confirming zero active runs, the identified DOXA API was restarted. The
  current UI/API flow succeeds. Local screenshot is ignored under
  `.doxa/backend-readiness.png`, not uploaded as experiment data.
- One existing Starlette/httpx TestClient deprecation warning remains.

## CI failure investigation

User-reported [Foundation checks #1](https://github.com/clarezahermetica/doxa/actions/runs/40127715613)
stopped in mypy on both backend versions: `Unused "type: ignore" comment` at the
two runtime Pydantic `TypeAdapter` aliases. Studio passed; backend tests and schema
checks were skipped after the typing failure.

The adapter constructor inputs now use an explicit dynamic-input cast while their
validated outputs retain precise types. No mypy error category was disabled.
Matrix `fail-fast:false` allows both Python versions to finish independently.
LF source attributes and UTF-8 status documentation support Windows/Linux parity.
The subsequent pushed run must be checked separately; this document does not
predeclare hosted CI success.

## Boundaries and remaining manual work

The six-system algorithms, Memory Tribunal rules and optional Moss implementation
were not changed. Only shared infrastructure metadata and the existing runtime's
provider/error boundary were extended. Existing migrations remain unchanged.

No RunPod endpoint/model/profile was invented, no cloud resource was provisioned,
no credit balance was asserted and no paid request was made. Native structured
output, tool calling, streaming, seed controls and other vendor adapters remain
unimplemented. Docker/Podman are unavailable and WSL reports it is not installed;
container enforcement acceptance tests cannot run here. DisabledSandbox's fail-closed
behavior is tested. Earlier private Moss results and the runtime database remain ignored.

Exact Windows setup, required variables, manual endpoint preparation and prerequisites
for the first separately authorized live test: [windows-setup.md](../windows-setup.md).
