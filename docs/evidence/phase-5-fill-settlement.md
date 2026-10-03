# Phase5 canonical settlement milestone — L0

Scope: protective SIMULATION SELL using the isolated official SDK3.0/common3.2
literal-loopback fixture. No exchange credentials, testnet/live authority, complete
account reconciliation or Phase5 gate is claimed.

Canonical fill identity includes tenant/account/symbol/raw trade ID. Immutable batches
preserve SDK source JSON and their exact QUERY order proof. Financial values are
strings; normalized IDs, direction, price, quantity, fee and UTC timestamp must match
preserved source. V1 requires exact quantity*price=quoteQty; rounded actual venue quote
amounts remain unposted truth pending an additive quote-amount contract.

Tenant-serialized settlement atomically posts new fills, qualified idempotency keys,
order transition, audit events and terminal proven remainder release. Savepoint rollback
preserves original financial state while durably retaining source, suspense and a critical
incident if attribution fails. Repeated same faults across observation clocks produce one
incident; each distinct source receipt is retained. Incident latches invalidate prepared
claims and prevent healthy accounting assertions from hiding unposted exposure.

Actual local OPA/PostgreSQL/ClickHouse/S3 and signed SDK HTTP fixtures:28 tests PASS,
including six settlement tests covering partial/replay/cancel, full multi-fill settlement,
unfunded third-asset fee rollback, conflicting fee identity, incident deduplication and
terminal order-proof binding. Final raw-source tamper integration rerun:28 PASS in71.76s. Eight additional pure
contract regressions reject float coercion, wrong IDs/direction/fee/quote/time:PASS.
Repository checks:115 tests PASS plus8 new source-contract tests PASS (123 total),47 dependency tests skipped in unit invocation;
strict mypy39,90 schema files, lint/format/source scan and offline SDK checks PASS.

Remaining: authenticated cancellation submission; explicit actual quote/fee accounting,
BUY cost buffers/mixed custody; complete venue filters/currency authority; full account
orders/balances/fill reconciliation and absence proof; selected simulation integration;
complete negative/chaos review. Existing L0/L6 guard remains enforced.

Pinned platform image build and non-root UID10001 execution import PASS; wheel/sdist
PASS. Compose readiness smoke failed during local disk exhaustion, so runtime smoke
is not newly claimed. Targeted cleanup of exact task-owned build caches and unused
regenerable images restored5.7GB; final financial integration then PASS. No broad
pruning or source/durable-volume deletion.
