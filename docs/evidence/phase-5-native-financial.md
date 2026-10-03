# Native simulation financial adapter

L0; no Phase5 gate, elapsed account health or live certification.

NativeSimulationFill derives fill identity from immutable job and native trade ID,
retains the full validated receipt, and derives actual gross quote from native cash
and fee. It never fabricates Binance SDK provenance. Additive native journal/schema
preserves prior published journal contracts. Exact base, actual quote and quote fee
postings use the original reserved custody. Weighted-average view reads actual gross;
initial funded base lacking a cost provenance remains unknown, without invented P&L.

Original durable admission/raw result is committed before financial work. Native
settlement serializes by tenant; one full native fill, journal/event/outbox, completion
proof and UNKNOWN->RECOVERY_REQUIRED->FILLED commit together. Deferred PostgreSQL
constraints require original source/admission, matching scope/asset/portfolio, actual
cash/commission and zero per-order reservation. Standalone native journal append or
using an existing reservation as completion proof cannot commit. Source rows also
reject a correctly hashed but unbound body.

Journal or audit interruption rolls back money and state; fsynced source recovery
settles without a second engine dispatch. Attribution failure preserves source and
reservation, records an append-only incident with critical audit/notification, and
blocks new risk. Alert identity excludes poll clock, so restating unchanged unavailable
source retains all raw observations but produces one unresolved-fault alert. Successful
subsequent financial repair does not erase an incident latch; controlled resolution
requires a separate proven record. Previously prepared claims are invalidated by
unresolved native work or incidents.

Validation:69 full actual cases PASS (234.94s), final13 native cases PASS (27.88s),
17 platform/ledger PASS (7.50s);164 units/mypy51/128 schemas/scan/offline SDK/
wheel-sdist PASS. The fixture combines actual PostgreSQL,
S3/ClickHouse/OPA backbone and unmodified Nautilus engine; no signed external order.
The native engine models a single request delta from canonical custody, not independent
continuous venue account truth. BUY authority still denied at L0; modeled funding is
library evidence only. Controlled expiry/absence/incident resolution remain next.
