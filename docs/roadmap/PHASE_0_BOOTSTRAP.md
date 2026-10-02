# Phase 0 — Repository Bootstrap

## Status
ACTIVE

## Objective

Create the reproducible monorepo/toolchain and freeze initial typed domain/contracts/events. No live Binance credentials or live order submission in this phase.

## Deliverables

Create planned `apps/`, `services/` (including `notification`), `packages/`, `agents/`, `policies/opa/`, `infra/`, `tests/`, and `docs/plans/` structure.

Toolchain must be justified in ExecPlan. Preference: Python for trading/research/agent services, TypeScript for custom web UI, reuse Rust indirectly through mature dependencies before custom Rust.

Implement typed foundations for TradeIntent, RiskDecision, PolicyDecision, Order/OrderState, Fill, Portfolio, StrategyVersion, ModelVersion, AuditEvent, CertificationState and common event envelope.

Add formatting, linting, type checking, unit/contract tests, CI, secret scan and reproducible local setup.

## Acceptance

1. Structure exists.
2. Docs linked.
3. Contracts type-check.
4. Unit/contract tests pass.
5. CI runs equivalent checks.
6. Secret scan clean.
7. No live-order path exists.
8. Architecture rules referenced.
9. Phase 0.5 / Phase 1 can proceed without guessing core semantics.

## Autonomous transition

Create/update `docs/plans/phase-0-repository-bootstrap.md`, implement and validate.

**In Autonomous Program Mode, do not stop at the Phase 0 gate.** Record evidence, commit/push, then automatically proceed to Phase 0.5 and next eligible phase.

Outside Autonomous Program Mode, return the Phase 0 result normally.
