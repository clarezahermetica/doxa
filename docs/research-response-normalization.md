# Research reply normalization

Structured Council turns use one canonical reply: `{"research_action": {"operation":
"claim", ...}}`. The canonical controller commands still determine allowed operations,
required fields, author permissions, valid references, evidence visibility, and investigation
stage. The normalizer does not perform those checks or commit actions.

`research-action-normalization-v1` accepts these representations:

- The canonical JSON object, with optional surrounding JSON whitespace.
- The same object in one complete Markdown code fence, unlabeled or labeled `json`
  (case-insensitive). No text may accompany the fence.
- The same envelope with `{"research_action":{"operations":[{...}]}}` when the list
  contains exactly one action object. This can also be fenced.

It rejects malformed JSON, duplicate members at any depth, non-finite numeric values,
bare actions, extra envelope keys, and empty or multiple actions. It does not extract
JSON from prose, rewrite fields, infer an operation, select a preferred action, or grant
tool access. The existing tool path accepts an exact, separate JSON envelope and still
applies the controller's permission and quota checks. Legacy experiments explicitly
configured for unstructured replies retain their separate text path.

The prompted and native Codex formats use the same example fields and enum values.
Prompt examples still require real case-specific IDs and values. Native output schemas
are a provider-side generation aid; satisfying one is not permission to act.

Structured context labels source, history, and memory IDs separately. Only a `source_id`
actually supplied to the participant is eligible for `source_ids`. When full history
would crowd out evidence or exceed the context limit, DOXA can excerpt historical prose
while keeping the record IDs and relationships. The context manifest marks the excerpts;
the original history and the exact text sent to the provider remain inspectable.

## What the ledger records

The original provider response artifact is written before interpreting the research reply.
The exact final text used for normalization is kept there without rewriting it. A
`response_normalization` record carries its SHA-256 hash, normalizer version, context,
participant, transformations, disposition, reason code, and the model-call record ID
when available. Offline fixtures have a hash and context but no live call ID.

Accepted decisions and their research records are committed in the same event. Rejected
decisions are observations and produce no research action. A rejected action does not
retroactively turn a completed model call into a failed inference or change its usage.
If a worker stops after response capture and before validation, the response can be
inspected without assuming an action or normalization decision was committed.
The run's reason distinguishes `research_response_format`, `invalid_research_operation`,
and `provider` failures. No rejection causes another model call.

This is an additive record: older workspace history is unchanged and SQLite needs no
migration. Older executables may not be able to inspect workspaces containing the new
record type. Use the updated source or a build that includes it.

## Capture boundaries

The audit is about the provider's retained final reply, not a dump of the subprocess's
raw event stream, hidden reasoning, authentication data, or HTTP headers. Existing
transport limits and secret checks still apply. Invalid encoding, oversized or truncated
streams, and failed transports may leave only safe diagnostics; an unavailable final
reply cannot be reconstructed. A completed reply that fails formatting or action
validation remains inspectable through the original model-call artifact.
