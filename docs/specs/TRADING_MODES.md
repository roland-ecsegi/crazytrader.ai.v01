# Trading Modes V1

Shared objective: maximize sustainable risk-adjusted compounded return after fees, spread, slippage, liquidity and risk constraints. No guaranteed monthly return and no forced trade count.

Each mode has independent capital budget, P&L, drawdown, attribution, start/pause/stop state, Auto Trading ON/OFF and audit trail.

## Math Mode

market data -> validated features -> quantitative/statistical model -> probability/return distribution -> costs/liquidity -> expected net edge -> risk-aware sizing -> TradeIntent.

LLMs may research and explain. Free-form LLM judgment cannot replace authoritative live mathematical edge computation. Zero trades is valid.

## Strategy Mode

market state -> regime detector -> eligible validated strategy versions -> scoring/evidence -> portfolio context -> Low/Medium/High profile -> TradeIntent.

Low: higher selectivity/smaller sizing. Medium: balanced. High: more aggressive within absolute owner/system survival limits; it is not permission to bypass hard risk.

Math evidence may feed Strategy Mode, but capital/P&L remain separately measurable.

Owner can allocate amount `n`, select Strategy risk profile, start/pause/stop Auto Trading, set hard caps, choose agent AI provider/model and trigger Global Kill. Owner manual trades still pass risk/policy.
