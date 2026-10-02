# Strategy and Model Lifecycle V1

Agents may research continuously; no unvalidated artifact reaches live capital.

Lifecycle:

DRAFT -> BACKTESTED -> VALIDATED -> OUT_OF_SAMPLE -> WALK_FORWARD -> PAPER -> SHADOW -> CANARY_ELIGIBLE -> LIVE.

Post-live: LIVE -> DEGRADED -> SUSPENDED -> RETIRED. Rollback may reactivate a previously validated immutable version when policy permits.

Validation includes realistic costs/liquidity, look-ahead leakage controls, train/validation/test separation, regime performance, overfit/parameter stability, drawdown/tail loss, execution realism and full data/config lineage. Use time-series purging/embargo or equivalent when appropriate.

Promotion records immutable artifact hash, dataset/features/config versions, metrics/evidence, risk review, policy decision and audit event. Research agents propose; they do not self-authorize.

Executed trades create provenance-rich ExperienceRecords. Learning can generate hypotheses/candidates. Certified artifacts never mutate silently. Adaptive live updates require bounded/versioned/auditable rules and rollback.

Deterministic monitoring may reduce allocation or suspend degraded artifacts while preserving safe position reduction/closure.
