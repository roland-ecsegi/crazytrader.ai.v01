# Data, Events, and Ledger Specification V1

## PostgreSQL

Operational relational state:
- tenants/owners;
- agents, skills, permissions, provider configs and memory metadata;
- portfolios/capital allocations/risk profiles;
- exchange accounts/instruments;
- strategies/versions;
- models/versions;
- experiments;
- trade intents;
- risk/policy decisions;
- orders/fills/positions;
- ledger transactions/postings;
- incidents/certification/configuration versions;
- audit references.

## ClickHouse

High-volume analytical/time-series data:
- ticks/trades/candles;
- selected order-book snapshots/deltas;
- features/signals/model predictions;
- execution/strategy telemetry;
- agent observations;
- backtest/research observations.

ClickHouse is never the financial ledger.

## Object storage

Versioned:
- historical datasets;
- model/strategy artifacts;
- reports;
- backtest artifacts;
- snapshots;
- large experiment outputs.

## NATS JetStream

Durable event backbone and replay. Critical consumers assume at-least-once delivery unless explicitly stronger. Financial state mutation handlers must be idempotent.

## Ledger

The ledger is append-only and reconstructable.

Transactions/postings cover:
- capital allocation/release;
- order reservation/release;
- asset acquisition/disposal;
- fees;
- realized P&L;
- portfolio/strategy transfers;
- reconciliation corrections.

Historical entries are never edited. Corrections are compensating transactions with reason/provenance.

Tests must prove internal balance/exposure can be reconstructed from ledger history and that duplicate events cannot double-post.

## External/internal truth

Binance = external venue truth.
Ledger/domain = internal accounting/control truth.

Continuously reconcile:
- balances;
- open/recent orders;
- fills;
- reservations;
- attributed holdings;
- venue precision/filter metadata.

Critical mismatch blocks new/increased risk, opens incident and starts reconciliation while preserving authorized cancellation/risk reduction.

## Precision

No binary floats for financial/accounting values or venue quantity/price conversion. Respect exchange tick/step/min-notional rules explicitly and version venue metadata.
