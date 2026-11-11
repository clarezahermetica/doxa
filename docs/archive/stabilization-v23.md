# Post-v22 stabilization (source v23-dev)

> Historical development report. Version, installation, and verification statements
> describe this pass only. Use the [current documentation](../README.md) for instructions.

This pass applies to the cumulative development checkout, not the published starter or
installed executable. It preserves the v22 live history and uses no new live inference,
Moss or RunPod requests. Nothing is committed, published, installed globally or released.

## Baseline and boundaries

Before edits, the working tree contained substantial uncommitted v21/v22 functionality.
A private ignored snapshot preserves those 191 publishable files and logical fingerprints
of three historical workspaces. Baseline: 475 passing tests, Ruff clean, strict mypy clean
on Windows and Linux; one existing Starlette/httpx deprecation warning.

The inventory contained 101 Python modules and 20,368 lines. The largest boundaries are
the shared workbench/context/runtime module, Textual client, finite task runtime, account
CLI adapter and text-research controller. Imports cross these boundaries deliberately;
lazy imports resolve controller/client cycles. Import counts alone do not establish dead
code. No compatibility layer, optional adapter, research algorithm or historical record
was deleted. README is unchanged.

After the two small shared helpers were added, a direct absolute-import graph contains
103 modules and no top-level cycles. Its 250 non-top-level import edges include lazy and
type-checking imports; this structural check does not establish dynamic reachability or
prove that a module can be deleted.

## Security findings and fixes

Ratings concern DOXA's local operator threat model, not a public multi-tenant service.
These findings do not establish that the application is completely secure.

| Finding | Severity / confidence | Reproduction and correction |
| --- | --- | --- |
| Legacy cache-task HTTP inference omitted disclosure consent | Medium / high | An isolated mock dispatched with paid consent true and disclosure false. The shared runtime now rejects before provider construction, reservation or dispatch. Local inference remains credential-free; account CLI retains separate quota/disclosure gates. |
| Metadata discovery had no cumulative deadline | Low / high | A bounded drip fixture outlived a scaled operation deadline. Discovery now has a total deadline, closes the response and returns unavailable. HTTP socket inactivity limits remain separate. |
| HTTP response caps followed automatic decompression | Low / high | A gzip fixture yielded a 4 MB decoded chunk before the 256 KiB metadata cap. Both HTTP paths now request identity encoding and reject compression before reading; one shared reader applies byte limits. Unknown remote billing remains unknown. |
| Pinned PDF parser affected by published resource defects | Low / high | Advisory metadata matched pypdf 6.21.2. Runtime and terminal lock now pin 6.21.4; extraction records the actual installed parser version. Existing bounded parser subprocess, memory/CPU caps and timeouts remain. No hostile PDF exploitation was attempted. |
| Plain CLI claims could emit terminal controls | Low / high | Source and installed Click/Colorama paths preserve or interpret controls on interactive terminals. Plain claim output now visibly escapes C0/C1 controls except newline/tab. Ledger text and JSON exports remain exact. No command execution is claimed. |

