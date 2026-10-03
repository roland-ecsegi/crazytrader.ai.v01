# Phase5 actual quote accounting milestone

Certification remains L0. No Phase5 gate, BUY execution permission, live order,
full-account reconciliation or elapsed certification is claimed.

Additive QuoteFillIdentity, VenueQuoteFill, VenueQuoteFillBatch and
VenueFillLedgerTransaction contracts preserve published V1 schemas. Official SDK
my_trades rows retain actual quoteQty, strict financial strings, scoped identity,
fee/time/raw provenance and the original tenant-bound venue precision receipt.
Actual cash uses quoteQty; product difference must be less than one quote quantum.
Quote fees on BUY debit the already reserved quote account. Zero actual quote
amounts do not manufacture cash or zero postings. Cost attribution reads mixed
legacy/new journal history. The existing journal schema and database money guards
remain authoritative.

Source-first settlement binds the original reservation receipt, complete query
proof and cumulative base quantity. Semantic comparison allows an identical legacy
fill to replay through the new format without rewriting history or double posting.
Changed financial facts remain incidents. Missing/malformed/out-of-tolerance quote
truth keeps funds reserved and records an unproven-batch incident.

Validation: 43 actual PostgreSQL/ClickHouse/S3/OPA/SDK combined cases PASS in146.04s;
17 actual PostgreSQL/NATS platform/ledger cases PASS in6.06s; make check PASS:
142 unit/contract tests, strict mypy43 modules,106 schema files, source scan and
offline SDK checks. Wheel/sdist build verified separately. Three new actual SDK
settlement cases cover rounded quote cash, legacy/new replay and unsafe quote delta.
Two actual journal cases cover BUY quote fees/reconstruction and borrowed-tenant
precision proof. Six unit cases cover quote delta, zero cash and strict raw strings.

Shared integration fixtures now tolerate an already-created bucket and scope archive
counts to their own tenant; the previously order-dependent assertions caused harness
failures, not financial failures. Final43 cases pass together.

Remaining: BUY permission/certification and sourced fee/slippage buffers; mixed
custody reservation/release; balance/open/recent-order account reconciliation;
known venue cancellation aliases; incident resolution; selected simulation adapter.
Individual trade quote truth is now explicit. Aggregate cummulativeQuoteQty/account
balance agreement is not yet implemented and cannot certify healthy accounts.
