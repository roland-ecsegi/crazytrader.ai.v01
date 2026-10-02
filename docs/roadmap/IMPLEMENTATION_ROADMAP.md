# Implementation Roadmap V1

## Goal

Build from a safe repository foundation to Enterprise Local LIVE CERTIFIED through gated phases.

## Phase 0 — Repository and contracts

Deliver:

- monorepo/toolchain;
- architecture docs;
- AGENTS.md and ExecPlan standard;
- domain package;
- contract package;
- event package;
- CI;
- lint/type/test framework;
- local development container baseline;
- no live trading.

Exit gate:

- all Phase 0 acceptance criteria pass.

## Phase 1 — Platform backbone

Deliver:

- PostgreSQL;
- NATS JetStream;
- audit service;
- basic control API;
- service identity/config system;
- health model;
- local observability baseline.

## Phase 2 — Market data and data platform

Deliver:

- Binance test/sandbox market-data adapter;
- normalized market events;
- gap/freshness detection;
- ClickHouse;
- object storage;
- historical ingestion interfaces.

## Phase 3 — Ledger and portfolio primitives

Deliver:

- append-only ledger;
- portfolio accounting;
- capital allocation;
- deterministic decimal handling;
- reconciliation-ready internal state.

## Phase 4 — Hard Risk and OPA

Deliver:

- risk rules engine;
- policy decision integration;
- kill-switch hierarchy;
- negative-path test suite.

No live execution yet.

## Phase 5 — Execution and reconciliation

Deliver:

- execution state machine;
- exchange test adapter;
- idempotent order submission;
- UNKNOWN state recovery;
- reconciliation service.

Initially testnet/simulation only.

## Phase 6 — Math Mode V1

Deliver:

- feature interfaces;
- quantitative edge contract;
- transaction-cost model;
- position-sizing proposal;
- Math Mode TradeIntent generation;
- deterministic test fixtures.

## Phase 7 — Strategy Mode V1

Deliver:

- strategy registry;
- immutable versions;
- regime metadata;
- Low/Medium/High profiles;
- Strategy Mode TradeIntent generation.

## Phase 8 — Permanent agent runtime

Deliver:

- stable agent identity;
- task lifecycle;
- permission model;
- skill registry;
- memory layers;
- audit integration.

## Phase 9 — Claude integration

Deliver:

- Claude CLI adapter;
- Claude API adapter interface;
- AI Gateway;
- provider fallback;
- usage and error telemetry.

AI remains outside the financial trust boundary.

## Phase 10 — Research lab

Deliver:

- experiments;
- backtesting integration;
- MLflow;
- optimization workflow;
- candidate strategy/model registry;
- research-agent tooling.

## Phase 11 — Controlled learning

Deliver:

- experience records;
- post-trade analysis;
- online-learning research path;
- drift detection;
- promotion workflow.

## Phase 12 — Capital Growth Engine

Deliver:

- portfolio allocation proposals;
- risk-budget allocation;
- strategy correlation analysis;
- owner hard-cap integration.

## Phase 13 — UI Command Center

Deliver:

- system health;
- portfolios;
- Math/Strategy controls;
- agent views;
- research views;
- certification views;
- risk and kill-switch controls;
- audit visibility.

## Phase 14 — Security hardening

Deliver:

- OpenBao integration;
- service least privilege;
- secret rotation;
- environment isolation;
- dependency and configuration hardening.

## Phase 15 — L1/L2 certification

Deliver:

- backtest readiness;
- simulation readiness;
- deterministic evidence.

## Phase 16 — L3 Paper

Deliver:

- paper-trading operation;
- long-running stability tests;
- failure/restart testing.

## Phase 17 — L4 Shadow

Deliver:

- live observation;
- no order submission;
- reconciliation proof;
- execution estimate validation.

## Phase 18 — L5 Canary

Deliver:

- tiny real-money capital cap;
- full risk and monitoring;
- incident testing;
- live execution evidence.

## Phase 19 — L6 Live Certified

Deliver:

- accepted canary evidence;
- resolved critical findings;
- verified recovery;
- verified kill switch;
- explicit owner live activation.

## Phase 20 — Enterprise Local stabilization

Deliver:

- operational runbooks;
- backup/restore;
- upgrade process;
- long-duration monitoring;
- performance tuning.

## Separate future phase — Enterprise SaaS

Not required for Enterprise Local live trading.

Adds:

- real multi-tenancy;
- organizations/users;
- RBAC/SSO/MFA;
- subscriptions/billing;
- tenant isolation;
- commercial API;
- API-based AI usage metering;
- HA/scaling;
- compliance and formal security programs.
