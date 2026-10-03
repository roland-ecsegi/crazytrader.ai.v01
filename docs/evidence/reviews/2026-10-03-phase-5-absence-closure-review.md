# Phase 5 elapsed-window absence closure adversarial review

Separate root-agent source review after implementation, not a separate-model or human review.

Reviewed the full closure contract, guarded SDK source, original binding/claim fence,
source-first assessor, tenant-locked financial transaction and migration017.

The snapshot assessment alone cannot prove absence against an old paused sender.
Closure therefore requires the immutable original protocol binding and its actual
SUBMITTING transition evidence, an exact paired signed lookup, captured HTTP Date
at least six seconds after the original request expiry (5000ms maximum signature
window plus one-second HTTP Date truncation), complete account coverage and an
unchanged internal head. The fixture serializes acceptance and lookup on one lock.
Legacy unbound and native executions cannot use this path. No LIVE venue claim.

Repairs from review: database checks actual original ambiguous transition, strict
negative response code/object shape, original server Date pairing, original bound
claim, zero-fill current state and exact inverse custody. Standalone financial
release must have deferred source/state/custody proof; source hashes alone are
insufficient. Whole financial state and audit/outbox share one transaction.

Initial actual tests: first run had a test setup error (binding API returns no
claim object), corrected. Repaired five cases PASS (36.17s). Expanded run:27 PASS (130.64s), one mixed-custody fixture balance mismatch;
corrected explicit independent venue truth (0.1 BTC after0.9 external transfer),
then final9 actual cases PASS (83.42s), including matching mixed custody, concurrent
closure, missing clock and incomplete account source.

Further review repair: deferred database proof reconstructs the original assessment
head, excluding only its own release and replacing only its target current state
with the actual original ambiguous transition. Any other ledger/configuration/state
change prevents closure. Exact revision advance and closure-bound transition evidence
are required. Final snapshot mutation test is included in the final10 actual cases: PASS (97.37s).
The final deferred proof rejects injected ledger mutation and rolls back both the
extra transaction and custody/state changes. Four additional contract negatives PASS.
No Phase5 gate or certification upgrade. Controlled retry and incident resolution
remain subsequent work.

The first full snapshot-guard run failed at migration setup: PL/pgSQL parsed an
unparenthesized CASE in the IF expression as a procedural CASE. Parenthesized the
SQL expression; no financial execution or PASS claim from that failed run.
Repository final178 PASS (20.23s), platform/ledger17 PASS (7.30s). Repaired final10 actual cases PASS (97.37s). Combined regression follows next work.
