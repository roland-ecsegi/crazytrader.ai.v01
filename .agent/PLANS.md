# ExecPlan Standard

ExecPlans are mandatory living/resumable implementation records for new services/agents, financial state machines, TradeIntent/events, migrations, risk/OPA/execution/reconciliation/ledger/Binance/security changes, cross-service work, and roadmap phases.

Store at `docs/plans/YYYY-MM-DD-short-title.md`.

Required sections:
- Goal and measurable gate
- Non-goals
- Architecture context
- Current state
- Proposed design and reused open-source components
- Files/ownership
- Dependencies, pinned-version plan, licensing/replacement path
- Failure modes, including risk-increasing vs risk-reducing behavior where relevant
- Security/financial-risk impact
- Data/event migrations and replay compatibility
- Implementation steps
- Exact test plan
- Acceptance criteria
- Rollback/recovery
- Resume checkpoint
- Progress log
- Decisions
- Completion summary

Resume checkpoint must record working branch, last durable commit, current step, next exact action, uncommitted-work status, blockers/usage state, and last verification commands.

Safety/product invariants may not be weakened to make tests pass. In Autonomous Program Mode a passing gate leads automatically to the next eligible phase. Before expected usage/budget interruption, push a durable checkpoint.
