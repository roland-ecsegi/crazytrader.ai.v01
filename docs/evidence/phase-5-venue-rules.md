# Phase5 full venue-rule provenance / dispatch prerequisite — L0

Additive VenueTradingRules/VenueRuleReceipt preserve complete official-SDK unsigned
exchange-info JSON. Metadata version binds the complete symbol; source hash binds full
response; receipt binds tenant and observation. Raw source is immutable/read-back checked
before append-only PostgreSQL receipt, exact replay idempotent, conflicts/tampering deny.

MARKET checks handle ordinary and market quantity intervals/steps, min/max notional flags
and exact averaging windows, spot/order-type permission, account order limits and BUY
position limits. Zero disables only the respective exchange constraint. Unknown or changed
fields fail closed. No assumptions about unavailable account counts or five-minute prices.

Execution preparation and final single-send claim require a fresh, matching full receipt
and source proof; reservation stores receipt reference. Tenant serialization includes rule
publication. Legacy NULL references do not gain authority. Cancellation remains possible
under stale market data and accounting incidents; receipts cannot release balances.

Unsigned official SDK one-shot BTCUSDT public market-data capture in
venue-rules-public.json:11 symbol filters, quote precision8. This is source/compatibility
evidence, not continuous coverage, real financial authority or certification.

Pre-dispatch foundation verification:136 repository tests PASS (13 focused rule tests),
mypy42,98 schemas, scan/offline SDK/wheel-sdist PASS;36 actual combined service tests PASS
in118.57s. After enforcement:35 service regressions PASS; one archive fixture timestamp
collision repaired by giving the test its own tenant scope. Final enforced38 service tests PASS in120.32s, including source change before prepare
and tamper after reserve. Final136 units/mypy42/98 schemas and wheel/sdist PASS.
No Phase5 gate. Remaining: actual quote amounts, BUY fees/buffers/mixed custody, full
account reconciliation/absence proof, selected mature simulation integration and final gate.
