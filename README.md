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

## Developer setup (Phase 0)

Use Python 3.12 and uv 0.12.19. Run `make setup` then `make check` from the repository root. `uv.lock` pins all Python dependencies. `make schemas` regenerates the checked-in V1 JSON Schemas after an intentional contract change.

See [Phase 0 ExecPlan](docs/plans/phase-0-repository-bootstrap.md), [contracts](packages/contracts/README.md) and [program status](docs/program/STATUS.md). Service/UI directories are ownership boundaries pending their roadmap implementation, not running services. This bootstrap remains L0 and contains no exchange order submission path.


Phase4 risk boundary: deterministic `crazytrader_risk.engine`, adopted OPA bundle,
HTTP policy client and opt-in same-policy local protective fallback. Internal
`RiskService` accepts intent/authenticated actor, not agent-supplied context. It
loads owner configuration and journal/archive/service/control proofs, then persists
risk/policy evidence and audit outbox. Missing source/config/lifecycle/certification
proof denies; current trusted certification boundary is L0. Cancellation contracts
manage an original immutable intent and stable owned order in the Phase5 registry. No exchange submission endpoint or live capability. See Phase4 evidence
and active Phase5 ExecPlan. Production scoped roles/TLS remain Phase14.

Phase5 coordination milestone: immutable execution requests/transitions, stable
client IDs, atomic journal reservation and one submission claim for approved
protective SIMULATION requests. Restart in SUBMITTING becomes UNKNOWN with funds
reserved. The isolated official-SDK loopback fixture verifies order submission/recovery,
canonical partial/full fill and fee settlement, owned cancellation and suspense/incident
containment. BUY cost buffers, mixed custody, complete account reconciliation and
selected simulation adoption remain active Phase5 work.

The official Spot SDK fixture now proves signed dummy-auth accepted-timeout and
query recovery after restart with one submitted order and exact decimal strings.
Fixed literal-loopback endpoints, no inherited credentials, retries0 and no redirects;
it cannot contact Binance or act as production live/simulation certification. Query
not-found remains unresolved; recovered open order alone does not grant full-account
health. Current-policy cancellation uses one durable DELETE claim; receipts never
release funds. Query plus complete fills atomically settles proven remainder. Known
unposted truth retains reservation and opens an incident while allowing owned
cancellation. Full venue-rule provenance and MARKET checks are required before reservation and
final submission claim;
actual quote-amount accounting remains pending. Certification is L0; no Phase5 gate.
