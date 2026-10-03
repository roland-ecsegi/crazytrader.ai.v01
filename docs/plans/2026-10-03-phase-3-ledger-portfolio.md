# Phase 3 ExecPlan — Append-only ledger and portfolio primitives

## Goal
Build canonical PostgreSQL double-entry, per-asset ledger history, reservations,
capital transfers and portfolio attribution. Prove duplicate delivery cannot
increase balances twice, concurrent reservations cannot overspend, corrections
are compensating entries, and all balances reconstruct from immutable history.

## Non-goals
No exchange/order submission, risk permission bypass, live funding, autonomous
capital growth or valuation from untrusted market/LLM text. No ClickHouse financial
ledger. No invented mark-to-market or certification advancement.

## Architecture context
AGENTS financial invariants; DATA_AND_LEDGER; DOMAIN_MODEL; CAPITAL_GROWTH;
EXECUTION_AND_RECONCILIATION; SERVICE_CONTRACTS ledger/portfolio boundaries.
Foundation: existing locked psycopg/PostgreSQL/event outbox/audit infrastructure.
Financial domain rules are product semantics, not a replacement for infrastructure.

## Current state
Phase 2 verified read-only data clients, exact decimal market contracts, deterministic
freshness/gap/depth alignment, immutable source/record manifests and analytical
projection. Phase 1 event/outbox/audit backbone is canonical. L0 remains. No ledger
transaction/posting persistence or accounting reservation exists yet.

## Proposed design
Immutable typed LedgerTransaction V1 with bounded postings, per-posting asset,
portfolio/account attribution, nonzero signed decimal amount and stable posting ID.
Every transaction balances separately for each asset; cross-asset trade postings
never claim USD/BTC amounts directly sum together. Transaction includes tenant,
type, source event, actor/provenance, reason, UTC timestamp, order/fill references
where relevant and correction reference for compensating entries.

Use PostgreSQL exact NUMERIC with bounds covering the contracts' 38-digit and
18-scale/positive-exponent range. Arithmetic uses explicit ample Decimal context,
never ambient 28-digit rounding. Append transactions/postings/event identity in
one database transaction, with immutable-content collision rejection. Enforce
balance and immutable history at SQL boundary too. Replay stable transaction/source
IDs is idempotent; changed content is denied. Lock relevant tenant/account/asset
keys in a consistent order before checking funds and posting.

Portfolio registry preserves immutable mode/tenant attribution. Cash/inventory
and reservation accounts are separately reconstructable. Transfers and reservation
release are zero-sum entries; cash/reserved accounts cannot become negative. Fill
and fee semantics have independent immutable venue/source IDs and accounting
provenance; valued P&L needs explicit valuation references rather than fabricated
prices. Reconciliation corrections must identify prior transaction and reason.
No balance cache is canonical. Derived views sum postings and isolate tenants and
Math/Strategy/Reserve portfolios. No public endpoint mutates accounting in this phase.

## Files and ownership
packages/contracts ledger payload/schema; packages/ledger domain accounting/store;
services/ledger and services/portfolio-engine runtime documentation;
infra/migrations/003_ledger.sql; tests/ledger real PostgreSQL/concurrency tests;
schema exporter/toolchain package/Docker inclusion; program/evidence documents.

## Dependencies and licensing
Reuse PostgreSQL17.6/psycopg3.2.12 already adopted; Decimal/Pydantic stdlib/root
locked contracts. No new financial engine or infrastructure dependency.
Supply-chain/production restricted DB roles remain Phase 14; do not claim clearance.

## Failure modes
Duplicate source delivery, changed-ID content, partial database failure, corrupt
balance/unbalanced transaction, insufficient funds, concurrent overspend, tenant or
portfolio ownership mismatch, duplicate fill/fee, restart/replay, compensation
mistakes and precision overflow. All fail closed/rollback; corrections never mutate
history. Risk-reduction release is accounting restoration, not new allocation.

