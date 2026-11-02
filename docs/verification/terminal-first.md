# Terminal-first acceptance — October 25, 2026

This pass extends the existing Textual application. React Studio and desktop sources/builds
remain archived; their development is frozen. No alternate research engine or ledger was added.
The source changes are uncommitted. README remains empty.

## Demonstrated behavior

The automated terminal workflow creates a previously unknown model identifier, creates an
agent template and two instances, configures an offline experiment, imports evidence, starts
its detached synthetic worker, inspects activity and claims, submits an evidence-linked
revision, evaluates, checkpoints, forks, compares and exports the canonical history.
This is an offline demonstration, not evidence of successful external inference.

Additional acceptance covers arbitrary compatible HTTP connections with mocked transports,
multiple Skeptics sharing a model, model-generated structured criticism/responses/revisions
and Archivist adjudication, exact context manifests, capability rejection before execution,
spending-guard rejection for native providers falsely marked local, and persistent same-profile
concurrency admission across different instruction versions. Model adjudication remains an
LLM evaluation. Citation references do not establish entailment or objective correctness.

Textual interaction tests cover 80×24 layout, resizing to 120×40, long claim content, a
1,050-record history, bounded 1,000-row inspectors, and filtering an older record outside
that initial display window. Ledger reads use a background worker; closing a viewer does
not cancel the detached experiment process. A model-backed run was not performed live.

Workspace tests cover canonical selection, missing remembered paths and preservation of
original root .env resolution. Windows DPAPI entry is masked and refuses replacement of an
existing reference. Original Moss keys were neither rotated nor replaced.

## Distribution scope

The terminal has a separate PyInstaller one-folder console build, migrations and a bundled
Python runtime. No Node.js, Vite or WebView is required at end-user runtime. Application
files do not contain the workspace, credentials or research history. The project terminal
launcher explicitly selects this project's .doxa workspace; portable users can choose an
existing workspace through W and inspect its canonical location in Settings/help.

PowerShell ConPTY startup, palette navigation and clean exit are separate from a manual
Windows Terminal GUI session. No clean-machine, signing, installer, antivirus certification,
other Windows-version or manual Windows Terminal usability claim is made.

## Remaining work and precise next steps

1. Run a separately authorized inference against one configured local compatible runtime;
   then separately verify selected remote providers/Moss with explicit applicable allowances.
   Mocked transports verify dispatch behavior, not actual service availability or model quality.
2. Add a reviewed reconciliation workflow for ambiguous local inference: started/uncertain
   calls retain their persistent admission hold. They must not be blindly replayed or reset.
3. Complete model execution on text-analysis forks. Current forks support immutable human
   analysis and comparison; they do not resume model inference or replay paid actions.
4. Add source entailment/argument-quality evaluation and independent checks where practical.
   Current coverage and response rates are accounting metrics, not truth measurements.
5. Validate the portable build manually in Windows Terminal/PowerShell on a clean machine,
   including extended runs, reconnects, ordinary laptop sizing and upgrade data retention.
6. Extend corpus selection across experiments and support additional runtimes/modalities only
   behind tested adapters. Images, embeddings, native function calling and token streaming
   are currently unsupported by text execution. Unknown capabilities stay unknown.

GGUF import records an existing file's header/version/hash/path, without loading tensors,
executing model code, downloading weights or proving sufficient hardware. Repository IDs
are registration metadata. Ollama/llama.cpp execution requires a separately installed
compatible server. LiteLLM's compatible proxy can be configured as an endpoint; a direct
LiteLLM SDK adapter is not implemented. Search requires a chosen provider and separate
network authorization; no live research search was performed.

No deployment, GitHub push, paid inference, actual endpoint discovery, Moss session, or
research web-tool call was performed for this pass. Existing GUI changes predating the
terminal correction were preserved; generated TypeScript compatibility types were updated.

## Final source checks

- pytest: 202 passed in 660.86 seconds. One existing Starlette/httpx TestClient
  deprecation warning; no test failures.
- Ruff: all checks passed.
- Strict mypy: no issues in 75 source files.
- Shared JSON/OpenAPI schemas and generated Studio TypeScript types were regenerated;
  the retained Studio production build passed compatibility checks without UI development.

## Final portable binary acceptance

Final folder: dist/DOXA-Terminal-v8/DOXA. Archive: dist/DOXA-Terminal-Windows.zip.
The one-folder executable launched with no command into the existing Textual workbench
under PowerShell ConPTY, displayed the existing completed synthetic experiment, its
persisted activity and operational command palette, and exited cleanly through Ctrl+Q.
The metadata discovery palette action was not executed. No configuration was submitted.

Frozen CLI doctor/models/agents/runs passed against the existing test workspace. Missing
workspace doctor exited 2 with a useful instruction and did not initialize a new directory.
Frozen DOCX parsing returned the expected fixture text. Migration 0003 is bundled.
No Studio/WebView, .env or ledger.sqlite3 files are bundled. Workspace data stays outside
installation files and was readable after replacement with this newer executable.

The original configured secret values were checked without printing them: 137 packaged
files and 171 publishable source files, zero findings. No .env values enter this report.
ZIP size: 35,731,300 bytes; 137 files.
SHA-256: 37b78976cd807b1414973417785f578759eb5a9dd0e2b8fca1faca7f5c7d1e9c.
Private machine-readable metadata: .doxa/terminal-package-verification.json.

PyInstaller warned about optional tzdata, pysqlite2 and MySQLdb imports. DOXA's tested
SQLite/UTC paths use the bundled standard library; those optional integrations were not
claimed or tested. Windows/OneDrive blocked cleanup of an earlier output folder, so this
verified v8 build uses a fresh folder and preserves prior artifacts. The ZIP is unsigned.

Final display correction: evaluations and structured research messages now use labeled
readable fields, with unknown metrics explicitly unknown. After this isolated presentation
change, 25 terminal/CLI tests pass (including the full interaction workflow and new readable
summary regression); Ruff and strict mypy pass again. The earlier full suite was 202 tests.
The final v8 executable displayed turns: 8.0 and objective correctness: unknown, opened
the command palette and exited cleanly. Frozen CLI/parser/secret scans were repeated on v8.
