# Pass 2.7 - Universal model catalog and connection setup

October 31, 2026. Terminal configuration only; Pass 3 is not started. No inference adapter,
shared ModelProfile contract, schema, migration, research algorithm or GUI was changed.
The supplied attachment contained text only, not screenshot images. Prior v13 captures,
source inspection and fresh Textual captures were used; no review of absent images is claimed.

## Catalog and model identity

Model setup now starts with an offline searchable catalog, then asks for a connection.
Search covers developer, family, display name and identifier. It contains 21 sourced exact-ID
examples (including one retired/redirected DeepSeek alias), 12 distinct family rows, and
Other / Custom. A family row never becomes an executable model ID. Exact IDs and manually
named checkpoints remain editable without membership checks; served IDs may differ by endpoint.
Catalog inclusion means documented identity, not account access or DOXA execution support.

The bundled version-1 JSON data file records identity, source URL, checked date, kind and status.
It can be updated without rewriting the form or restricting future custom identifiers.
User notes append atomically to workspace/model-catalog.json; existing profile IDs are also
included automatically. Corrupt/unknown notes are not overwritten. Appends serialize using
the existing workspace DB lock without adding a table or experimental database. Updates
preserve user entries. Catalog notes contain descriptions/references, never credential values.

Model developer/family/checkpoint/display name are separate from the connection/provider and
hosting description. RunPod is a hosting connection; OpenAI-compatible describes a protocol,
not model authorship. Choosing a catalog model does not select a provider or claim its
availability through every listed service. Overriding its served ID marks the note user-supplied.

## Actual transports versus registration

| Connection | Current DOXA behavior |
| --- | --- |
| Native OpenAI | Existing official-origin Chat Completions adapter; NOT Responses. Temperature is omitted. |
| Native Anthropic | Existing official-origin Messages text adapter, including its own key header. |
| RunPod | Existing official vLLM OpenAI-style endpoint, not Serverless Jobs or deployment. |
| OpenRouter, Together AI, Fireworks AI, Groq | Presets for their documented compatible Chat Completions interfaces, using the existing generic adapter. No live service certification. |
| Ollama, vLLM, LM Studio, SGLang | Existing compatible-server pathway. Local examples are explicit selections; researcher-supplied served IDs/URLs remain necessary. Ollama native /api/chat is not implemented. |
| Custom | Explicit protocol and endpoint; existing trusted registered adapters are offered. Unknown IDs remain allowed. |
| Gemini native, xAI native, Cohere native, Bedrock SigV4, Vertex native, Azure native, Responses, Ollama native | Registration notes only. No runnable ModelProfile or agent assignment is created, no credential is stored, and no incompatible API is silently routed through compatibility mode. |

Adapter presence is not exact-model compatibility. Existing fixed compatible/Messages requests
include temperature/max_tokens/stream=false; some current models require parameters or behavior
that this adapter cannot express. Such model acceptance remains unverified. No thinking,
provider-native tools, schema output, caching, streaming or multimodal controls were invented.
Text/structured-output capability declarations remain unknown until explicitly configured.
Enabling a new/changed request requires explicit fixed-request compatibility confirmation.
Saving, enabling, authorization and successful inference remain distinct.

## Progressive form and workspace cleanup

- Two pages: choose/search/describe a model, then configure its connection. Model identity stays
  visible in the connection summary. All IDs remain editable via Back to model.
- Only applicable endpoint/authentication fields appear. RunPod has endpoint information;
  compatible servers have a base URL and explicit local flag; native fixed-origin providers
  hide unrelated URLs/artifacts. Repository/GGUF metadata is limited to appropriate local/
  custom registrations and never loads or executes weights. No connection defaults globally
  to loopback. Unsupported methods say registration-only before saving.
- Deployment notes and optional masked new-secret entry are collapsed. Existing references
  and secrets are preserved; replacement remains refused. Generation/resource limits have
  labels and units in Advanced. Context budgets are DOXA bounds, not advertised model capacity.
- Readiness explains selected/configured, missing credentials, unsupported transport, endpoint/
  model unverified and separate launch authorization. Save performs no discovery or inference.
  Error text identifies the rejected field/combination without exposing values or secrets.
