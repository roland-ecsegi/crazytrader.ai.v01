# Phase5 mixed custody milestone

Protective SIMULATION SELL reservation now combines INVENTORY and AVAILABLE in a
single immutable balanced journal transaction. INVENTORY is consumed first; source
postings are durable allocation proof. The existing reserve_account column remains
a compatibility hint and never authorizes financial release.

Proven terminal cancellation loads/hash-checks original reservation, binds tenant,
portfolio, order and asset, derives consumed quantity from actual per-order RESERVED
postings and restores only unused source amounts. Atomic settlement/release/state and
stable identities retain replay protection. No new permission or schema migration.

44 actual combined PostgreSQL/ClickHouse/S3/OPA/official-SDK cases PASS (174.04s).
The mixed-custody case reserves0.06 INVENTORY+0.04 AVAILABLE, fills0.04, cancels and
restores0.02 INVENTORY+0.04 AVAILABLE exactly, no duplicate reservation or release.
Unit regressions cover consumption across source boundary, insufficient total,
excess release and cross-portfolio original proof. make check/build evidence updated
with checkpoint. Certification L0; BUY fee/slippage buffers, account reconciliation,
selected simulation and Phase5 gate remain pending.
