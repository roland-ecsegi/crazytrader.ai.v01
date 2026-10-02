# Architecture V1 — Enterprise Local

## Target

CrazyTrader.ai V0.1 targets Enterprise Local first:

- one owner;
- one tenant;
- private/local deployment;
- Binance Spot first;
- fully functional Math Mode;
- fully functional Strategy Mode with Low, Medium, and High profiles;
- permanent agents;
- Claude CLI and API routing;
- research and controlled self-improvement;
- real-money capability only after formal certification.

The later Enterprise SaaS phase adds customer-facing multi-tenancy, billing, commercial APIs, stronger tenant isolation, and large-scale infrastructure. It must not be required for the owner to trade live locally.

## Four planes

### Trading Plane

Owns:

- market data;
- feature computation;
- Math Mode;
- Strategy Mode;
- portfolio state;
- TradeIntent;
- risk;
- policy;
- execution;
- reconciliation;
- ledger.

### Agent Control Plane

Owns:

- permanent agent identity;
- agent runtime;
- skills;
- tools;
- memory;
- task orchestration;
- AI provider selection;
- advisory analysis.

### Research Plane

Owns:

- datasets;
- experiments;
- feature research;
- model training;
- strategy discovery;
- backtesting;
- optimization;
- walk-forward validation;
- candidate lifecycle.

### Platform Plane

Owns:

- UI;
- control API;
- databases;
- event backbone;
- secrets;
- audit;
- observability;
- backups;
- infrastructure.

## Core flow

    Owner / UI
         |
         v
     Control API
         |
         +-------------------+------------------+
         |                   |                  |
         v                   v                  v
    Agent Runtime      Trading Control      Research
         |                   |                  |
         +-------------------+------------------+
                             |
                             v
                        TradeIntent
                             |
                             v
                     Hard Risk Engine
                             |
                             v
                            OPA
                             |
                        ALLOW / DENY
                             |
                             v
                     Execution Engine
                             |
                             v
                     Binance Adapter
                             |
                             v
                          Binance
                             |
                             v
                      Reconciliation
                             |
                             v
                          Ledger

## Financial trust boundary

Above the boundary:

- agents;
- Claude;
- ML;
- research;
- strategy proposals;
- portfolio recommendations.

Below the boundary:

- contract validation;
- certification enforcement;
- hard risk;
- policy;
- execution;
- reconciliation;
- ledger;
- kill switches.

The system must assume that anything above the boundary can be wrong.

## Baseline services

- control-api
- agent-runtime
- ai-gateway
- market-data
- math-engine
- strategy-engine
- portfolio-engine
- risk-engine
- execution
- reconciliation
- ledger
- research
- audit
- notification

Platform components:

- PostgreSQL
- ClickHouse
- NATS JetStream
- OPA
- OpenBao
- MLflow
- object storage
- OpenTelemetry
- Prometheus

## Preferred reusable foundations

### NautilusTrader

Strong candidate for execution and simulation foundations. Exact version must be pinned only after a compatibility spike.

### Binance official SDK

Use for exchange-native compatibility, integration tests, reconciliation/reference behavior, and API drift checks.

### Hummingbot / Condor / MCP

Use as crypto-native architectural reference and selective reuse where appropriate. Do not expose broad exchange-control MCP tools directly to live agents.

### Qlib, Optuna, River, Riskfolio-Lib, Stable-Baselines3

Research-plane candidates. None may directly control live execution.

### MLflow

Model and experiment registry candidate.

### OPA

Authorization policy engine.

### OpenBao

Secrets manager.

### NATS JetStream

Event backbone and replay.

### PostgreSQL and ClickHouse

Operational state and analytical/time-series storage respectively.

## Deployment

Enterprise Local should initially use containers on a Linux host, with Docker Compose or equivalent orchestration.

Kubernetes is intentionally deferred to the SaaS/scaling phase.

## Future SaaS readiness

Important entities should be tenant-aware from the start where low-cost to do so:

- tenant_id
- owner_id

Enterprise Local may use a single constant tenant such as local-owner.

Tenant-awareness in schemas is not permission to claim multi-tenant security before the SaaS hardening phase.
