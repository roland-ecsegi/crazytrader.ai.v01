# Unsent simulation expiry

L0; no Phase5 gate/certification or exchange order.

Only the current configured owner may expire an original protective SIMULATION
request. Its AUTHORIZED state must be expired and have no past dispatched/ambiguous
state, SDK observation or native receipt. Native admission alone is unsent and can
expire. SUBMITTING/UNKNOWN always retain reservation; query not-found is not absence.

One immutable original custody proof restores the whole unused INVENTORY/AVAILABLE
allocation exactly. Release, EXPIRED transition, typed expiry evidence/event/audit/
outbox commit together under tenant serialization. Deferred PostgreSQL constraints
bind original request/reservation and release, expiry clock, no dispatched history
and exact custody restoration. A standalone expiry journal release cannot commit.
Duplicate delivery returns the immutable first proof; claim versus expiry race can
produce either an unreleased dispatch claim or expired/restored custody, never both.
Audit failure rolls back money/state and permits safe idempotent expiry recovery.

Actual7 expiry cases PASS (6.10s). Contract negatives include partial release, borrowed
actor/tenant/portfolio and live request. Final36 affected cases PASS (98.62s),17 platform/ledger PASS (6.79s),169 units/
mypy53/130 schemas/scan/offline SDK/wheel-sdist PASS.
Controlled authoritative absence/retry and append-only incident resolution remain next.
