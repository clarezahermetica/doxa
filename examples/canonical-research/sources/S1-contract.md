# S1 — finite cache contract (constructed integration fixture)

After an initial read of x=1, an update to x=2 must be visible on the next read.
After deletion, the next read must return a missing value. Repeated reads without a
mutation must return the stored value.

This fixture uses DOXA's built-in cache-policy v1 environment. Its `invalidate_all`
policy removes the affected cached key on both update and delete. `stale_on_update`
omits update invalidation; `stale_on_delete` omits delete invalidation. The policy
names are identifiers, not performance claims. No arbitrary code is executed.
