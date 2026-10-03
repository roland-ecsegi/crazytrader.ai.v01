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
source assertions deny pending verified certification registry. Selected native simulation and SDK fixture adapters implemented during Phase5.

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
- [x] Atomic durable reservation/authorization and stable request/client identities (protective SIMULATION and mixed custody verified; modeled BUY fee buffers verified, execution authority remains denied at L0).
- [x] Internal unmodified native simulation financial adapter and official SDK fixture accepted-timeout/restart proof.
- [x] Pre-T016 review; fixture query-open recovery, partial fills/cancel/suspense incidents and owned cancellation. Bounded source-first fixture account comparison verified; controlled recovery/resolution pending.
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
Phase5 SDK milestone published at6e23475; canonical settlement and final source
review repairs PASS. Owned cancellation and complete venue-rule dispatch enforcement verified. Next exact
action: source-bound elapsed-window absence release/controlled retry. Original
send deadline/guard binding and fixture acceptance/read linearization verified, and append-only incident resolution. Bounded signed fixture
absence assessment has no financial effect.
Unsent expiry verified. Native
job/request binding, financial journal/state/incidents, worker/source and restart
proof verified. Modeled
funding and unmodified Nautilus baseline verified. Bounded fixture account
comparison and mixed custody verified. Above-L0 source/certification assertions stay denied. Actual quoteQty
accounting and cost attribution implemented with additive contracts. Current certification L0; no Phase5 gate.

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


2026-10-03 official SDK recovery milestone: fixed dummy-auth literal-loopback child
uses the already locked Spot SDK3.0/common3.2 without float conversion or automatic
retry. SDK-generated float annotation accepts exact decimal string; actual wire
0.100000000000000001 PASS. It cannot inherit owner credentials, accept live modes,
target Binance or follow redirects. Accepted-before-timeout fixture commits venue
truth in real PostgreSQL; UNKNOWN records preserve reservation and duplicate delivery
cannot send again. Query after both object/HTTP restart finds one stable order;
query-only reconciler recovers ACKNOWLEDGED, not full-account health. No-order query
stays RECOVERY_REQUIRED, no retry/release. Receipt persistence interruption likewise
recovers one existing order. Typed source action SUBMIT/QUERY and exact account/request
hash bind immutable observations.22 actual combined-store/SDK tests PASS;115 units,
mypy38,84 schemas, scan/SDK offline/wheel-sdist PASS. Pre-T016 review recorded before
reconciliation implementation. Next: canonical fill batches, exact atomic accounting,
cancel remainder, suspense and incident containment. Actual SDK redirect-to-second-server test PASS (no follow/no credential forwarding). No phase gate/live certification.


2026-10-03 settlement milestone: canonical scoped fill identities and immutable raw
source/query proof; atomic partial/full accounting and proven cancel remainder release;
savepoint preserves suspense/incidents on unowned fee/conflict; incident latches risk and
claim authority.28 actual combined tests PASS before final raw-source tamper hardening;
115 units/mypy39/90 schemas PASS. Review and scope in docs/evidence/phase-5-fill-settlement.md
and reviews/2026-10-03-phase-5-settlement-review.md. Final hardened actual28 tests PASS (71.76s),8 source-contract regressions PASS;
pinned image build/non-root import and wheel/sdist PASS. Compose smoke failed during
disk exhaustion; no new runtime smoke claim. Targeted cache cleanup restored5.7GB. No Phase5 gate; continue cancellation and actual quote/fee semantics.

2026-10-03 cancellation milestone:35 actual combined tests PASS (119.44s),123 unit
tests/mypy40/94 schemas and wheel/sdist PASS. Seven current-policy/ownership/duplicate/
timeout/crash/audit/fill-race/incident cases. SDK fixture cryptographic HMAC validation.
Evidence/review in phase-5-cancellation.md and reviews/2026-10-03-phase-5-cancellation-review.md.
Settlement hosted CI37124294645 PASS. Continue complete venue rules/actual quote amounts,
BUY fee buffers/mixed custody/full account reconciliation/selected simulation before gate.

2026-10-03 venue rules: complete unsigned SDK source capture and tenant-bound immutable
receipts;13 rule regressions PASS,136 repository tests/mypy42/98 schemas/build PASS;
36 actual foundation tests PASS (118.57s). Required matching source before reservation
and final claim now implemented;35 existing financial regressions PASS, source-archive
fixture timestamp collision repaired. Final38 actual tests PASS (120.32s);136 repository tests/mypy42/98 schemas/build PASS. Actual public BTCUSDT
one-shot capture:11 filters/quote precision8, not elapsed or financial certification.
Next actual quote amounts/BUY buffers/full account recovery; review/evidence committed
with this milestone. Cancellation checkpoint8654034 hosted CI37125094475 PASS.

