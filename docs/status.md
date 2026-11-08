# Current status

DOXA is an unfinished terminal-first proof of concept. The published application uses
Textual and the CLI; React Studio and the native graphical desktop are retired. The source
identifies package `0.1.0a0`, terminal build `v24`.

## Latest recorded verification

The November 7, 2026 v24 report records **514 passing tests**, one pre-existing
Starlette/httpx warning, Ruff and strict mypy checks for Windows/Linux, and unchanged
generated schemas with no SQL migration. These results predate this documentation cleanup;
they are not a fresh test run of this branch.

That report also records an internal frozen-executable offline investigation with 17 events,
zero live calls, package/hash checks and an owned Windows-console launch/quit. The operator's
existing installed command was updated to v24 with historical data/settings preserved.
This is not a published binary release, signing or clean-machine certification.

## Recorded live execution

The November 5 v22 acceptance records **24 real Codex CLI calls** across five source-backed
investigations and solo/self-correction controls. Requested settings were `gpt-6.1-sol`,
medium effort for Researchers/Skeptics and high for Archivists. The self-correction control
persisted a criticism, `qualify` response and versioned revision. Main claims were accepted
without disputed cross-agent responses. Quota/USD cost and independently resolved model/
effort remain unknown.

The controls differed in effort, calls and retrieved passages; human correctness labels
were unset. This verifies those integration paths, not causal improvement in research
quality, disputed cross-agent cycles, or every provider/model/settings combination.
Earlier failed histories and uncertain holds remain preserved.

## Capabilities and remaining limits

| Area | Current boundary |
| --- | --- |
| Experiments | Configured participants, evidence, bounded debate/investigation, immutable claims/revisions, checkpoints, comparisons and exports. Model judgments remain unverified. |
| Dispute review | Optional current-claim/reviewer follow-up criterion; abstention, plateau and resource stops can remain unresolved. No unlimited loop or durable human pause/continue cursor. |
| Evidence evaluation | Reference/artifact linkage and character-span diagnostics; these do not verify truth or entailment. Independent labels and controlled studies remain necessary for quality claims. |
| Providers | Native/compatible HTTP transports have mocked coverage; Codex CLI has the specific live observations above. Other account CLIs have detection only. See the [provider guide](providers.md). |
| Retrieval and tools | Local lexical search and optional scoped Moss snapshots; bounded approved fetch pathway. Live Moss and remote synchronization remain unverified; no production live-search adapter is configured. |
| Local models | Compatible-server connections; no automatic model loading or server provisioning. |
| Six systems | Exercised in the finite cache-policy environment; no general proposition oracle, learned reflection policy or executable generated-code repair runner. |
| Execution | Explicit caps, detached workers and inspection/replay. Cross-run resource policy, descendant containment and semantic progress criteria remain open-ended execution prerequisites. |
| Recovery | Verified history/backup inspection; no automatic replay of interrupted inference or automatic settlement of uncertain charges. |
| Modalities | No token-stream viewer, multimodal generation, embeddings or automatic native tool-result loop. |
| Distribution | Source installation and internal Windows packaging; no public binary release, signed distribution or clean-machine acceptance. |

Use the [documentation index](README.md) for current instructions. The
[development archive](archive/README.md) preserves full historical reports and verification
chronology, including failures and superseded installation observations.
