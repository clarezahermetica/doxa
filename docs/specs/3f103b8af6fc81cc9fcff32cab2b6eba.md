# Core System — Epistemic Git

Source: https://app.notion.com/p/3f103b8af6fc81cc9fcff32cab2b6eba
Retrieved October 24, 2026; source last edited 2026-10-13T03:49:30.960Z.
Specification, not execution evidence.

## Purpose

Epistemic Git preserves how an agent's explicit commitments evolve instead of retaining only the final response. It is the knowledge and decision-history substrate that lets the other DOXA systems refer to specific claims, assumptions, revisions, and disagreements.

## Core objects

A <b>claim</b> is an explicit proposition asserted by an agent or extracted into a structured record. A <b>decision</b> is a consequential choice or action proposal. <b>Evidence</b> is an attributable source, tool result, test result, observation, or human input linked to a claim. <b>Dependencies</b> are explicit relationships indicating that a later claim or decision was declared to rely on an earlier item.

## Claim lifecycle

Initial statuses: Proposed, Supported, Disputed, Qualified, Retracted, Superseded. Status indicates the current DOXA record, not metaphysical truth.

## Required capabilities

- Create stable IDs for claims and decisions.
- Attribute authorship to agent, human, verifier, or system.
- Link supporting and contradicting evidence.
- Record explicit dependencies.
- Create new versions without destroying prior versions.
- Preserve disagreement between agents rather than flattening a council into one answer.
- Compare two versions or branches.
- Flag downstream dependent records when an upstream claim is invalidated or materially revised.
- Allow human or verifier notes to attach to the exact version under review.

## First-release dependency semantics

Dependencies should be explicit and conservative. DOXA may accept structured dependencies supplied by the agent or extracted by a helper model, but automatically inferred semantic dependencies should be labeled as inferred rather than certain causal explanations.

## Acceptance tests

1. Create a claim with evidence and retrieve it by ID.
2. Revise the claim and verify the original remains inspectable.
3. Attach a challenge to version 1 without retroactively rewriting version 1.
4. Add a dependent decision, invalidate the upstream claim, and surface the dependent decision for review.
5. Preserve two conflicting agent claims on separate branches.
6. Compare branch state and show which claims/evidence changed.

## Research use

Epistemic Git supports process-level evaluation, False Critic targeting, memory provenance, and branch comparison. It operationalizes the question: <b>what changed, why was it challenged, what evidence was available, and what later behavior depended on it?</b>

## Integrated ledger acceptance addendum — October 12, 2026

- Claims are contextual objects within <b>Experiments / Trajectories / Evidence</b>; the historical name “Epistemic Git” need not be visible in the primary navigation.
- Persist proposed, qualified, challenged, revised and superseded claim events with idempotent writes to the shared Experiment Ledger; never overwrite earlier versions or branch-specific disagreements.
- Every cited supporting item has a source/evidence ID, provenance type and claim-version relationship. Verifier and LLM judgments remain distinct.
- Acceptance: reconstruct claims and dependencies through CLI and [localhost](http://localhost) Studio from one canonical persisted ledger after restart.
