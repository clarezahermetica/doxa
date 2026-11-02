# S2 — fixed oracle reference (constructed integration fixture)

Each case starts with a fresh cache environment. The ordered cases are read, update,
delete. The expected table follows the independent cache-policy v1 verifier:

| Policy | read | update | delete |
| --- | --- | --- | --- |
| invalidate_all | pass | pass | pass |
| stale_on_update | pass | fail | pass |
| stale_on_delete | pass | pass | fail |

These three checks do not measure latency, throughput or correctness outside this
finite environment. A real citation to this table is not proof that a sentence
misrepresenting the table is true.
