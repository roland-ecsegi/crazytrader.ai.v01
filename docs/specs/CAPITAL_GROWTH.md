# Capital Growth Engine V1

## Purpose

Allocate owner-provided capital across Math Mode, Strategy Mode, strategies and reserve without allowing a strategy/agent to unilaterally increase its own risk budget.

Inputs include owner absolute cap, per-mode budget, balances/exposure, realized/unrealized P&L, drawdown, lifecycle stage, performance quality/sample size, correlations, liquidity, volatility/regime, risk profile and certification.

Outputs are allocation proposals or deterministic allocations within pre-authorized limits.

Rules:
- owner hard cap always wins;
- research performance alone cannot unlock large live capital;
- growth requires stage-appropriate evidence;
- loss/degradation can reduce/freeze allocation automatically;
- Math and Strategy remain separately attributable;
- reserve capital is explicit;
- no martingale-style loss chasing;
- Kelly/fractional-Kelly or similar methods require validation/caps before production;
- High risk cannot exceed absolute survival/drawdown constraints.

Canary/live increases are stepwise, reversible and owner-capped. Exact amounts are configuration, not promised-return logic.
