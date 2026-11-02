# Separate live-provider acceptance

No live inference was authorized or performed during Pass 3. Mock-provider tests establish
serialization and controller behavior, not account access or exact-model compatibility.
Use this procedure only after the operator names the provider, exact model and maximum spend.
Do not retry the historical Moss operation or alter its reservation.

1. Open the existing workspace with `doxa`. Keep the OneDrive synchronization precaution:
   avoid simultaneous synchronized writers and keep a verified backup outside the sync root.
2. Choose **Choose model and connection**. Select native OpenAI Responses, native OpenAI Chat,
   Anthropic Messages, Gemini generateContent, or an explicitly compatible endpoint. Enter the
   exact served model ID. Preserve existing credential references; saving never replaces keys.
3. Declare only known text/JSON capabilities. Configure a small output limit, sufficient input
   bytes/context, a timeout, concurrency 1 and no retries. Thinking controls require explicit
   model support. Temperature omission is available; native OpenAI always omits temperature.
   Leave network research tools disabled. No model-list request is necessary.
4. Set provider allowance and experiment run ceiling within the separately approved spend.
   A reservation ceiling is conservative local admission, not a vendor billing guarantee.
   Configure one participant and one round for the first probe; import a short local source.
   Use ordinary structured claims, not the three-round staged protocol for this first probe.
5. Open **Inspect launch preflight**. Inspect the exact profile/version/model, connection,
   permissions, call bounds and spending ceiling. Eligibility is not verified inference.
6. Only with the separate named authorization, open **Start selected run**, approve disclosure
   and paid inference, and enter the complete per-attempt upper bound. The configured run
   ceiling must not exceed the approved maximum. Keep planned calls, retries and tools within
   that amount; unknown bills retain their reservation.
7. Inspect activity, actual response/model IDs, output/finish state, usage and accounting.
   An incomplete/refused/tool-only response must not become a completed research claim.
   A timeout remains uncertain and must not be replayed. Local cancellation does not prove
   remote termination or a zero bill.
8. Export to a new `.zip` for history, configurations and verified referenced artifacts.
   Record the provider/model, timestamp, observed result and bill uncertainty. Only this
   observed result qualifies as a live-provider test.

For a complete research cycle after that separate probe: create a new experiment with
multiple independently named participants, at least two local sources, structured actions,
**Staged research cycle**, and at least three rounds. Set a sufficient call/token/time budget.
Inspect claims, criticism, responses, revisions and evaluations. Model adjudication is an
unverified judgment; source linkage and changed claims do not establish correctness.

**Create another run attempt** reuses immutable configuration without replaying old calls.
Import evidence into the new attempt. A changed criticism strategy creates a separately
versioned condition; comparisons check configuration differences and source hashes before
labeling a matched condition. Neither pairing nor matching establishes causal isolation
of stochastic model output. Text-analysis forks restore recorded history, not a live model's
hidden state, and do not automatically continue inference.

CLI equivalents remain available: `doxa run preflight RUN --json`, `doxa run start RUN`,
`doxa run watch RUN`, `doxa run cancel RUN`, `doxa run new-attempt RUN`, and
`doxa export RUN results.zip`. Flags authorizing paid/external operations are deliberately
omitted here; no copy-and-paste command should accidentally authorize an unspecified service.
