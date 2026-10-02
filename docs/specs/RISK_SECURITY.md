# Risk and Security Specification V1

## Hard Risk Engine

The Hard Risk Engine is deterministic and independent from the Risk Analyst Agent.

## Risk inputs

- TradeIntent
- portfolio state
- current allocation
- current drawdown
- realized daily P&L
- total daily P&L
- open orders
- market liquidity
- spread
- volatility
- market-data health
- exchange health
- reconciliation health
- certification level
- selected risk profile
- owner absolute limits

## Hard-rule categories

- maximum portfolio capital
- maximum mode capital
- maximum strategy exposure
- maximum symbol exposure
- maximum total exposure
- maximum concurrent positions
- maximum order notional
- maximum order frequency
- realized daily-loss limit
- total daily-loss limit
- maximum drawdown
- minimum liquidity
- maximum spread
- maximum slippage
- stale-data rejection
- exchange-health rejection
- reconciliation-health rejection

## Risk profiles

Low, Medium, and High may alter:

- position sizing;
- signal threshold;
- drawdown budget within owner maximum;
- strategy eligibility;
- concentration;
- volatility tolerance;
- concurrent-position count.

They may never alter:

- withdrawal prohibition;
- global kill switch;
- certification requirement;
- owner absolute limits;
- secret boundaries;
- reconciliation requirements.

## OPA policy examples

Deny when:

- certification is insufficient;
- live trading is disabled;
- actor lacks required permission;
- symbol is not allowlisted;
- strategy lifecycle stage is not eligible;
- hard-risk decision is deny;
- reconciliation state is unhealthy;
- exchange state is unhealthy;
- global kill is active;
- TradeIntent expired.

## Kill-switch hierarchy

- Pause Agent
- Pause Strategy
- Pause Portfolio
- Pause Math Mode
- Pause Strategy Mode
- Disable New Orders
- Cancel Open Orders
- Reduce Exposure
- Global Kill

Global Kill must work without Claude.

## Secrets

Preferred secrets manager: OpenBao or equivalent.

Binance key permissions for live Spot:

- read: enabled
- trade: enabled
- withdraw: disabled

Prefer exchange IP allowlisting.

Secrets must never be stored in:

- source control;
- prompts;
- agent memory;
- frontend storage;
- logs;
- ClickHouse;
- unencrypted DB fields.

## Environment separation

Required environments:

- development
- test
- simulation
- paper
- shadow
- canary
- live

Live credentials must never be reused in development.

## Security event audit

Audit at minimum:

- permission changes;
- risk-limit changes;
- policy changes;
- strategy promotions;
- model promotions;
- secret lifecycle events;
- kill-switch actions;
- live-mode activation;
- TradeIntent decisions;
- order submissions;
- reconciliation incidents.

## Fail-closed rule

When safety-critical state is unknown, new trading is blocked until state is reconciled.
