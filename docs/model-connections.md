# Model connections

The terminal uses the existing model catalog, immutable model profiles, provider registry,
workspace credential resolver and launch controller. A connection check does not create a
research record or authorize a later model call.

| Existing component | What changed |
| --- | --- |
| Compatible HTTP adapter | Ollama and LM Studio still use the same compatible generation route. Their read-only discovery routes differ. |
| Offline catalog and Textual model form | Local server choices come first. A listed ID can be selected before creating a profile, or an arbitrary ID entered manually. |
| Endpoint metadata checker | Reports credential availability, reachability and model listing independently. Uses provider-specific authentication, bounded responses and no redirects. |
| Codex CLI transport | Keeps the existing executable, sandbox, usage and disclosure controls. Clarifies what the CLI sign-in result establishes. |
| Windows DPAPI and legacy references | Existing values remain untouched. New references are opaque and resolve only through protected storage. |
| Profile, agent and ledger stores | Unchanged schemas and version pinning. Connection changes do not rewrite prior runs. |

Previously, the model form and metadata screen offered separate paths to registration
and discovery, and both local presets used the generic models endpoint. The same discovery
function now serves both screens. Before this change, secure entry could create a DPAPI
file but had no explicit replacement or deletion flow, and a legacy environment value could
shadow its alias. The secure reference namespace avoids that overlap without changing
legacy precedence.

## Set up a local server

1. Open **Choose model and connection**, then **Find models on a local server**.
2. Pick Ollama, LM Studio or another compatible runtime. Supply the loopback API base
   (for example, `http://127.0.0.1:11434/v1` for Ollama or
   `http://127.0.0.1:1234/v1` for LM Studio).
3. Choose **List local models (read-only)** and select an ID. You can also enter an ID
   without discovery via **Back to model**.
4. Save. If you want to enable the profile for later authorized runs, review the declared
   text capability, limits and compatibility checkbox under **Advanced**.

[Ollama lists models through GET /api/tags](https://docs.ollama.com/api/tags).
[LM Studio lists models through GET /v1/models](https://lmstudio.ai/docs/developer/openai-compat/models).
Other compatible servers use the configured base plus `/models`, if supported.
No discovery operation starts a server, loads weights, downloads a model or generates
output. Loopback says where DOXA sends its request; the operator is responsible for where
the server processes or forwards it. A model listing verifies neither its compatibility
nor the reliability of its output. For a saved profile, use the existing terminal
connection check or `doxa models --check PROFILE`. Add `--authorize-network` in the CLI
for one metadata request; without it the check stays offline.

## Use an existing CLI session

Select **Codex CLI**, then **Check installed CLIs**, or use the existing `doxa model-clis`.
The adapter uses [documented Codex commands](https://developers.openai.com/codex/cli/reference),
including `codex login status`. DOXA does not read or copy Codex authentication files.
A successful local status check reports the authentication mode. It does not prove that
the session remains valid, that an invocation will succeed, or that an account or
organization permits a particular external integration. Use the adapter only where your
plan, account policy and applicable terms allow it. API-key mode is not a subscription
session in DOXA. Launch still requires separate quota and disclosure authorization.

## Optional API key

Choose the native provider or a compatible endpoint explicitly. Expand **API credential**
and enter a key in the masked field, then save. DOXA never writes new secrets to dotenv
or changes a historical profile. The advanced existing-reference field accepts a reference,
not a key. An explicit legacy copy stores the value under a fresh managed reference in the
new profile version and leaves the original in place. Check other applications before
removing a legacy value yourself.

To rotate or remove a protected key, edit the saved profile, open **API credential**, and
confirm the operation on its saved reference. Rotation affects every profile version
sharing that reference but does not edit their records. Creating a new key via **Save**
instead makes a new reference and leaves the old one untouched. Deletion removes the
local copy, not the issuing provider's key. An explicitly configured legacy alias retains
its older environment/dotenv precedence; deleting a DPAPI copy does not delete or
disable a separate legacy source.

## Threat model and failure behavior

- Windows uses existing current-user DPAPI. The workspace stores ciphertext, not a
  recoverable portable key. macOS Keychain and Linux Secret Service are optional through
  `pip install '.[os-credentials]'`. DOXA selects the concrete built-in
  [keyring backend](https://keyring.readthedocs.io/en/latest/) for the platform; no
  autoselection, chainer or plaintext fallback. A missing dependency, locked collection
  or inaccessible service can make a credential unavailable.
- Keychain/Secret Service entries use a workspace path namespace. Only empty reference
  markers are on disk. Moving/restoring a workspace does not move vault entries.
  Reconnect explicitly at the new location. An uncertain vault write may leave a
  marker, but no plaintext file. Current-user malware, trusted Python package tampering,
  OS vault access granted to other programs, and process-memory inspection are outside
  the storage guarantee. Do not paste a key into a model ID or URL.
- Managed references never fall back to environment/dotenv. Existing aliases remain
  compatible. No secure backend is needed for keyless connections.
- Connection errors are summarized without response bodies, headers or subprocess
  output. Discovery omits IDs containing known credential values. Existing persistence,
  artifact and export guards remain in force. Backups also scan copied history and
  artifacts for known credentials before publication. These are known-secret checks,
  not a general detector for unknown, encoded or transformed secrets. Deleting a key
  cannot recall copies already held by an authorized in-flight request.
- Real DPAPI is covered on Windows with dummy keys. Keychain and Secret Service are
  exercised with fake backends only. No macOS/Linux installer is provided. Native
  providers and running local model servers were not acceptance-tested live in this pass.
