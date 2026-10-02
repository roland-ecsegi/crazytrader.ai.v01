# Phase 0 — Repository Bootstrap

## Status

ACTIVE

## Objective

Create a reproducible, testable repository foundation and freeze the first version of domain and service contracts.

Phase 0 intentionally does not implement live trading.

## Deliverables

### Repository

Create:

- apps/web
- apps/control-api
- services/agent-runtime
- services/ai-gateway
- services/market-data
- services/math-engine
- services/strategy-engine
- services/portfolio-engine
- services/risk-engine
- services/execution
- services/reconciliation
- services/ledger
- services/research
- services/audit
- packages/domain
- packages/contracts
- packages/events
- packages/shared
- agents
- policies/opa
- infra
- tests/unit
- tests/integration
- tests/simulation
- tests/chaos
- tests/security
- docs/plans

### Toolchain

Codex must propose and document the exact language/runtime choices before implementing them.

Guiding preference:

- Python for trading/research/agent services unless a stronger reason exists.
- TypeScript for web UI.
- Rust may be used indirectly through NautilusTrader or performance-critical libraries rather than introducing custom Rust prematurely.

### Contracts

Implement initial typed contracts for:

- TradeIntent
- RiskDecision
- PolicyDecision
- Order
- OrderState
- Fill
- Portfolio
- StrategyVersion
- ModelVersion
- AuditEvent
- CertificationState
- common event envelope

### Quality

Provide:

- formatting;
- linting;
- type checking;
- unit-test framework;
- contract tests;
- pre-commit or equivalent developer checks;
- CI workflow.

### Local developer environment

Provide:

- documented setup;
- environment-variable template with no secrets;
- container baseline where justified;
- one command or documented minimal command set to run checks.

## Explicit non-goals

Do not implement:

- Binance live credentials;
- Binance live order submission;
- real-money mode;
- production risk values;
- automatic strategy self-promotion;
- billing;
- multi-user SaaS;
- Kubernetes.

## Acceptance criteria

Phase 0 passes only if:

1. Repository structure exists.
2. Documentation is internally linked.
3. Contracts compile/type-check.
4. Unit tests run.
5. Contract tests run.
6. CI executes the same core checks.
7. No secrets are present.
8. No code path can submit a live exchange order.
9. Architecture rules are referenced from AGENTS.md.
10. A Phase 1 ExecPlan can be written without guessing core contract semantics.

## First Codex task

Codex should:

1. Read AGENTS.md.
2. Read .agent/PLANS.md.
3. Read architecture/spec documents.
4. Create docs/plans/phase-0-repository-bootstrap.md.
5. Propose exact toolchain choices in that plan.
6. Implement Phase 0 only.
7. Run all Phase 0 checks.
8. Update the plan with evidence.
9. Stop at the Phase 0 gate.