2026-10-03 actual quote milestone:43 actual combined cases PASS (146.04s),17 platform/ledger
PASS (6.06s),142 units/mypy43/106 schemas/build PASS. Original precision receipt, actual
quote cash/fees and legacy/new replay verified. Evidence/review committed; no Phase5 gate.

2026-10-03 mixed custody:44 actual cases PASS (174.04s),147 units/mypy43/106 schemas/build
PASS. One immutable allocation; exact original-source cancel restoration and replay.
Review/evidence committed. Next account-wide comparison; no Phase5 gate.

2026-10-03 account milestone:50 actual combined cases PASS (219.07s), final10 account
cases PASS (53.17s); later alert repair ten unchanged cases PASS, fixed dedup case
PASS (7.76s). Platform/ledger17 PASS (7.92s),150 units/mypy45/110 schemas/build PASS.
Immutable raw partial-source receipts, per-read audit and one critical unchanged-fault
alert; balances/open/history/fills/cumulative quote/reservation/cost comparison.
No certification effect or historical latch clearing. Next simulation costs/mature
Nautilus adapter and controlled recovery; no Phase5 gate.

2026-10-03 simulation funding foundation:155 units/mypy47/114 schemas/build PASS;
actual quote journal3 cases PASS (1.70s). Explicit model/currency/precision/fee cap;
no execution grant. Unmodified Nautilus1.221.0 two-run native financial equality PASS;
raw native source captured. Baseline only, durable financial adapter/recovery next.
Account checkpointff36e635 hosted CI37133706740 PASS. No Phase5 gate.

2026-10-03 native source boundary:162 tests/mypy48/118 schemas/build PASS. Seven
actual isolated native tests; private fsynced claim/result, response-loss recovery,
missing result never reruns, exact source/clock/currency and native precision checks.
No SDK provenance fabrication. Native environment added to CI setup. PostgreSQL
financial adapter/recovery next; no Phase5 gate/certification.

2026-10-03 native registry:60 full actual cases PASS (221.28s), final5 native cases
PASS (10.47s);163 units/mypy49/122 schemas PASS. Owned original request/source
binding, account backend fencing, concurrent dispatch and source recovery after
persistence interruption. Financial-proof placeholder denies inserts; UNKNOWN retains
custody. Evidence/separate root review committed. Next native journal/state/incidents;
no Phase5 gate.

2026-10-03 native financial:69 full actual cases PASS (234.94s). Actual native cash/fee
source, additive journal, deferred PostgreSQL atomic completion, crash/duplicate
recovery and critical incidents. Final13 native cases PASS (27.88s),17 platform/ledger PASS (7.50s),164 units/
mypy51/128 schemas/scan/offline SDK/wheel-sdist PASS; no Phase5 gate. Next unsent expiry/controlled absence/resolution.

2026-10-03 unsent expiry:7 actual cases PASS (6.10s),169 units/mypy53/130 schemas
PASS. Original custody, duplicate/race, unknown retention, native admission expiry
and source/proof/audit rollback. Final36 affected cases PASS (98.62s),17 platform/ledger PASS (6.79s), scan/offline
SDK/wheel-sdist PASS. Next controlled absence/retry and append-only incident resolution;
no Phase5 gate.

2026-10-03 fixture absence source: initial6 actual cases PASS (31.36s), standalone
signed lookup PASS (8.48s). Raw source first, complete account comparison, unchanged
scope/head and pending SDK/native health fences. No financial effect. Source review
identified original-send/late-acceptance fence required before release/retry; implement
next, no Phase5 gate. Full83 passes (285.88s) and one fixture identifier failure;
repaired final8 PASS (34.99s),175 units/mypy55/134 schemas/scan/offline SDK/build,
17 platform/ledger PASS (6.27s).

2026-10-03 guarded dispatch: actual prepared-request deadline and signed5000ms window,
immutable reviewed-source bound before claim, Python/SQL evidence fence and exclusive
backend choice. Original late sender stays UNKNOWN/no wire; legacy requests are not
backfilled.22 repaired cases PASS (66.83s),20 final fill/deadline/SDK PASS (111.11s),
178 units/mypy56/138 schemas/scan/offline SDK PASS,17 platform/ledger PASS (11.89s).
Final90 actual cases PASS (302.24s), wheel-sdist PASS; no financial release/retry or gate.
