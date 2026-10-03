# Phase5 owned cancellation milestone — L0

Internal authenticated actor supplies a typed CancellationRequest referencing the existing
TradeIntent-derived owned order. The durable execution registry builds ownership context;
current owner config/policy permission and pinned OPA authorize. Caller-selected market,
P&L/accounting health or live flags cannot grant cancellation authority. This path does not
require healthy market/accounting claims and can protect an owned order during incidents.

Tenant lock serializes config/state/duplicate claims. Full request/context/authorization
record, audit event and CANCEL_PENDING transition commit before the one SDK DELETE.
Request replay cannot send again after timeout, acceptance or process interruption.
Signed SDK traffic uses fixed dummy auth/literal loopback only; fixture validates actual
HMAC-SHA256 for POST/GET/DELETE. Cancellation receipt is immutable evidence, never a
balance release. Query+complete fill proof posts fills/fees and releases only proven
remaining custody; unposted third-asset fee retains reservation and incident.

Actual services:35 combined PostgreSQL/OPA/ClickHouse/S3/SDK tests PASS in119.44s,
including seven cancellation tests (concurrency, timeout, forged actor/revoked permission,
audit failure, partial fill race, receipt-persistence interruption, existing incident).
Repository:123 tests PASS,54 dependency tests skipped in unit run; mypy40,94 schemas,
lint/format/source scan/offline SDK checks PASS; wheel/sdist PASS.
Settlement hosted CI37124294645 PASS at5d41b448.

Fixture keeps canonical client ID after cancellation. Actual venue alias changes and
owner-local signed transport remain unadopted; no real exchange or certification claim.
Full account reconciliation, controlled absence/retry, venue filters/actual quote amount,
BUY cost buffers and selected simulation integration remain Phase5 engineering work.
