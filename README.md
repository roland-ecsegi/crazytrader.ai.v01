# CrazyTrader.ai V0.1

CrazyTrader.ai is an autonomous, agent-controlled crypto trading platform being built as an **Enterprise Local** product first, with a separate future Enterprise SaaS commercialization phase.

## Product target

Enterprise Local is the complete private product for one owner / one tenant. It must eventually support real-money Binance Spot trading after formal certification; the future SaaS phase is **not** required for the owner to trade live.

Core product requirements:

- **Math Mode**: quantitative/statistical live decision path; AI may research/orchestrate but does not replace the quantitative decision engine.
- **Strategy Mode**: validated/versioned strategies with **Low / Medium / High** risk profiles.
- Independent capital allocation and P&L for Math Mode and Strategy Mode.
- Permanent software agents with stable identity, real executable skills, governed memory, permissions, experience, and audit history.
- AI Gateway supporting Claude CLI/subscription workflows, Claude Agent SDK where supported, Claude API, and future providers.
- Autonomous research and controlled learning from historical data and the platform's own executed trades.
- Deterministic Hard Risk Engine, OPA policy enforcement, execution, reconciliation, ledger, kill switches, and recovery.
- Binance live key with **withdrawal disabled**; live credentials are owner-local secrets and are never exposed to Codex Cloud or LLM prompts.
- Backtest -> simulation -> paper -> shadow -> bounded canary -> L6 LIVE CERTIFIED.
- Custom product UI and business logic. Open-source components are infrastructure building blocks, not the product identity.

## Performance objective

The platform must optimize **sustainable risk-adjusted compounded return subject to survival, drawdown, liquidity, cost, and owner-capital constraints**.

There is **no guaranteed monthly return** and no hard-coded rule forcing a target such as 12%, 44%, 100% or a minimum number of trades. Zero trades is valid when the estimated edge does not clear costs and risk thresholds.

## Core operating principle

> AI proposes. Math calculates. Risk constrains. Policy authorizes. Execution executes. Exchange confirms. Ledger records. Agents learn.

## Financial trust boundary

Anything above the boundary may be wrong; anything below must be deterministic, constrained, auditable, recoverable, and fail-safe.

    Claude / Agents / ML / Research
                  |
                  v
              Proposals
    --------------------------------
          FINANCIAL TRUST BOUNDARY
    --------------------------------
                  |
                  v
           Hard Risk Engine
                  |
                  v
                 OPA
                  |
                  v
           Execution Engine
                  |
                  v
               Binance

## Start here

1. `AGENTS.md`
2. `.agent/PLANS.md`
3. `docs/architecture/ARCHITECTURE_V1.md`
4. `docs/architecture/OPEN_SOURCE_ADOPTION.md`
5. `docs/specs/TRADING_MODES.md`
6. `docs/specs/AGENTS_AND_SKILLS.md`
7. `docs/specs/STRATEGY_MODEL_LIFECYCLE.md`
8. `docs/specs/CAPITAL_GROWTH.md`
9. `docs/specs/TRADE_INTENT.md`
10. `docs/specs/EXECUTION_AND_RECONCILIATION.md`
11. `docs/specs/RISK_SECURITY.md`
12. `docs/specs/UI_COMMAND_CENTER.md`
13. `docs/specs/LOCAL_DEPLOYMENT.md`
14. `docs/specs/TESTING_AND_CERTIFICATION.md`
15. `docs/roadmap/AUTONOMOUS_ENTERPRISE_LOCAL_GOAL.md`
16. `docs/roadmap/CODEX_RESUME_PROTOCOL.md`
17. `docs/roadmap/CODEX_MASTER_PROMPT.md`
18. `docs/program/STATUS.md`

## Current state

Architecture/specification baseline audited on 2026-10-02. Implementation starts at Phase 0 and, in Autonomous Program Mode, proceeds automatically through the roadmap after each gate passes.

Real-money activation remains impossible before L6 and requires an explicit owner-controlled local credential/activation step.
