# Autonomous Enterprise Local Master Goal

Take CrazyTrader.ai from the audited baseline to **Enterprise Local / L6 LIVE CERTIFIED**, autonomously in Codex Cloud except for true external owner actions. Enterprise SaaS is out of scope.

Required end state: custom single-owner product; Math and Strategy (Low/Medium/High); independent capital/P&L and Auto Trading controls; permanent agents with real skills/memory/permissions; Claude CLI/Agent SDK/API via AI Gateway; autonomous research/controlled learning; lifecycle; Capital Growth; Binance Spot; Hard Risk/OPA/execution/reconciliation/ledger; OpenBao/NATS/PostgreSQL/ClickHouse/object store/MLflow; custom UI; observability/backups/recovery/runbooks; L1-L6 evidence.

Autonomous loop per phase: inspect status -> read specs -> ExecPlan -> implement -> test -> adversarial gate review -> repair -> update evidence -> commit/push -> auto-advance.

Before inventing mature infrastructure, follow `OPEN_SOURCE_ADOPTION.md`.

Codex Cloud never receives Binance live keys, owner Claude auth/session material or OpenBao unseal/bootstrap secrets. Final Claude local-auth validation and Binance canary/live run on owner-controlled deployment.

Only ask owner for minimum true external action after completing all independent work and checkpointing.

Follow `CODEX_RESUME_PROTOCOL.md`. Auto-continue within budget. Budget-limited means paused, not completed. If platform requires manual Resume after reset, preserve state so that is the only action required.

Maintain STATUS, DECISIONS, KNOWN_ISSUES, VALIDATION_LOG and active ExecPlans. STATUS records phase/certification/branch/last commit/next action/blockers/usage/verification.

Use durable branch (preferred `codex/enterprise-local-autonomous`) and push frequently.

At major gates audit architecture drift, prompt/secret exposure, agent privilege creep, duplicate orders, idempotency, unknown-state recovery, risk-reduction availability, ledger invariants, event replay, stale data, policy/certification bypass, unvalidated promotion and dependency licensing/security.

L5/L6 requires explicit owner action and local canary. If missing, set BLOCKED_FOR_OWNER_LIVE_VALIDATION. Do not declare complete.

Master Goal completes only after actual L6 evidence exists, required tests pass, no critical defect remains, runbooks are ready, and SaaS has not been mixed into scope.
