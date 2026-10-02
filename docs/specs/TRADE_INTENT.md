# TradeIntent Contract V1

## Purpose

TradeIntent is the only proposal interface by which Math Mode, Strategy Mode, owner manual actions or portfolio rebalancing may request a financial action. It is not an exchange order.

## Required fields

- intent_id
- schema_version
- tenant_id
- portfolio_id
- mode
- source_type
- source_id
- strategy_version_id when applicable
- model_version_ids when applicable
- risk_profile_version_id when applicable
- capital_budget_ref
- instrument_id
- symbol
- side
- intent_type
- risk_effect: RISK_INCREASING | RISK_REDUCING | RISK_NEUTRAL
- exactly one authoritative sizing input: requested_notional OR requested_quantity
- conversion/rounding metadata where needed
- confidence when probabilistic
- expected_edge when applicable
- expected_horizon
- max_slippage
- reason_code
- evidence_refs
- market_state_ref
- portfolio_state_ref
- created_at
- expires_at
- trace_id

## Source types

math_engine, strategy_engine, owner_manual, portfolio_rebalance.

Owner manual requests still pass Hard Risk/OPA.

## Intent types

OPEN, INCREASE, REDUCE, CLOSE, REBALANCE.

## Example

    {
      "intent_id": "ti_01...",
      "schema_version": "1",
      "tenant_id": "local-owner",
      "portfolio_id": "strategy-medium",
      "mode": "STRATEGY",
      "source_type": "strategy_engine",
      "source_id": "strategy-agent",
      "strategy_version_id": "trend-breakout@17",
      "risk_profile_version_id": "medium@3",
      "capital_budget_ref": "alloc_...",
      "instrument_id": "binance:spot:BTCUSDT",
      "symbol": "BTCUSDT",
      "side": "BUY",
      "intent_type": "OPEN",
      "risk_effect": "RISK_INCREASING",
      "requested_notional": "40.00",
      "confidence": "0.84",
      "expected_edge": "0.012",
      "expected_horizon": "PT2H",
      "max_slippage": "0.0015",
      "reason_code": "TREND_REGIME_BREAKOUT",
      "evidence_refs": ["ev_..."],
      "market_state_ref": "ms_...",
      "portfolio_state_ref": "ps_...",
      "created_at": "...",
      "expires_at": "...",
      "trace_id": "..."
    }

## Validation sequence

schema -> certification -> portfolio/capital budget -> Hard Risk -> OPA -> execution plan -> final expiry/venue filters -> order submission.

Risk-reducing intents use the same auditable pipeline, but policy/risk must preserve safe emergency reduction under degraded conditions.

## Rejection/expiry

Rejected/expired intents are immutable. A retry is a new intent based on current state. An expired intent can never be submitted.

## Idempotency

intent_id is never reused. Execution creates stable client-order IDs from approved execution requests, not free-form model text.

## Evidence

Evidence must reconstruct feature/model/strategy/regime/market/portfolio/capital/risk-profile/cost context.

## Owner override

There is no direct owner bypass. Owner changes an audited configuration/policy and submits a new intent.
