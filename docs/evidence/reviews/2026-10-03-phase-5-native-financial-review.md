# Native financial adapter adversarial review

Separate root source pass after implementation, not human or separate-model review.

Reviewed financial provenance, native ID scope, immutable admission/source equality,
actual cash/commission precision, ledger union compatibility, transaction boundaries,
unknown-state recovery, account backend fences, direct SQL bypass and alert duplication.
Corrections: replaced source-only placeholder denial with deferred source/journal/state
completion constraints; checked actual native cash against controlled postings and
source assets/portfolio; prevented forged reservation completion; source receipt SQL
uses NULL-safe original binding; included native incident and pending state in final
claim safety hash; alert identity excludes restatement clock. Real fault cases verify
rollback/reserve retention and restart without engine resubmit.

Residual scope: one modeled SELL/MARKET, not independent elapsed account/certification;
unsupported native precision remains unavailable; initial funded base cost unknown;
controlled absence/incident resolution pending. No Phase5 gate. Future above-L0 BUY
execution must use the verified certification registry and explicit currency/fee caps.
