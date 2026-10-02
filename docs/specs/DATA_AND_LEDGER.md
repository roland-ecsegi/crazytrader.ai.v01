# Data, Events, and Ledger Specification V1

## PostgreSQL

Use PostgreSQL for operational relational state:

- tenants
- owners
- agents
- agent permissions
- agent metadata
- portfolios
- capital allocations
- exchange accounts
- instruments
- strategies
- strategy versions
- models
- model versions
- experiments
- trade intents
- risk decisions
- policy decisions
- orders
- fills
- positions
- incidents
- certification state
- configuration versions
- audit references

## ClickHouse

Use ClickHouse for high-volume analytical and time-series data:

- ticks
- trades
- candles
- order-book snapshots/deltas as selected by implementation
- features
- signals
- predictions
- execution telemetry
- strategy telemetry
- agent observations
- backtest observations

ClickHouse is not the financial ledger.

## Object storage

Use MinIO or equivalent for:

- historical datasets;
- model artifacts;
- strategy artifacts;
- backtest outputs;
- reports;
- snapshots;
- large experiment artifacts.

## NATS JetStream

Use as the event backbone.

Critical consumers must use durable consumption and explicit idempotency.

## Internal ledger

The ledger is append-only.

Entry categories include:

- capital allocation;
- capital release;
- order reservation;
- reservation release;
- asset acquisition;
- asset disposal;
- fee;
- realized P&L;
- portfolio transfer;
- strategy allocation;
- reconciliation correction.

Corrections are compensating entries. Historical entries are not silently edited.

## Truth model

Binance is the external venue truth.

The internal ledger is the internal accounting truth.

The platform continuously reconciles the two.

## Reconciliation

Compare at minimum:

- account balances;
- open orders;
- recent orders;
- fills;
- internal reservations;
- attributed portfolio holdings.

Critical mismatch behavior:

    mismatch detected
          |
          v
    block new trading
          |
          v
    open incident
          |
          v
    reconcile venue state
          |
          v
    recover or require owner intervention

## Decimal precision

Never use binary floating point for accounting balances, notional amounts, fees, or ledger values.

Store and calculate with explicit decimal precision appropriate to venue rules.
