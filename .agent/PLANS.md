# ExecPlan Standard

## Purpose

ExecPlans are mandatory for substantial Codex work in CrazyTrader.ai. They are living implementation documents and durable resume checkpoints.

## When required

Create an ExecPlan for:
- a new service or permanent agent;
- a new financial state machine;
- TradeIntent, RiskDecision, PolicyDecision or event-schema changes;
- database/event migrations;
- risk/OPA/execution/reconciliation/ledger changes;
- Binance integration;
- AI provider integration;
- security architecture;
- cross-service refactoring;
- every implementation roadmap phase.

## Location

Store under:

    docs/plans/YYYY-MM-DD-short-title.md

## Required structure

### Goal
Concrete outcome and measurable gate.

### Non-goals
What is intentionally excluded.

### Architecture context
Binding architecture/spec/ADR references and invariants.

### Current state
What exists before the work starts.

### Proposed design
Components, boundaries, contracts, data flow and open-source foundations to reuse.

### Files and ownership
Directories/files expected to change and why.

### Dependencies and licensing
External dependencies, version/pinning plan, license, security implications, replacement path, and whether the component crosses the financial trust boundary.

### Failure modes
Expected failures and fail-safe behavior. For money-path work explicitly cover risk-increasing vs risk-reducing behavior.

### Security and financial-risk impact
State whether work is above/below the financial trust boundary. Cover secrets, prompt injection, privilege changes, replay/idempotency, and degraded-state behavior as relevant.

### Data/event migrations
Schema changes, compatibility, replay/backfill plan, rollback.

### Implementation steps
Small checkable steps with status boxes.

### Test plan
Exact commands/tests, not broad categories.

### Acceptance criteria
Objective pass/fail conditions.

### Rollback/recovery
How to revert safely.

### Resume checkpoint
Always record:
- working branch;
- last durable commit SHA;
- current step;
- next exact action;
- uncommitted-work status;
- current blockers;
- usage/budget state;
- last verification commands/results.

### Progress log
Dated updates.

### Decisions
Material decisions/alternatives/rationale.

### Completion summary
What shipped, evidence, limitations, next phase.

## Rules

Safety/product invariants cannot be weakened to make tests pass.

In Autonomous Program Mode:
- a passing gate automatically leads to the next eligible phase;
- before expected budget/usage interruption, checkpoint and push;
- if resumed after interruption, rehydrate from this ExecPlan and docs/program/STATUS.md rather than replanning from scratch.
