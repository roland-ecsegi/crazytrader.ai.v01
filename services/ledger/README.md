# Canonical accounting journal

Apply migrations 001 and 003 through a separate administration identity. Internal
`LedgerStore` commits typed transactions, postings, immutable event artifact and
outbox together; a failed constraint rolls everything back. No network mutation,
agent tool, venue credential or order-submission endpoint exists here.

`commands.move` supports fixture/approved funding, allocation/transfer, order
reservation and partial release. A SELL reservation moves INVENTORY into RESERVED;
BUY reserves AVAILABLE quote funds. `account_fill` records immutable `Fill` quantity,
price, fee and order/venue-fill identity. Base/quote/third-asset fees are explicit
postings; unowned fee funds fail closed. Actual venue ingestion and mismatch/suspense
handling belong to Phase 5 reconciliation; fixture funding proves no live balance.

Every asset sums to zero separately. PostgreSQL NUMERIC(74,18) and explicit Decimal
contexts cover V1 bounds; no float or silent notional rounding is allowed. Stable
transaction/source/fill/reservation IDs reject changed content. Tenant-wide advisory
locking intentionally trades throughput for simple Enterprise Local correctness.
SQL guards also check per-asset balance, nonnegative controlled/order-reserved funds,
JSON/row/hash lineage and immutable UPDATE/DELETE/TRUNCATE behavior. Postings must
be inserted in the same SQL transaction as their journal header; a committed
transaction cannot acquire new postings later.

Corrections are full attribution-preserving compensations with original transaction
reference/reason/provenance. A transaction can be compensated once; compensating its
compensation is a new explicit correction. Partial corrections need a separately
versioned command design; they cannot use this full-reversal primitive.

`balance`, `snapshot` and `history` reconstruct operational quantities directly from
immutable journal rows. Mode/tenant attribution is explicit; there is no canonical
mutable balance cache. `attribution.positions` uses exact rational weighted-average
fill costs and an explicit 18-place half-even display policy. Third-asset fee quote
value remains UNKNOWN (`realized_pnl=null`) until sourced conversion exists. Display
valuation never grants trading/risk permission; no invented market price fills a gap.

Production scoped DB roles, secret/TLS deployment, reconciliation, permissions,
Hard Risk and OPA compose in later gates. Accounting writes do not grant trade
approval or certification. L0 remains.