- Save/Cancel remain fixed while fields scroll. Guide save/cancel/Escape returns retain the
  original step. F1/palette terminology now says Choose model and connection.
- Existing-workspace paths clear and disable the Create checkbox. The original nonempty/
  existing-ledger validation remains; no workspace is overwritten, initialized over or moved.

## Compatibility and preservation

Compatible profiles still use the existing deterministic controller and canonical immutable
ConfigurationStore versions. Multiple profiles may share an exact model ID with different
endpoints; agent templates and participant instances pin profile versions independently.
Editing a profile does not rewrite historical experiments or model assignments.

No profile migration was performed. Current contracts lack first-class developer/family/display/
checkpoint/hosting fields and managed-auth structures such as SigV4. Descriptions therefore
remain non-authoritative local catalog notes, not new scientific evidence, experiment fields
or an alternative engine. Exact served IDs/settings and canonical profile versions remain the
execution authority. A standalone experimental export does not suddenly gain these UI notes.
Full versioned scientific identity and unsupported native authentication need contract review
in a separately scoped pass. Optional-note writing is separate from profile persistence; if
it fails after a profile is saved, the UI reports that partial result truthfully.

## Verification and remaining Pass 3 work

Added checks cover catalog search/selection, custom IDs and preserved entries, concurrent
metadata appends and corruption refusal, three-size forms and conditional fields, missing
credentials and unsupported transports, invalid protocol/service combinations, same weights
on different deployments, same-role participants pinned to different profiles, historical
version immutability, guide return, offline HTTP prohibition and existing-workspace protection.
The earlier guide tests now wait for composed controls to mount instead of racing screen
activation; all substantive navigation assertions remain.

Fresh headless SVGs at 80x24, 120x40, 160x50 are under .doxa/pass27-ui-acceptance/:
catalog, native-openai, unsupported-gemini, custom-local, return-after-cancel, return-after-save.
Visible guidance labels have no horizontal overflow; fixed Save/Cancel are visible. All
captured configuration paths record zero model calls. These are not novice/Windows Terminal
or clean-machine acceptance. Final full-suite and packaged results are appended below.

Pass 3 remains: separately authorized live readiness tests; provider/model-specific request
parameters and any genuinely new transports if approved; schema-reviewed canonical identity/
managed-auth metadata; existing broader research gaps. No automatic model-list discovery,
weight downloads, deployment, paid calls, Moss/RunPod requests or experimental retries occur.
The old Moss hold remains reserved/uncertain. Existing OneDrive and manual-acceptance limits
remain. All previous reports and v13 fallback artifacts are preserved.

## Files changed

src/doxa/cli/model_catalog.json and model_catalog.py provide sourced data, search, append-only
notes and connection descriptions; model_setup.py implements the conditional terminal form.
operations.py keeps its ModelScreen import compatible while retaining existing import/start
operations. workspace_screen.py protects the creation checkbox. reference.py updates shared
terminology. DOXA-Terminal.spec bundles the catalog data. tests/test_pass27_models.py adds
coverage; test_terminal_first.py selects an explicit connection; test_pass26_terminal.py waits
for mounted controls. docs/status.md, this report, scripts/build_terminal.ps1 and Open DOXA
Terminal.cmd record the verified version. No previous reports or GUI sources were changed.

## Official catalog sources (checked October 31, 2026)

