# Open-Source Adoption Policy and Initial Map

Avoid reinventing mature infrastructure while preventing license/architecture lock-in. Every material dependency requires a compatibility spike, pinned version/range, license record, security review, replacement boundary and tests.

## Primary candidates

**NautilusTrader** — primary event-driven trading/execution/simulation candidate. Validate Binance Spot behavior, restart/reconciliation semantics, Python compatibility and LGPL obligations. Wrap behind our adapter.

**Binance official SDK/connectors** — venue-native reference and integration/reconciliation/API-drift tests. Never expose raw SDK authority to agents.

**Hummingbot / Condor / Hummingbot MCP** — crypto-native connector/agent references and selective reuse where license fit is verified. Do not rebrand as product or expose broad exchange MCP to live agents.

**CCXT** — optional research/future multi-exchange adapter, not sole Binance execution authority.

**Qlib / Optuna / River / Riskfolio-Lib / Stable-Baselines3** — research-plane candidates only; production use requires reproducibility and lifecycle gates.

**MLflow, OPA, OpenBao, NATS JetStream, PostgreSQL, ClickHouse, object storage** — core infrastructure candidates.

## License caution / reference only

- Freqtrade/FreqAI: GPL; study/benchmark unless explicit legal approval.
- cryptofeed: AGPL; avoid proprietary embedding without legal approval.
- vectorbt: verify current commercial terms before embedding.
- Grafana: internal ops only unless licensing is reviewed; custom product UI remains ours.

## Spike rule

Before building custom exchange execution, backtest engine, event bus, policy engine, secret store, model registry or analytical store, first evaluate the approved candidate and record why reuse is unsuitable.

## Product differentiation

Permanent-agent governance, Math/Strategy behavior, capital growth, controlled self-improvement, lifecycle/certification, custom UX, cross-agent knowledge/audit and product-specific risk/policy contracts.
