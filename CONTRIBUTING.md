# Contributing to CrazyTrader.ai

Read `AGENTS.md`, `.agent/PLANS.md`, architecture/specs and current program status before coding. Substantial work requires an ExecPlan.

PR/task summaries should state goal, architecture impact, changed contracts/services, tests/gate evidence, security/financial impact, migrations and limitations.

TradeIntent, hard risk, OPA, execution, reconciliation, ledger, certification and secrets changes require explicit gate review plus negative-path tests.

In Autonomous Program Mode the gate review may be an independent adversarial Codex pass. Routine human approval is not required unless a true external blocker or binding decision exists.

Behavioral changes update matching specs. Do not skip roadmap gates.