Upstream PDF references: [cross-reference resource advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-x3rh-gjgm-fmqc),
[6.21.4 security fixes](https://github.com/py-pdf/pypdf/releases/tag/6.21.4).
Only package names/versions were submitted to public advisory services; no private
research, source text or credential was submitted.

The immutable pre-remediation Codex Security report is outside the repository in the
local Codex scan store. It records the original defects, not the fixed source. Initial
finalization failed because coverage was partial; the subsequent review completed the
requested source-risk surfaces before finalization. Product source review, fixture
validation, secret-pattern scanning, generated-contract comparison and executed tests
are distinct methods; not every test line received a second independent manual audit.

## Reliability fixes

- A Skeptic is reassigned after an author actually responds. An initially accepted claim
  with no response/new material proceeds directly to the Archivist. Multiple Skeptics
  still reassess when an author response changes the exchange. Disagreement is not forced.
- Successful research outcomes are published after final evaluation and checkpoint
  creation. An injected failure at either step now records a failed outcome and preserves
  the original exception. It cannot leave a successful result or mask the error with a
  conflicting outcome idempotency key.
- The investigation outcome and terminal run state are committed in one ledger event.
  Failure to publish that event cannot leave a separate successful outcome behind.
  Previously committed claims, model calls and reservations remain intact.
- Investigation stage, selected claim and active criticism are checked before generated
  semantic records commit. Raw provider output/accounting retains its original provenance.
- Deep invalid HTTP JSON becomes an unavailable/invalid-response result instead of an
  uncaught recursion failure. Dispatched requests retain uncertain billing semantics.
- Supplemental malformed-input validation found that UTF-16 DOCX declarations bypassed
  the raw byte DTD check and expanded a harmless internal entity. A parser-level DTD
  rejection now works across XML encodings, with UTF-8/UTF-16 regressions. No external
  entity access or code execution was demonstrated; process/resource limits remain.
- Account CLI profiles return truthful metadata guidance without attempting HTTP discovery
  or demanding an API credential. Use the existing **Check installed CLIs** action.
- The web-tool enable switch resolves from the selected workspace, matching inference
  configuration. An unrelated launch directory's `.env` cannot determine this switch.
  Run, agent, disclosure, domain and quota gates still apply.

Existing callers of remote legacy `ExecuteTask` must set `authorize_external=true` as
well as `authorize_paid=true`. Neither setting is inferred from the other. No schema or
SQL migration is needed; the disclosure field already exists.

## Verification and limitations

Eight original-defect regressions failed before the fixes and passed afterward. Additional
offline checks cover exact JSON preservation, CLI discovery, malformed JSON, workspace
configuration precedence and terminal outcome publication failure. The existing suite
covers interrupted workers, unknown holds, immutable transactions, backup/restore,
artifact tampering, archive paths, offline multi-agent protocols and Textual interactions.
Final results: **493 passed** in 742.40 seconds, with the one pre-existing Starlette/httpx
warning. Ruff and strict mypy pass for Windows and Linux (103 source files); `pip check`
passes. Public schemas reproduce exactly. The final advisory check found no matches in
59 third-party packages. Ruff's extra security-rule scan has the same flags as baseline:
68 internal assertions, five subprocess cautions, one executable-path caution, one
exception-handling caution and one XML-parser caution. These are triaged source locations,
not 76 confirmed vulnerabilities. Fixed-argument subprocesses, bounded exception fallback
and parser-level DTD rejection supply relevant controls; assertions are not substitutes
for controller input validation. See also [status](../status.md).

A complete isolated offline investigation also passed archive inspection (14 files),
backup/restore and exact run-history comparison. The restored workspace contains 16
events, 27 records and 11 verified referenced artifacts, including the new combined
terminal outcome/state event. These are synthetic infrastructure checks, not research
results or evidence of live-provider compatibility.

The initial full-suite verification was intentionally superseded when the additional
DOCX encoding and equivalent-UUID spelling regressions were added. The final suite is
run afresh after those source corrections; a partial earlier run is not counted as a pass.

A subsequent full run reported 492 passes and one Getting Started mounting failure in
the 80×24 operator test. Both operator layouts passed independently. The traceback
showed a pending selector mount during test shutdown; unlike other existing terminal
tests, this driver assumed one pause completed deferred startup. It now waits for the
guide and selector to finish mounting, with a bounded failure timeout. No framework
exception is swallowed or application behavior bypassed. The full suite is rerun after
this test-driver correction, and the failed log is retained privately.

Final read-only preservation checks cover 614 events, 809 records and 199 referenced
artifacts across three existing workspaces. Configuration, operation and reservation
fingerprints and migration revisions match the before-edit snapshot exactly. Unknown
historical holds remain held. README and Git HEAD are unchanged.

## Files changed in this pass

These changes are measured against the private before-edit snapshot, not against Git
HEAD, which predates the user's cumulative v21/v22 work.

| Files | Purpose |
| --- | --- |
| `core/execution.py` | Enforce disclosure before remote cache inference. |
| `core/investigation.py`, `core/workbench.py` | Avoid redundant reassessment, validate stages before commit, delay success until finalization and publish outcome/state atomically. |
| `providers/http_limits.py`, `providers/discovery.py`, `providers/runpod.py` | Share bounded identity-body handling, add discovery deadline and safe malformed-response handling; explain CLI metadata limitations. |
| `cli/plain_text.py`, `cli/workbench.py` | Escape plain claim presentation while retaining exact stored/JSON text. |
| `core/web_tools.py` | Resolve the enable switch against the selected workspace. |
| `retrieval/documents.py` | Reject DTDs at the parser boundary and report the actual PDF parser version. |
| `pyproject.toml`, `requirements-terminal.lock` | Pin the narrowly patched PDF dependency; other dependency versions unchanged. |
| `version.py` | Identify the changed development source as v23-dev. |
| `tests/test_v22_stabilization.py` | Eighteen offline regression cases. |
| `tests/test_adapters_accounting.py`, `tests/test_backend_completion.py` | Explicit disclosure consent in six authorized mock-inference fixtures. |
| `tests/test_pass4_operator.py` | Wait for deferred guide/selector mounting before driving the operator workflow. |
| `docs/status.md`, this report | Observed results, compatibility and remaining prerequisites. |

Paths in this table are relative to `src/doxa/` unless prefixed with `tests/`, `docs/`,
or a root configuration filename. No files were deleted. The duplicated HTTP body-reading
loops were replaced by one helper; no broad subsystem rewrite or research algorithm
replacement was performed.

The installed global launcher remains its existing version. To inspect this source:

```powershell
.\.venv\Scripts\python.exe -c "from doxa.cli.main import app; app()" --version
.\.venv\Scripts\python.exe -c "from doxa.cli.main import app; app()" runtime-info --json
```

The explicit source launcher is `scripts/launch_development.ps1`; it does not replace
an installed build or alter saved workspace selection. No frozen v23 binary was produced
or accepted on a clean Windows machine in this pass.

## Before an open-ended investigation

The controller already supports multiple criticism/response/revision cycles, explicit
unresolved outcomes, immutable exchanges, source/context manifests and hard admission
limits. Model agreement remains an unverified judgment, distinct from correctness.

It is **not ready for an unlimited or automatically resumed research loop**. Required work:

1. Persist a scheduler continuation cursor, pending stage, target and accepted configuration
   before dispatch; reconcile interrupted/uncertain calls before permitting continuation.
2. Define a controller-owned safe pause state and explicit human continuation command.
   Viewer reconnection/replay is not execution resume; never replay unknown external calls.
3. Define substantive-disagreement and evidence-progress policies. Current plateau logic
   compares claim text/evidence structure; paraphrases can appear new. It is not a semantic
   progress measure. An Archivist's abstention can end a bounded run unresolved today;
   an attributed judgment can also end a run without every critic agreeing. Continuing
   while disagreement remains requires an explicit research policy, not a truth label.
4. Characterize descendant-process teardown with trusted platform fixtures. Current account
   CLI cleanup explicitly terminates its tracked immediate process; arbitrary process-tree
   containment is not established. Native tools remain disabled.
5. Specify cross-run process/concurrency and workspace disk limits. Per-run, provider and
   spending guards do not imply one global cap on all local worker processes.
6. Establish evidence-based treatment of worker diagnostics and aggregate export memory
   bounds. No concrete secret leak or export exploit was confirmed in this review.
7. Obtain fresh bounded live approval after offline verification, using this exact runtime.
   This pass adds no new live compatibility or causal research-quality evidence.

Unknown historical spending holds are retained. No automatic reconciliation, reservation
release, ledger merge, workspace relocation or credential rotation is part of this pass.
