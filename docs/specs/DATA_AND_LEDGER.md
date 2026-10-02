# Data, Events, and Ledger Specification V1

PostgreSQL: operational/domain state.
ClickHouse: high-volume market/features/signals/predictions/execution/strategy/agent/backtest telemetry; never the financial ledger.
Object storage: versioned datasets/artifacts/reports/snapshots.
NATS JetStream: durable event/replay; financial consumers assume at-least-once delivery and implement idempotency.

## Ledger

Append-only transactions/postings sufficient to reconstruct capital allocation/release, reservations, asset acquisition/disposal, fees, realized P&L, portfolio/strategy transfers and reconciliation corrections.

Historical entries are never silently edited. Corrections are compensating transactions with reason/provenance. Tests must prove internal balances can be reconstructed from ledger history.

Binance is external venue truth; ledger is internal accounting truth. Reconcile balances, open/recent orders, fills, reservations and attributed holdings.

Critical mismatch blocks **new risk**, opens an incident and starts reconciliation while preserving safe cancellation/risk reduction.

Never use binary float for accounting/notional/fee/price-quantity conversion. Respect venue precision/min-notional filters explicitly.
