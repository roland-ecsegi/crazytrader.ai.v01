# Contributing to CrazyTrader.ai

## Before coding

Read:

- AGENTS.md
- .agent/PLANS.md
- docs/architecture/ARCHITECTURE_V1.md
- relevant docs/specs files
- active roadmap phase

## Work style

Use a focused branch or Codex task.

For substantial work, create an ExecPlan under docs/plans.

## Pull requests

A PR should state:

- goal;
- architecture impact;
- files/services changed;
- tests executed;
- security/financial-risk impact;
- migration impact;
- remaining limitations.

## Safety-critical changes

Changes to:

- TradeIntent;
- risk;
- OPA;
- execution;
- reconciliation;
- ledger;
- certification;
- secrets;

require explicit review and negative-path tests.

## Documentation

Behavioral changes must update the corresponding specification.

## Scope

Do not implement a later roadmap phase merely because it is convenient. Respect active phase gates.
