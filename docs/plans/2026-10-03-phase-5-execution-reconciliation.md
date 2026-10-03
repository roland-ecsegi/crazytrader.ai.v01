# Phase5 ExecPlan — Execution and reconciliation

## Goal
Build durable explicitly authorized order state, stable IDs, simulation/test adapter,
partial fills/cancel accounting and UNKNOWN recovery with audited duplicate protection.

## Non-goals
No live orders/credentials, external owner authentication, fabricated certification,
LLM order tools, blind retry or unmodified Nautilus Binance timeout behavior.

## Architecture context
AGENTS, EXECUTION_AND_RECONCILIATION, TRADE_INTENT, DATA_AND_LEDGER,
TESTING_AND_CERTIFICATION, Phase4 gate; mandatory pre-T014 review recorded.
Mandatory pre-T016 separate review before reconciliation implementation.

## Current state
Phase0–4 foundation implemented at L0. Immutable journal, market archive/checkpoint,
owner config, typed risk/policy evidence and internal trust boundary exist. Above-L0
source assertions deny pending verified certification registry. No order adapter.

## Proposed design
Contract-first explicit state/observation/ownership evidence, append-only transition
history and transactional current pointers. Stable client ID from immutable request.
Only persisted policy+risk evidence with current state can authorize; serialization
and ledger reservation are atomic. Adapter interface internal only; simulation
provides deterministic venue truth and fault injection. Unknown retains reservation
and blocks duplicate send. Reconciliation proves venue identity/fills/absence before
controlled recovery. Execution permission is never a boolean in model output.

## Files and ownership
packages/contracts execution; packages/execution internal service/store/adapter;
services/execution/reconciliation entrypoints; additive migrations; tests/execution;
actual PostgreSQL integration harness, schemas, evidence/review/status.

## Dependencies and licensing
Reuse pinned psycopg/Decimal/Pydantic/OPA/event platform and dynamically integrated
unmodified Nautilus1.221 simulation candidate (LGPL boundary in compatibility ADR).
Any rejection/alternative needs recorded evidence. Official signed test adapter
remains isolated owner-local boundary. No unreviewed additional package.

## Failure modes
Duplicate intent/clientID, crash before/after send, accepted timeout, ambiguous error,
stale approval/current state, competing reservations, partial fill duplicate, cancel
race, venue identity mismatch, missing fills, outage/restart and clock skew.

## Security and financial-risk impact
Below financial trust boundary; only execution may reach adapter. Simulation cannot
be mistaken for LIVE. No API/agent direct order access; current LIVE guard enforced.

## Data/event migrations
Immutable execution request/transition/fill observations, mutable constrained pointer,
idempotency keys and outbox in same transaction as reservation/accounting effects.

## Implementation steps
- [x] Read durable Phase4 gate and pre-T014 adversarial review.
- [x] Typed states/requests/venue observations and deterministic transition rules.
- [x] Atomic durable reservation/authorization and stable request/client identities (protective SIMULATION milestone; BUY/mixed custody still pending).
- [ ] Internal selected simulation adapter and accepted-timeout/restart proof.
- [ ] Pre-T016 review, reconciliation/partial fills/cancel/suspense incidents.
- [ ] Full negatives/chaos, adversarial repairs, evidence, publish and advance Phase6.

## Test plan
make check/integration; actual PostgreSQL concurrency/restart/fill-replay; deterministic
fixture timeout accepted -> UNKNOWN -> query recovered with one submission; malformed
venue ID/not-found ambiguity; no live/expired/changed/forged authority; exact accounting.

## Acceptance criteria
No duplicate exposure under delivery/restart/timeout; unresolved states block new
risk; reservations/fills/cancel account exactly; independent protective path; truthful
simulation scope, owner-local test/live validation explicitly deferred if unavailable.

## Rollback/recovery
Stop new submissions, retain reservations/immutable history, reconcile unresolved
stable IDs. Never reset SUBMITTING to CREATED or release unknown funds on rollback.

## Resume checkpoint
Phase4 gate publication pending. Next exact action: typed execution state machine
and durable request contract before implementing the adapter. Current certification L0.

## Progress log
2026-10-03: Phase4 completed; pre-T014 review recorded, Phase5 prepared.

## Decisions
Preserve LIVE L6 owner guard. Native Nautilus Binance submission remains deferred
until its ambiguous-error semantics can meet UNKNOWN invariant. Missing venue auth
must not prevent independent simulation/reconciliation engineering.

## Completion summary
Pending implementation.


2026-10-03 coordination milestone: explicit contracts/state transitions and canonical
stable client IDs; shared LedgerStore.append_in_transaction, durable request/transition
history and CAS pointer; tenant serialization, source/config/checkpoint recheck and
atomic protective simulation reservation. One SUBMITTING claim only, startup maps
interrupted send to UNKNOWN and retains funds. Actual OPA/journal/source17 tests
(4 execution) plus platform/ledger17 PASS.114 unit/contract tests, mypy35,82 schemas,
source scan, wheel/sdist PASS. No transport, reconciliation, partial-fill settlement,
BUY cost buffer, mixed custody or Phase5 gate claim. Next exact action: isolated
mature official-SDK fixture-only signed POST/query with accepted-then-timeout, then
mandatory pre-T016 review and canonical recovery/accounting. Phase4 remote722a914,
hosted CI37116292477 PASS.
