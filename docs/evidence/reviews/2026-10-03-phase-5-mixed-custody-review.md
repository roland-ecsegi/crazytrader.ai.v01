# Independent adversarial root pass: mixed custody

Separate root review after implementation, not human/separate-model approval.
Original reserve postings are hash-checked and tenant/portfolio/order/asset bound at
release. One immutable reservation supports two sources without schema mutation.
Inventory-first consumption is explicit; release bounded by original and actual
per-order remaining custody. Compatibility reserve_account is not release authority.
Stable release identity and settlement savepoint prevent financial replay.

Negative balances, insufficient sources, excess release, invalid posting directions
and cross-portfolio allocation reject. Actual44 cases PASS. One initial concurrent
unit run timed out the bounded SDK child before any redirect wire call; unchanged
sequential checks pass. No retry or credential-forwarding behavior was added.
No blocking defect found for this bounded milestone; no Phase5 gate or BUY authority.
