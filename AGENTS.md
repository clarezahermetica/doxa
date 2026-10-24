# DOXA implementation guidance

- Read README.md, docs/architecture.md, docs/status.md and the relevant linked source
  before changing shared contracts. The current phase is foundation, not a full release.
- Keep the modular monolith, one controller and canonical SQLite history. CLI and Studio
  must use the same persisted records. Never add a private research-system database.
- Preserve append-only history, explicit ancestry, versioned schemas, idempotent commands
  and atomic event/object commits. Do not relabel stored model text as verifier evidence.
- Keep human annotations, LLM evaluations and deterministic checks distinguishable.
- Do not enable generated-code execution without enforced container isolation and quotas.
  Keep inference opt-in and require persistent spending guards before a paid operation.
- Unknown usage/cost is null. Synthetic/replayed output must be labeled as such.
- Add tests for meaningful contract/state changes. Run pytest, Ruff, mypy and Studio build
  as appropriate; regenerate schemas and TypeScript types when contracts change.
- Do not claim the six systems, protocols or providers work until their implementations
  and acceptance checks exist. Update docs/status.md when implementing a new capability.
