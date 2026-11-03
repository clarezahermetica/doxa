# Supported-provider matrix

This describes the current source implementation. A transport implementation and mocked
contract test do not verify an account, credits, endpoint, exact model or provider-wide support.
Provider registration and mocked tests do not perform live acceptance.

| Connection | Implemented pathway | Verification / limitations |
| --- | --- | --- |
| OpenAI native | Explicit official-origin Chat Completions or Responses | Mock HTTP serialization, blocks, usage, finish/errors and cancellation. Exact live model/settings unverified. Temperature omitted; reasoning must be explicitly declared/configured. |
| Anthropic native | Official-origin Messages with its key/version headers | Mock text/thinking/tool blocks, stop reason, usage and thinking configuration. Exact live compatibility unverified. |
| Gemini native | Official generateContent contents/parts/system instruction | Mock generation/thinking settings, usage, stop/block state. Exact live compatibility unverified. |
| Arbitrary OpenAI-compatible server | Explicit URL, served model ID, authentication reference and compatible Chat format | Mock contract coverage. Exact server compatibility unverified. Supports explicit unbilled loopback configuration; no paid API key is required for a local no-auth server. |
| RunPod | Existing vLLM OpenAI-style endpoint | Uses the tested compatible wire boundary and official endpoint validation. Not Serverless Jobs, deployment, weight provisioning or an observed live test. |
| OpenRouter / Together / Fireworks / Groq | Compatible endpoint presets | No additional native adapter or service-wide certification. The chosen endpoint/model must accept the configured request format. |
| Ollama / vLLM / LM Studio / SGLang | Explicit OpenAI-compatible server configuration | Native Ollama protocol and model loading are not implemented. No model server/weights are downloaded or launched automatically. |
| Cohere / Bedrock / Vertex / Azure native / other unsupported catalog protocols | Descriptive registration only unless a separately installed trusted adapter exists | A catalog entry does not make an executable adapter or compatible model assignment. |
| Moss | Optional research/memory retrieval service, not a language model | Mocked eligibility/cache boundaries. Live retrieval and remote synchronization remain unverified. |

Model IDs are open-ended; there is no model-family whitelist. Compatibility depends on declared
capabilities, the adapter and the exact request. Native function requests are preserved at the
wire boundary, but automatic native tool-result conversations are unavailable. Prompted web tools
remain separately permission/authorization gated. Streaming, multimodal inference, embeddings,
GGUF execution and unrestricted generated code remain unavailable.

No automatic substitution, fixture fallback or replay is allowed for an uncertain paid call.
Unknown usage/charges remain unknown. See [separate live acceptance](live-acceptance.md)
for the named-provider/model/spend approval required before a real probe.

## Wire-level verification

All combinations below are **mock verified only**, not live verified. Arbitrary saved
profiles remain configured/unverified; catalog-only protocols remain registration only.
No credential, exact model, hosted deployment or billing integration was certified.

| Adapter | Authentication and request | Output and operational limits |
| --- | --- | --- |
| Native OpenAI Chat | Fixed official HTTPS origin, Bearer reference, `store=false`, `max_completion_tokens`; temperature omitted | Chat text/usage/tool-request parsing. Model-specific reasoning parameter support is not inferred. |
| Native OpenAI Responses | Explicit `/responses`, Bearer reference, `max_output_tokens`, declared reasoning and optional schema | Preserved text/refusal/function blocks and usage. Incomplete status blocks completion; no automatic continuation. |
| Native Anthropic Messages | Fixed official HTTPS origin, `x-api-key`, version header, system separate from messages, `max_tokens`; declared thinking | `max_tokens`, `pause_turn`, and `model_context_window_exceeded` remain incomplete. Tool requests are retained; no automatic tool-result loop. |
| Native Gemini generateContent | Fixed official HTTPS origin, `x-goog-api-key`, contents/parts/systemInstruction, explicit generation/thinking controls | `MAX_TOKENS` and `CONTINUATION` remain incomplete. Candidate blocking/refusal and unknown usage remain distinct. |
| Compatible/loopback/RunPod vLLM | Chat-style explicit endpoint/model/authentication; local no-auth requires loopback; remote requests retain spending/disclosure gates | Compatibility belongs to the exact server/model/settings. Not native Ollama, RunPod Jobs, model provisioning or weight execution. |

The transport bounds response bytes, disables environment proxy inheritance and redirects,
and uses the smaller request/profile timeout. Cancellation cancels the local wait; it cannot
establish remote termination or a final bill. Error text suppresses raw responses. Dispatch
and reservations precede remote work; ambiguous outcomes retain holds. Native tool requests
cannot silently become completed research claims. Prompts and declared context limits do
not establish actual context-window or structured-output compatibility for an unknown model.

Protocol references consulted during implementation:

- [OpenAI Chat request contract](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
- [OpenAI Responses request contract](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
- [Anthropic stop reasons](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons).
- [Gemini generateContent contract](https://ai.google.dev/api/generate-content).
- [RunPod vLLM compatibility](https://docs.runpod.io/serverless/vllm/openai-compatibility).

These documents explain protocol semantics; they are not evidence of a successful DOXA
live call. Run the separately authorized acceptance procedure before promoting any exact
adapter/model/settings combination to live verified. These mocked checks do not establish
any live-verified combination; the live gate requires separate authorization.
