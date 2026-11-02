# Preregistered canonical fixture: finite cache coherence, version 1

This is an offline engineering integration fixture, not an empirical model study.
The materials and scripted participant behavior are constructed for inspection.
No inference service, web search, generated code or Moss request is needed.

## Question

Does `stale_on_update` satisfy the supplied read/update/delete coherence contract,
what bounded correction is justified, and can these materials establish which policy
is fastest? Restrict conclusions to cache-policy v1's finite oracle.

## Frozen materials

- S1 `sources/S1-contract.md`: contract and implementation scope.
- S2 `sources/S2-oracle.md`: independently checkable finite oracle reference table.
- S3 `sources/S3-memo.md`: deliberately conflicting, unverified maintainer assertion.
- S4 `sources/S4-unrelated.md`: irrelevant administrative information.

Files are imported unchanged and hashed. Source identifiers above are stable corpus labels;
the controller allocates separate actual source-record IDs, recorded in the study manifest.

## Declared controls

| Condition | Participants | Execution |
| --- | --- | --- |
| A | One Researcher | Fixed synthetic responses, three rounds |
| B | One Researcher and one Skeptic | Same researcher opening; explicit objection and response |
| C | Two Researchers, two Skeptics and one Archivist | Distinct instances; explicit criticism, responses and an adjudication |

All conditions use the same question, source bytes, offline permissions, adversarial
protocol identifier, three rounds, maximum 20 scheduled calls/turns, context/output bounds,
evaluation criteria and no model profile. The intended composition changes are declared.
Role instructions and response fixtures are pinned and exported. Shared initial researcher
assertions deliberately include an unsupported overgeneralization; criticism can lead to
a bounded revision in the scripted fixture. Scripted differences are known in advance.

**This is not a causal test of multi-agent model quality.** There is no model generation.
Role composition changes the number of scripted turns and available information. Even with
future authorized model calls, composition/token/interaction differences must be reported,
not collapsed into a claim that additional agents caused greater correctness.

## Reference hypotheses and labels, established before execution

H1: Under `CacheFixture(version="1")`, `invalidate_all` passes read/update/delete;
`stale_on_update` fails update; `stale_on_delete` fails delete. Verify these labels using
the existing independent `environments/cache_policy.py:verify` function, not participant text.

H2: A claim that all three policies satisfy the entire contract contradicts S2.
A real citation to S2 does not make that claim entailed by S2.

H3: No timing, throughput, memory or hardware measurements are supplied. A fastest-policy
claim is unsupported. Passing this finite oracle does not prove correctness for arbitrary
caches, concurrency, distributed consistency or arbitrary generated programs.

H4: The controller should preserve an opening claim, the exact targeted objection, its
author's response/revision, the source/evidence links and the bounded adjudication judgment.
Fixture adjudication is not an independent verifier verdict.

H5: Revoked or private-ineligible memory must not enter later contexts. An index result
cannot authorize itself. Research source documents are not automatically Tribunal-approved
agent memories. Demonstrate the strongest supported promotion/revocation path in the
finite-cache six-system companion, without pretending text memory has an independent oracle.

H6: Text checkpoints preserve history/configuration and support human-analysis forks;
they do not authorize model replay. The existing finite-cache companion must exercise
actual state restore, valid versus misleading criticism, memory eligibility/revocation,
objective Gym rates and bounded reflection in one complete trajectory.

## Measurements

Record claim versions/current claims, evidence-linked claims, missing evidence, objections,
responses, unresolved objections, revisions, explicit contradiction reports, adjudications,
context manifests, checkpoints/branches, known usage and unresolved usage/cost separately.

Distinguish citation presence, source existence, in-range character spans, entailment,
oracle correctness, agreement and procedural completion. No overall quality score.
Reference-label checks are explicit fixture checks; preserve nulls for unmeasured truth,
entailment, tokens, latency and billed charges. A synthetic no-call run must not manufacture
provider-reported usage. Do not sum inherited branch work as independent observations.

## Reproduction and acceptance

Use fresh, isolated workspaces. Preserve the protocol/corpus hashes before running.
Export each history with configuration and artifacts, then independently inspect ZIP hashes,
event/claim/source/agent/context/evaluation/checkpoint/ancestry identities from another
directory. Separately verify non-destructive workspace backup/restore.

Preserved-history inspection is not a claim of deterministic live model regeneration.
The full operator procedure, actual observations, limitations and any missing interactions
belong in the Pass 4 report after execution; this protocol is not a success claim.
