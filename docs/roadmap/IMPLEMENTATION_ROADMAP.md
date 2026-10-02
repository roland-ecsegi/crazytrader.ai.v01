# Implementation Roadmap V1

## Goal

Reach Enterprise Local / L6 LIVE CERTIFIED through evidence-gated autonomous phases.

## Phase 0 — Repository, toolchain and contracts

Deliver:
- monorepo/toolchain;
- typed domain/contracts/events;
- CI, formatting, linting, type checks;
- unit/contract test framework;
- secret scan;
- reproducible local developer setup.

No live exchange path.

## Phase 0.5 — Open-source compatibility/license spikes

Before reinventing infrastructure:
- evaluate/pin NautilusTrader execution/simulation fit;
- validate Binance official SDK/reference behavior;
- verify OPA/OpenBao/NATS/MLflow/PostgreSQL/ClickHouse/object-store integration approach;
- record versions/licenses/security/replacement boundaries;
- record why any approved candidate is rejected.

## Phase 1 — Platform backbone

PostgreSQL, NATS JetStream, audit service, notification service, control API, service config/identity, health model and baseline telemetry.

## Phase 2 — Market/data platform

Binance test/sandbox market-data adapter, normalized events, freshness/gap detection, ClickHouse, object storage and historical ingestion.

## Phase 3 — Ledger/portfolio primitives

Append-only transaction/posting ledger, reservations, allocations, decimal invariants, portfolio attribution and reconciliation-ready state.

## Phase 4 — Hard Risk + OPA

Risk-direction classification, deterministic limits, Low/Medium/High constraints, kill hierarchy, degraded-mode risk-reduction path, OPA policies and negative-path tests.

No live risk-increasing orders.

## Phase 5 — Execution + reconciliation

Execution state machine, idempotent client IDs, selected execution foundation, exchange test adapter, partial fill/cancel flow, UNKNOWN state and reconciliation.

Start with simulation/testnet only.

## Phase 6 — Math Mode

Quantitative features/models, expected-value/cost model, sizing, separate budget/P&L, Auto Trading controls, TradeIntent generation and deterministic fixtures.

## Phase 7 — Strategy Mode

Strategy registry/immutable versions, regime metadata, Low/Medium/High, separate budget/P&L, Auto Trading controls and TradeIntent generation.

## Phase 8 — Permanent agent runtime

Stable identity, permissions, task lifecycle, skill registry, governed memory, ExperienceRecords, audit and agent health.

## Phase 9 — AI Gateway / Claude

Claude CLI, Agent SDK and API adapters, UI-selectable provider/model, fallback/usage telemetry, local-auth boundary and provider outage behavior.

## Phase 10 — Research lab

Backtest/research engine integration, MLflow, optimization, datasets/features lineage, candidate registry, leakage/overfit controls and research-agent skills.

## Phase 11 — Controlled learning

Experience pipeline, post-trade analysis, drift, online/adaptive research path, lifecycle/promotion/rollback enforcement.

## Phase 12 — Capital Growth Engine

Mode/strategy allocation proposals, correlation/liquidity/regime inputs, performance-quality/sample-size gates, owner absolute caps and degradation de-allocation.

## Phase 13 — Custom Command Center UI

System health, portfolios, Math/Strategy controls, capital/risk profiles, Auto Trading, agents, skills/memory status, strategies/models, research, certification, audit, Global Kill and AI provider/model selection.

## Phase 14 — Security hardening

OpenBao, network/service least privilege, secret rotation, prompt-injection controls, dependency vulnerability scanning/SBOM, environment separation and hardening tests.

## Phase 15 — Operations/recovery readiness

Backup/restore drills, restart/replay/reconciliation recovery, upgrade/rollback, runbooks, monitoring/alerts and long-duration operational tests.

## Phase 16 — L1/L2

Backtest and simulation certification evidence.

## Phase 17 — L3 Paper

Real-time paper operation, stability, failure/restart and accounting evidence.

## Phase 18 — L4 Shadow

Live observation without orders, reconciliation proof and execution-estimate comparison.

## Phase 19 — L5 Canary Authorized + owner-local bounded canary

Owner enters withdrawal-disabled live key into local secret store and sets tiny capital cap/activation. Run bounded real canary on owner deployment and collect evidence.

## Phase 20 — L6 LIVE CERTIFIED / Enterprise Local acceptance

Resolve critical findings; verify recovery, duplicate-order protection, ledger, kill switch, monitoring/backups/runbooks; explicit owner live activation; final autonomous architecture/security audit.

## Future Enterprise SaaS — separate

Multiple users/orgs, real tenant isolation, RBAC/SSO/MFA, subscriptions/billing, commercial API, paid API-first AI usage/cost metering, HA/scaling and additional security/compliance/pentesting/customer admin.
