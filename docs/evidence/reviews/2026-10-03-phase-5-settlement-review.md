# Phase5 settlement adversarial review

Separate root review pass after implementation, not a human or separate-model review.
No phase gate or certification upgrade.

Findings repaired:
- Terminal cancellation accounting must preserve the exact order-status query in the
  source batch, not just fill JSON; caller-swapped status now fails validation.
- Incident identity must exclude polling clock to avoid repeated critical alerts for
  unchanged unresolved truth; source receipts remain immutable.
- Savepoint rollback must return the original persisted state after local transition
  construction; failed accounting cannot return a fictitious recovered transition.
- Terminal duplicate checks must validate previously posted fill digests to preserve late
  fee conflicts instead of silently discarding known changed venue truth.
- Typed normalized fills must match raw IDs/direction/quantity/price/fee/time, independently
  of transport normalization; altered fee authority is rejected.
- Platform Dockerfile must copy the execution package included in the root wheel.

Open scope is recorded in phase-5-fill-settlement.md and the active ExecPlan. Quote
rounding, full account reconciliation and incident resolution remain engineering work.
