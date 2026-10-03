# Phase 4 ExecPlan — Deterministic Hard Risk and OPA

## Goal
Implement deterministic Spot risk direction and capped authorization using typed
immutable intent/state/owner limits, then OPA policy with explicit degraded-state
reduction/cancellation semantics. Prove unsafe/new risk cannot pass and protective
management does not depend on AI. No order submission or live activation.

## Non-goals
No free-form agent risk decisions, inferred owner capital, credential entry, execution
adapter, profit promise, SaaS or automatic policy weakening. No LIVE before L6 plus
owner activation (AGENTS invariant10), even though later canary wording needs an ADR.

## Architecture context
AGENTS; RISK_SECURITY; TRADE_INTENT; TRADING_MODES; TESTING_AND_CERTIFICATION;
SERVICE_CONTRACTS; DATA_AND_LEDGER; adopted OPA1.8.0 digest. Pre-T012 mandatory
adversarial architecture/security review must be recorded before implementation.

## Current state
Phase 0–2 published; Phase 3 local gate completing. Typed TradeIntent/RiskDecision/
PolicyDecision, append-only ledger/portfolio snapshots, market freshness/gap and
immutable provenance exist. L0, no orders or secrets. No deterministic evaluator,
policy bundle or authenticated risk/control mutation exists.

## Proposed design
Risk context is a typed snapshot from trusted internal state with intent/market/
portfolio/config version hashes and UTC freshness. Do not expose a tool that accepts
LLM-supplied healthy flags, balance, owner caps or lifecycle assertions as authority.
A test fixture is not a production state adapter. Decision is bound to exact intent,
state/config hashes and short expiry, with immutable reason codes/audit/outbox.

Classify Spot BUY as increasing; SELL is reducing only when quantity is provably
bounded by current attributable holdings and unresolved order reservations. Caller
risk_effect is a proposal; mismatch denies. Ambiguous REBALANCE denies until modeled.
Notional sizing/conversion uses verified fresh price/filter metadata and explicit
conservative step rounding; reducing exact-quantity SELL may use its dedicated
path under stale market/global new-risk kill, provided ownership, venue state,
quantity/no-short proof and explicit reduction authorization are current.

Check certification/execution environment (simulation/paper/shadow/testnet/LIVE),
portfolio/mode/strategy/version/lifecycle/profile, owner/system caps, total/mode/
portfolio/strategy/symbol exposure, order count/frequency/notional, daily loss and
drawdown, current market/venue/reconciliation health, liquidity/spread/slippage and
expiry/clock. Low/Medium/High can tighten owner limits and never loosen them.
Unknown cost/P&L/valuation health denies new risk; protective reductions use exposure
proof rather than fabricated prices. All arithmetic is exact decimal/rational.

OPA evaluates a canonical internal request with Hard Risk result, state hashes,
actor permissions, symbol allowlist, lifecycle, expiry and kill scope. Bundle digest
is verified; missing/down/invalid response denies new risk. Dedicated emergency
policy is owner-authorized/versioned and locally available for reduction/cancel;
no free-standing boolean from agent may invoke it. Cancel-only versus flatten
approval is explicit. Decision carries policy version/hash and provenance.

## Files and ownership
packages/contracts risk context/limits/authorization; packages/risk deterministic
engine/trusted adapters; services/risk-engine runtime; infra/policy Rego/bundle;
tests/risk unit/negative tests and actual OPA fixtures; migrations/events as needed;
program/evidence/review documents. Extend package, schema and locked toolchain.

## Dependencies and licensing
Reuse exact adopted OPA1.8.0 server digest and Apache2.0 policy infrastructure.
Use locked root Decimal/Pydantic/psycopg/NATS and mature HTTP client; no home-built
policy VM or AI dependency. Record any additional client pin/license before use.
Production roles/TLS/artifact signing remain later security gate.

## Failure modes
Forged increasing-as-reducing intent, expired/stale/changed state, float/rounding
loss, oversell under concurrent pending orders, caps/profile escalation, kill scope
bypass, unknown P&L/venue state, policy denial/outage/timeout/malformed response,
clock skew and source-ID replay. Fail closed for new risk; bounded protective paths
must have explicit deterministic ownership/quantity/policy proof and durable audit.

## Security and financial-risk impact
Below financial trust boundary; permission alone cannot bypass Hard Risk. No raw
SDK or credentials in agent/API policy payloads. Future execution consumes only
bound authorization with final expiry/filter/reconciliation rechecks, never bare
RiskDecision ALLOW. Development fixtures cannot become production authority.

