# Implementation Roadmap V1

Goal: Enterprise Local / L6 LIVE CERTIFIED through evidence-gated autonomous phases.

0. Repository/toolchain/domain/contracts/events/CI. No live execution.
0.5. Open-source compatibility/license spikes; evaluate/pin NautilusTrader/Binance SDK and core platform dependencies before rebuilding equivalents.
1. Platform backbone: PostgreSQL, NATS, audit, control API, config/identity, baseline telemetry.
2. Market/data: Binance test/sandbox data, normalized events, gap/freshness, ClickHouse/object store/history.
3. Ledger/portfolio: append-only postings, allocation, decimal invariants, reconciliation-ready state.
4. Hard Risk + OPA: risk-direction model, deterministic limits, kill hierarchy, risk-reduction path, negative tests.
5. Execution + reconciliation: state machine, idempotency, selected execution foundation, exchange test adapter, UNKNOWN recovery.
6. Math Mode: quant features/models, cost-aware edge/sizing, independent budget/P&L, TradeIntent.
7. Strategy Mode: registry/versioning/regime, Low/Medium/High, independent budget/P&L, TradeIntent.
8. Permanent agent runtime: identity, permissions, skills, memory/ExperienceRecords, audit.
9. AI Gateway/Claude: CLI, Agent SDK, API adapters, UI-selectable provider/model, local-auth boundary.
10. Research lab: backtests, MLflow, optimization, candidates, leakage/overfit controls.
11. Controlled learning: experience/post-trade/drift/online-learning research and promotion lifecycle.
12. Capital Growth Engine: allocation/risk/correlation/liquidity/regime with owner caps.
13. Custom Command Center: health, mode controls, capital/risk, agents, strategies/models, research, certification, audit, kill, provider/model selector.
14. Security hardening: OpenBao, least privilege/networking, secret rotation, prompt-injection defenses, dependency scanning/SBOM, environment separation.
15. Operations/recovery: backups/restore drills, restart/replay/reconciliation recovery, upgrade/rollback, runbooks, long monitoring.
16. L1/L2 evidence.
17. L3 Paper.
18. L4 Shadow.
19. L5 Canary Authorized + bounded owner-local canary.
20. L6 LIVE CERTIFIED / Enterprise Local acceptance.

Future Enterprise SaaS is separate: multiple users/orgs, true tenant isolation, RBAC/SSO/MFA, subscriptions/billing, commercial API, paid API-first AI metering, HA/scaling and additional security/compliance/pentesting/customer admin.