## Security and financial-risk impact
Below financial accounting boundary; independent of AI and market availability.
Actor/source provenance required. No live secrets, SDK or agent tool exposure.
Only internal typed authorized commands in this phase; Hard Risk/OPA/execution
will compose authority checks later, never treat a ledger entry as trading approval.

## Data/event migrations
Additive V1 ledger/portfolio tables, exact amounts, unique transaction/source IDs,
append-only triggers and per-asset balancing safeguards. Atomic outbox event
integration must preserve existing HealthChange/market payloads. Replay must be
idempotent. Corrections retain references to original history; no destructive reset.

## Implementation steps
- [x] Read Phase 3 specification and define accounting boundary.
- [x] Implement and export immutable balanced transaction/posting contracts.
- [x] Add exact SQL journal, provenance, idempotency and nonnegative-fund controls.
- [x] Implement portfolio registration, allocation/reservation/release primitives.
- [x] Prove history reconstruction, fill/fee attribution, corrections and concurrency.
- [x] Adversarial self-review, repair, full checks, durable publication.
- [x] Continue to mandatory independent pre-T012 Hard Risk architecture/security review.

## Test plan
make check/integration; real PostgreSQL tests for per-asset balance enforcement,
UPDATE/DELETE/TRUNCATE denial, all-or-nothing rollback, duplicate/changed source IDs,
tenant/mode isolation, concurrent reservation overspend, partial release, compensating
corrections, high precision and cold-restart reconstruction. Negative tests must
exercise database constraints directly as well as typed command validation.

## Acceptance criteria
Ledger reconstructed balances equal immutable history, replay changes no balances,
concurrent commands cannot overspend, corrections are append-only, and supported
capital/reservation/attribution operations pass real PostgreSQL tests. No float,
mutable historical amount or order/credential path. L0 remains.

## Rollback/recovery
Stop writers, preserve journal, roll back reader/command versions. Apply explicit
compensating transactions for accounting corrections with provenance. Rebuild
projections from immutable postings. Never erase real journal history.

## Resume checkpoint
Branch codex/enterprise-local-autonomous. Publishing Phase3 from parent
866efded6d3d5e4778d2f17a1b2f0bc446bb7a5d. Local gate PASS: make check/integration
(73 unit/contract tests plus subsequent unchecked-copy regression PASS =74 total;
17 actual platform/ledger tests, 2 market tests), strict mypy23 modules, 46 schemas,
source scan, SDK offline check and wheel/sdist PASS. Next exact action: active
Phase4 ExecPlan, pre-T012 review recorded in docs/evidence/reviews/2026-10-03-pre-T012.md;
implement typed limits/context/classification negatives. No current external blocker;
future live authority conflict recorded but independent engineering continues.
Usage active. Implementation committed at this checkpoint; no hidden VM-only state.

## Progress log
2026-10-03: Prepared ledger design while final Phase 2 verification runs.

## Decisions
Asset amounts balance separately; valuation does not merge currencies. Exact SQL
journal is canonical; ClickHouse and mutable balance caches confer no accounting
truth. Explicit Decimal context must cover full contract precision. Portfolio
attribution and correction provenance are mandatory, including transfers.

## Completion summary
PASS. Immutable per-asset balanced journal, portfolio registry/snapshots, order
reservations/partial releases, allocation/transfers, source/fill identity, fees,
full compensation and cold reconstruction. SQL prevents unbalanced/negative/late
postings, repeated corrections and body/hash/row mismatch; journal/audit/outbox
are atomic. Exact rational weighted-average attribution has explicit display policy
and unvalued third-fee P&L remains unknown. No trading authority, credentials or
certification gained. Actual venue mismatch/suspense handling composes in Phase5;
scoped SQL roles remain security gate. Continue Phase4 review/implementation.

2026-10-03: Complete gate/self-review repaired SQL placeholder binding, ambient
Decimal negation, SELL reservation custody, third-asset fee attribution, late
posting extension, duplicate compensation, journal body/hash/row divergence and
unchecked Pydantic model-copy bypass. No mutable balance cache or fabricated P&L.
