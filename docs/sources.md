# Specification provenance

All seven requested pages were fetched successfully through the Notion connection.
Their full page bodies were available; no truncated-page or unknown-block warning was
returned. Notion marks them unverified; “authoritative” here follows the user's explicit
source selection, not a native Notion verification badge. No Notion content was modified.

| Reference | Applied to |
| --- | --- |
| [October 18 design lock](https://app.notion.com/p/3fd03b8af6fc81829c27df96c35f392c) | Consolidated invariants, six ports, four modes, $75 cap, disabled unsafe execution and honest phase labels. |
| [Research & Build HQ](https://app.notion.com/p/3f103b8af6fc819f8359c331aedc8465) | System identity, shared history, eventual release breadth and human feedback. |
| [System Architecture and Shared Contracts](https://app.notion.com/p/3f103b8af6fc816db112d46752ccd016) | Modular monolith, controller, interfaces, environment/provider boundaries. |
| [Event Model and Core Data Entities](https://app.notion.com/p/3f103b8af6fc81b6ac43f8758dfeaaeb) | UUIDs, event vocabulary, atomic records, ancestry, provenance, usage and versions. |
| [Agent Council and Operating Modes](https://app.notion.com/p/3f103b8af6fc817db1c3c81b41bb2e55) | Six roles, private/shared messages and four protocol slots. |
| [Model and Provider Adapter Strategy](https://app.notion.com/p/3f103b8af6fc8122a704cd362983deac) | Capabilities, exact assignments, unknown costs, provider slots and opt-in disclosure. |
| [Implementation Stack and Repository Plan](https://app.notion.com/p/3f103b8af6fc81aeb6dfe844bb02b1c5) | Locked stack, repository modules, migrations and test priorities. |

Source page-body snapshots are in `docs/specs/`, named by page UUID, with source URLs
and last-edit metadata. Future work should re-fetch relevant live specs before treating
snapshots as current. Hackathon logistics mentioned in the source lock were not checked
live because this task does not submit a project or advise on event eligibility/deadlines.

## Research-system source refresh - October 24, 2026

The six detailed system pages were read through the connected Notion fetch tool.
Their technical content is snapshotted locally (specifications, not execution evidence):

- [Epistemic Git](specs/3f103b8af6fc81cc9fcff32cab2b6eba.md)
- [Counterfactual Engine](specs/3f103b8af6fc8180b6c1fff62e6d66c5.md)
- [False Critic](specs/3f103b8af6fc81cb8490c3e66b2454aa.md)
- [Memory Tribunal](specs/3f103b8af6fc813dbb24d50a13717f77.md)
- [Self-Correction Gym](specs/3f103b8af6fc8109a6c6e778c8da6187.md)
- [Adaptive Reflection](specs/3f103b8af6fc81d990c5efdebd493041.md)

See the [pre-change implementation audit](research-audit.md) and
[implementation handoff](research-systems.md) for the distinction between source
requirements, current tested domain behavior and incomplete release gates.
