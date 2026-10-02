# Architecture V1 — Enterprise Local

## Target

CrazyTrader.ai V0.1 is a complete private single-owner/single-tenant product first, capable of Binance Spot real-money operation after L6 certification without the future SaaS phase.

Future Enterprise SaaS adds customer multi-tenancy, subscriptions/billing, commercial API, paid API-first AI routing at scale, stronger tenant/compliance security and HA as justified.

## Product invariants

- Math Mode and Strategy Mode are first-class.
- Math Mode live decisions are quantitative/statistical and cost-aware.
- Strategy Mode uses validated/versioned strategies with Low/Medium/High profiles.
- Mode capital, P&L, drawdown and attribution are independently observable.
- No fixed return guarantee or forced minimum trade count.
- Permanent agents are persistent software entities, not temporary labels.
- Open-source solves infrastructure; custom UI/product behavior and agent governance remain ours.
- Binance withdrawal remains disabled.
- Codex Cloud builds the product but never possesses live secrets.

## Four planes

**Trading**: market data, features, Math/Strategy, portfolio, TradeIntent, hard risk, OPA, execution, reconciliation, ledger.

**Agent Control**: permanent identities, runtime, skills/tools, memory, orchestration, AI routing.

**Research**: data, hypotheses, experiments, features/models/strategies, backtests, optimization, walk-forward and candidate lifecycle.

**Platform**: custom UI/control API, storage/events/secrets/audit/observability/backups/recovery/deployment.

## Core flow

    Owner / Custom UI -> Control API
             |-> Agent Runtime
             |-> Trading Control
             |-> Research
                    |
                 TradeIntent
                    |
             Hard Risk Engine
                    |
                   OPA
                    |
              Execution Engine
                    |
                  Binance
                    |
              Reconciliation
                    |
                  Ledger

## Risk-direction invariant

Degraded state may deny **new/increased risk** while preserving authorized **risk reduction, cancellation and emergency flattening**. A failed dependency must not trap capital.

## Financial trust boundary

Above: agents, Claude/AI, ML, research, strategy/portfolio proposals.
Below: schema/certification, hard risk, OPA, execution, reconciliation, ledger, kill switches.
Anything above may be wrong.

## Baseline services/platform

control-api, agent-runtime, ai-gateway, market-data, math-engine, strategy-engine, portfolio-engine, risk-engine, OPA, execution, reconciliation, ledger, research, audit, notification; PostgreSQL, ClickHouse, NATS JetStream, OpenBao, MLflow, object storage, OpenTelemetry, Prometheus.

## Reuse

Follow `OPEN_SOURCE_ADOPTION.md`. NautilusTrader is the primary execution/simulation candidate subject to an early spike. Binance official SDK is venue-native reference/integration. Hummingbot/Condor/MCP are selective reference sources. Quant/ML libraries stay in research and cannot become direct live authorities.

## AI runtime

Permanent agents are provider-independent. Enterprise Local should support Claude CLI/`claude -p`, Claude Agent SDK where supported, Claude API and future adapters behind AI Gateway. Local subscription auth stays owner-local and never enters Codex Cloud.

## Deployment

Owner-controlled Linux/private host with containers/Compose or equivalent. Internal DB/OPA/OpenBao endpoints are not directly exposed to WAN. Kubernetes is deferred to SaaS.

Schemas may carry tenant/owner IDs now; that is not a claim of current multi-tenant isolation.
