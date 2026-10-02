# TradeIntent Contract V1

TradeIntent is the sole proposal interface for Math Mode, Strategy Mode, owner manual requests and rebalancing. It is not an exchange order.

Required fields:
- intent_id/schema_version;
- tenant_id/portfolio_id;
- mode;
- source_type/source_id;
- strategy_version_id/model_version_ids/risk_profile_version_id where applicable;
- capital_budget_ref;
- instrument_id/symbol;
- side/intent_type;
- risk_effect: RISK_INCREASING | RISK_REDUCING | RISK_NEUTRAL;
- exactly one authoritative sizing expression (requested_notional or requested_quantity) with explicit conversion metadata when needed;
- confidence/expected_edge when applicable;
- expected_horizon/max_slippage/reason_code/evidence_refs;
- market_state_ref/portfolio_state_ref;
- created_at/expires_at/trace_id.

Intent types: OPEN, INCREASE, REDUCE, CLOSE, REBALANCE.

Validation: schema -> certification -> portfolio/capital budget -> Hard Risk -> OPA -> execution plan -> final expiry/venue-rule validation -> order.

Risk-reducing intents remain auditable but policy/risk must preserve safe emergency reduction under degraded conditions.

Rejected/expired intents are immutable. Retry means a new intent. intent_id is never reused. Execution creates stable client-order IDs from approved execution requests, never free-form model text.

Evidence must reconstruct feature/model/strategy/regime/market/portfolio/capital/risk-profile/cost context.

Owner cannot bypass hard risk; owner changes audited config/policy then creates a new intent.