## Data/event migrations
Additive typed context/decision evidence; versioned limits and policy hashes. Existing
ledger/market events remain compatible. Persist final result immutably before any
future execution request. Replay altered intent/state IDs denied; expired decisions
cannot be reused. Break formats only with a new version.

## Implementation steps
- [x] Read binding risk/intent/mode/certification contracts and design boundaries.
- [x] Record pre-T012 autonomous adversarial architecture/security review and resolve findings.
- [x] Implement typed limits/context/bound evidence and deterministic classifier/evaluator.
- [x] Implement scoped kill controls and dedicated bounded reduction/cancel path.
- [x] Implement versioned Rego authorization bundle and actual OPA integration.
- [x] Verify negative matrix, outage behavior, immutable replay and audit.
- [x] Final adversarial pass, durable publication, continue Phase 5 review/execution.

## Test plan
make check/integration; table-driven increasing/reducing/mismatch/certification/
expiry/caps/profile/health/price/filter tests; oversell/reservation negatives;
actual OPA eval and outage/malformed/permission/symbol/lifecycle denial; AI-unavailable
protective path fixture; no L0/L5 LIVE allow under current AGENTS invariant.

## Acceptance criteria
Unsafe/unknown increasing proposals deny with deterministic reason codes; reducing
quantity proof, scoped kill/cancel/flatten authorization work without AI; actual
OPA agrees with typed evaluator and its failures are bounded/fail-closed. Decisions
are intent/state/config/policy-bound with audit and no execution endpoint. L0 remains.

## Rollback/recovery
Freeze increasing risk, preserve versioned decisions/audit, revert evaluator/policy
reader with old schema support. Keep last verified owner-authorized protective
policy locally; never use outage to broaden permissions or fabricate current state.

## Resume checkpoint
Branch codex/enterprise-local-autonomous. Last published Phase3
ca085cd33135bd337b5b79de27d1bbf5aa11f17a, hosted CI37111641894 PASS.
Current Phase4 milestone: typed owner/profile limits, explicit unknown risk evidence,
Spot classifier/evaluator with29 tests, bound Rego/HTTP client and same-policy local
OPA reduction fallback with36 actual integration tests PASS. No phase gate claimed.
Next exact action: typed cancel-only proof/policy, trusted state/permission adapter
and immutable risk/policy audit persistence, then full negative gate/self-review.
Milestone publication in progress; no external blocker, usage active. No venue
mutation capability or production context endpoint exists. Future live authority
conflict remains recorded; continue independent engineering before owner ADR.

## Progress log
2026-10-03: Risk specification/design prepared while Phase3 final checks run.

## Decisions
Current AGENTS forbids real money before L6; do not silently interpret L5 as LIVE
permission. Risk effect comes from attributable exposure proof. A fixture-only
context adapter provides no production readiness. Unknown fee valuation denies new
risk while explicit bounded reduction remains available where venue state permits.

## Completion summary
Pending implementation and mandatory review.

2026-10-03 milestone: 29 deterministic risk cases plus actual OPA HTTP/CLI integration
(36 PASS). HTTPX0.28.1 metadata license is BSD-3-Clause. Local fallback is disabled
by default, hashes binary/code/data and runs the same Rego, reduction only. Network
DENY is never overridden; unsafe/increasing proposals deny during outage. Context
and full authorization are re-evaluated/bound; expiry uses earliest source lifetime.
Legacy RiskDecision.v1 remains unchanged; new RiskEvaluationDecision.v1 explicitly
represents unknown drawdown/exposure, avoiding fabricated zero metrics.


2026-10-03 gate:109 unit/contract tests, actual OPA38, actual platform/ledger17,
actual market/risk13, mypy31,76 schemas, source scan and wheel/sdist. Cancellation
maintenance binds original intent/client ID; LocalProtectivePolicy verifies same
Rego and pinned OPA binary, owner opt-in required. Internal RiskService accepts only
intent/authenticated actor, validates owner config, journal/head, archive/checkpoint,
service safety facts and persistent owner controls, and emits immutable outcomes.
Config activation SQL history, source identity conflicts and terminal decision
replay are protected. Above-L0/lifecycle claims deny pending verified registries.
Adversarial review/evidence recorded. Advance Phase5; do not repeat this gate.
