# AGENTS.md — Repository Instructions for Codex

## Mission

Build CrazyTrader.ai V0.1 as an Enterprise Local autonomous crypto trading platform that can eventually become real-money capable on Binance after formal certification.

The implementation must preserve the architecture in docs/architecture and docs/specs.

## Non-negotiable rules

1. No LLM, agent, prompt, hook, UI component, or research process may directly submit an order to Binance.
2. Every proposed trade must become a typed TradeIntent.
3. Every TradeIntent must pass schema validation, certification validation, portfolio validation, deterministic hard-risk validation, and OPA authorization before execution.
4. Binance live credentials must never be available to agent prompts, agent memory, frontend code, analytics stores, test fixtures, or source control.
5. Open-position protection, reconciliation, and kill switches must not depend on Claude availability.
6. Research output may not self-promote into production.
7. Strategy and model versions are immutable after promotion.
8. Financial operations must be idempotent where retry is possible.
9. Unknown exchange state must trigger reconciliation, never blind retry.
10. Real-money mode must be impossible before L6 LIVE CERTIFIED.
11. Withdrawal capability is out of scope and must remain disabled.
12. Live credentials and real-money activation require an explicit owner-controlled external setup step.

## Architecture authority

In case of conflict, use this precedence:

1. AGENTS.md safety rules.
2. Accepted ADRs under docs/adr.
3. docs/architecture/ARCHITECTURE_V1.md.
4. docs/specs.
5. docs/roadmap/AUTONOMOUS_ENTERPRISE_LOCAL_GOAL.md when autonomous-program mode is active.
6. current ExecPlan.
7. implementation details.

If implementation requires changing a higher-priority rule, stop and create an ADR proposal instead of silently changing architecture.

## Autonomous program mode

When Codex is explicitly launched with the Enterprise Local Master Goal in docs/roadmap/AUTONOMOUS_ENTERPRISE_LOCAL_GOAL.md, it is authorized to progress autonomously through the implementation roadmap without waiting for routine human approval between phases.

In autonomous program mode, Codex must:

1. keep durable project state in the repository;
2. create or update phase ExecPlans;
3. implement the current phase;
4. run validation and self-audit;
5. fix failures;
6. record evidence;
7. commit completed milestones to the assigned working branch;
8. advance to the next phase only after the previous gate passes;
9. continue until Enterprise Local completion or a true external blocker is reached.

Codex must not stop merely to ask routine questions, confirm ordinary engineering choices, request approval for a passing phase gate, or provide status updates.

A blocker is valid only when work cannot safely continue without information, access, credentials, an external service action, or a binding product decision that cannot be derived from the existing architecture.

Examples of valid blockers:

- repository/environment permission is missing;
- required cloud tooling cannot be enabled by Codex;
- owner authentication is required;
- a required external credential must be entered by the owner;
- Binance live API credentials are required for later live validation;
- explicit owner activation is required before real-money execution;
- a binding architecture conflict requires an ADR decision and no safe default exists.

When blocked, Codex must:

1. finish all independent work that can still proceed;
2. commit and push durable progress;
3. write BLOCKER.md or update the program status with exact blocker details;
4. ask the owner for the minimum action required to unblock;
5. state exactly how to resume.

## Required workflow for substantial work

For every task that changes architecture, service boundaries, data contracts, security, trading logic, risk logic, or more than one service:

1. Read AGENTS.md.
2. Read the relevant architecture/specification documents.
3. Create or update an ExecPlan following .agent/PLANS.md.
4. Identify dependencies and affected contracts.
5. Implement the smallest coherent slice.
6. Add or update tests.
7. Run required checks.
8. Record important decisions.
9. Update documentation when behavior changes.
10. Do not advance to the next roadmap gate until acceptance criteria pass.

## Repository ownership boundaries

A task should modify only the areas it owns unless the ExecPlan explicitly justifies cross-boundary changes.

Expected top-level ownership:

- apps/web: user interface.
- apps/control-api: owner-facing control API.
- services/agent-runtime: permanent agents and task lifecycle.
- services/ai-gateway: AI provider adapters and routing.
- services/market-data: exchange market data.
- services/math-engine: quantitative features and Math Mode.
- services/strategy-engine: strategy selection and Strategy Mode.
- services/portfolio-engine: allocation and capital growth.
- services/risk-engine: deterministic hard risk.
- services/execution: order execution.
- services/reconciliation: exchange/internal state reconciliation.
- services/ledger: append-only financial journal.
- services/research: research and validation workflows.
- services/audit: audit event persistence.
- packages/contracts: public internal contracts and schemas.
- packages/domain: shared domain types.
- packages/events: versioned event definitions.
- agents: agent manifests, skills, prompts, policies, and tests.
- policies/opa: authorization policies.
- infra: deployment and platform configuration.
- tests: integration, simulation, chaos, and security tests.

## Testing rules

Critical financial paths require:

- unit tests;
- contract tests;
- integration tests;
- failure-path tests;
- idempotency tests where applicable;
- restart/recovery tests;
- negative authorization tests;
- deterministic risk tests.

No test may claim real-money readiness merely because a backtest passes.

## Security rules

- Never commit secrets.
- Never generate sample live credentials.
- Never log raw secrets.
- Never expose secrets through exception messages.
- Use least privilege.
- Treat agent outputs as untrusted input.
- Treat external exchange responses as untrusted data until validated.
- Prefer explicit allowlists over broad permissions.
- Security controls below the financial trust boundary must be deterministic.

## Open-source dependency rules

Before adding a material dependency, record:

- license;
- role;
- why it is needed;
- replacement path;
- whether it crosses the financial trust boundary;
- whether it is safe for proprietary/commercial use.

Current preferred candidates are documented in docs/architecture/ARCHITECTURE_V1.md.

Do not copy GPL or AGPL code into proprietary core without explicit legal/licensing review.

## Coding principles

- Contract-first design.
- Version event and API schemas.
- Strong typing at boundaries.
- Explicit state machines for financial workflows.
- Immutable production artifacts.
- Append-only financial ledger.
- Reproducible environments.
- Observable services.
- Fail closed when safety state is uncertain.
- Prefer simple deterministic code in the money path.

## Phase control

Outside autonomous program mode, the current active phase is defined by the relevant roadmap phase document.

In autonomous program mode, Codex may advance sequentially through the roadmap after each phase gate passes and evidence is recorded.

Do not skip gates. Do not claim later certification levels without their required evidence.

## Definition of Done

A task or phase is done only when:

- acceptance criteria pass;
- tests pass;
- documentation matches behavior;
- no TODO hides a safety-critical missing implementation;
- failure behavior is defined;
- no new privilege escalation path was introduced;
- required evidence is recorded;
- the current certification/roadmap gate is genuinely satisfied.
