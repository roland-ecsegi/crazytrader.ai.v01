# CrazyTrader.ai V0.1

CrazyTrader.ai is an autonomous, agent-controlled crypto trading platform being designed as an Enterprise Local product first, with a later Enterprise SaaS phase.

Current repository status: architecture and Codex execution specification.

## Product target

Enterprise Local must be:

- single-owner and single-tenant;
- privately deployable;
- capable of Binance Spot live trading after certification;
- built around permanent software agents with persistent identity, memory, skills, permissions, and audit history;
- capable of running Math Mode and Strategy Mode independently;
- able to use Claude CLI, Claude API, and future AI providers through adapters;
- protected by deterministic risk, policy, execution, reconciliation, and kill-switch systems;
- able to research and improve strategies without allowing unvalidated research to reach live capital.

## Core operating principle

AI proposes. Math calculates. Risk constrains. Policy authorizes. Execution executes. Exchange confirms. Ledger records. Agents learn.

## Trading modes

### Math Mode

Pure quantitative/statistical decision logic. The LLM may orchestrate research and explain results, but the trading edge calculation is produced by deterministic or validated quantitative models.

### Strategy Mode

Validated and versioned strategies operating under selectable Low, Medium, and High risk profiles. High risk never bypasses absolute hard limits.

## Financial trust boundary

Everything above the trust boundary may fail, hallucinate, become unavailable, or propose a bad action.

Everything below it must be deterministic, constrained, auditable, recoverable, and fail-safe.

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

## Repository documentation

Start with:

1. AGENTS.md
2. .agent/PLANS.md
3. docs/architecture/ARCHITECTURE_V1.md
4. docs/specs/SERVICE_CONTRACTS.md
5. docs/specs/DOMAIN_MODEL.md
6. docs/specs/TRADE_INTENT.md
7. docs/specs/EVENT_CATALOG.md
8. docs/specs/AGENTS_AND_SKILLS.md
9. docs/specs/RISK_SECURITY.md
10. docs/specs/TESTING_AND_CERTIFICATION.md
11. docs/roadmap/IMPLEMENTATION_ROADMAP.md
12. docs/roadmap/CODEX_TASK_GRAPH.md
13. docs/roadmap/PHASE_0_BOOTSTRAP.md

## Current rule

Do not implement real-money trading yet. The repository is in Phase 0 specification/bootstrap. Live trading must remain impossible until the certification ladder reaches L6 LIVE CERTIFIED.
