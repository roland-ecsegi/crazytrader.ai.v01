# TradeIntent Contract V1

## Purpose

TradeIntent is the only permitted interface by which an agent, Math Mode, or Strategy Mode may request a financial action.

It is a proposal, not an order.

## Required fields

- intent_id
- schema_version
- tenant_id
- portfolio_id
- source_type
- source_id
- strategy_version_id when applicable
- model_version_ids when applicable
- instrument_id
- symbol
- side
- intent_type
- requested_notional or requested_quantity
- confidence when produced by probabilistic systems
- expected_edge
- expected_horizon
- max_slippage
- reason_code
- evidence_refs
- created_at
- expires_at
- trace_id

## Source types

Examples:

- math_engine
- strategy_engine
- owner_manual
- portfolio_rebalance

Owner manual actions must still pass risk and policy.

## Intent types

V1 examples:

- OPEN
- INCREASE
- REDUCE
- CLOSE
- REBALANCE

## Example

    {
      "intent_id": "ti_01...",
      "schema_version": "1",
      "tenant_id": "local-owner",
      "portfolio_id": "strategy-medium",
      "source_type": "strategy_engine",
      "source_id": "strategy-agent",
      "strategy_version_id": "trend-breakout@17",
      "instrument_id": "binance:spot:BTCUSDT",
      "symbol": "BTCUSDT",
      "side": "BUY",
      "intent_type": "OPEN",
      "requested_notional": "40.00",
      "confidence": "0.84",
      "expected_edge": "0.012",
      "expected_horizon": "PT2H",
      "max_slippage": "0.0015",
      "reason_code": "TREND_REGIME_BREAKOUT",
      "evidence_refs": ["ev_..."],
      "created_at": "...",
      "expires_at": "...",
      "trace_id": "..."
    }

## Validation sequence

    TradeIntent
        |
        v
    Schema Validation
        |
        v
    Certification Validation
        |
        v
    Portfolio Validation
        |
        v
    Hard Risk Validation
        |
        v
    OPA Authorization
        |
        v
    Execution Plan
        |
        v
    Order Submission

## Rejection behavior

Rejected intents are immutable audit records.

A rejected intent is not modified and retried.

If the source still wants to trade, it must create a new intent based on current state.

## Expiry

An expired intent may never be submitted.

Execution must validate expiry again immediately before submission.

## Idempotency

intent_id must never be reused for a different proposal.

Execution generates an idempotent client_order_id derived from an approved execution request, not from free-form model text.

## Evidence

Each intent must be attributable to enough evidence to reproduce why it was proposed:

- feature snapshot;
- strategy version;
- model versions;
- market-state snapshot reference;
- portfolio-state reference;
- risk-profile version.

## Manual override rule

There is no direct owner bypass around hard risk.

The owner may change configured limits through an auditable configuration workflow, then create a new intent.