- [OpenAI - GPT](https://developers.openai.com/api/docs/models)
- [Anthropic - Claude](https://platform.claude.com/docs/en/models/overview)
- [Google - Gemini](https://ai.google.dev/gemini-api/docs/models)
- [xAI - Grok](https://docs.x.ai/developers/models)
- [DeepSeek - DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/)
- [Alibaba - Qwen](https://huggingface.co/Qwen/Qwen3-32B)
- [Meta - Llama](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)
- [Mistral AI - Mistral](https://docs.mistral.ai/models/mistral-large-4-0)
- [Cohere - Command](https://docs.cohere.com/docs/models)
- [Moonshot AI - Kimi](https://platform.kimi.ai/docs/guide/kimi-k3-1-pro-quickstart)
- [Z.ai - GLM](https://docs.z.ai/guides/llm/glm-5.3)
- [MiniMax - MiniMax](https://platform.minimax.io/docs/guides/models-intro)
- [OpenAI - gpt-oss](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)

Connection evidence: [OpenRouter](https://openrouter.ai/docs/api-reference/overview),
[Together](https://docs.together.ai/docs/openai-api-compatibility),
[Fireworks](https://docs.fireworks.ai/tools-sdks/openai-compatibility),
[Groq](https://console.groq.com/docs/openai), [Ollama](https://docs.ollama.com/openai),
[vLLM](https://docs.vllm.ai/en/latest/serving/online_serving/),
[LM Studio](https://lmstudio.ai/docs/developer/openai-compat),
[SGLang](https://docs.sglang.ai/basic_usage/openai_api.html).
These document interface shapes, not observed DOXA service execution.

## Final verification and artifact

- **262 tests pass**, one pre-existing Starlette/httpx TestClient deprecation warning;
  final run 527.08 seconds. Ruff passes; strict mypy passes **84 source files**.
  Nine new acceptance cases include the three form sizes. The final assignment case verifies
  shared weights on distinct endpoints AND same-role agents with different actual model IDs,
  while retaining the earlier pinned experiment unchanged.
- Captures show no horizontally overflowing visible guidance labels at 80x24, visible fixed
  Save/Cancel controls and return to the original step after save/cancel at every tested size.
- Frozen v14 in PowerShell ConPTY at 80x24 searched the bundled catalog and selected a
  sourced model. Cancel returned to Research setup step 2. It reopened, accepted a custom
  ID, selected the local Ollama compatible connection, saved a disabled profile, returned
  to the same guide, reopened/canceled with Escape, and exited with code 0.
- Independent fixture inspection confirms exact model ID packaged-custom-model-v14, a
  local compatible adapter, no authentication, disabled status, and no event/record/
  reservation/operation rows. This does not verify any local server or model execution.
- All nine packaged exports match direct-controller records. One export exceeded the first
  60-second harness limit; completed files were verified without overwriting and missing
  files completed under a bounded 180-second retry limit. Cold-start/export timing needs
  manual acceptance under ordinary machine/synchronization load.
- Original root event/record/configuration/accounting hashes remain unchanged: **223 events,
  291 records**. .env, encrypted credentials, README and workspace preferences are preserved.
  The startup-help file differs from the older imported Pass 2.6 hash, but its last write
  was 16:44, before the 16:56 Pass 2.7 request. Its current setting (show help, step 8) was
  retained without rewriting. Timestamp evidence and the old baseline remain private.
  The historical $1 Moss reservation stays reserved/uncertain, billing unknown.
- All 138 packaged files (including catalog JSON) and 191 publishable project files were
  scanned for configured secrets: zero findings. No workspace, .env, credentials, history,
  private notes/captures, node_modules, Studio or WebView is bundled. v13 retains its exact
  fallback ZIP hash and executable folder. The launcher now targets v14.

[Catalog](../../.doxa/pass27-ui-acceptance/catalog-80x24.svg) ·
[Native connection](../../.doxa/pass27-ui-acceptance/native-openai-80x24.svg) ·
[Unsupported native transport](../../.doxa/pass27-ui-acceptance/unsupported-gemini-80x24.svg) ·
[Custom local setup](../../.doxa/pass27-ui-acceptance/custom-local-80x24.svg) ·
[Return after Save](../../.doxa/pass27-ui-acceptance/return-after-save-80x24.svg).
Packaged records: .doxa/pass27-packaged-navigation.json and pass27-packaged-config.json.
Manual novice, Windows Terminal, clean-machine and cold-start acceptance remain unverified.

Artifact: dist/DOXA-Terminal-Windows.zip (v14, top-level DOXA folder).
Size: 35,823,591 bytes.
SHA-256: 2080cdf50cce29febbf05efdefb7249fec170e09902a466b05282ac10ccb9b5d
Executable: dist/DOXA-Terminal-v14/DOXA/DOXA.exe.
Only requested official-documentation research occurred. No model inference/discovery API,
Moss/RunPod service request, paid call, deployment, signing or GitHub push was performed.
Stop after Pass 2.7; Pass 3 requires a separate instruction.
