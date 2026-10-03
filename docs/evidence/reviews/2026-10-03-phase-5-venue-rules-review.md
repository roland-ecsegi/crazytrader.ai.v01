# Phase5 complete venue-rule adversarial review

Separate root pass, not human/separate-model approval; no Phase5 gate or L6 claim.

Full unsigned exchange-info source is preserved/read-back checked before operational
receipt. Metadata hash includes the full selected raw symbol, source hash includes the
complete response, and tenant-bound receipt prevents cross-tenant canonical-key reuse.
Strict precision/spot flags, unique symbol/filter identities and financial strings reject
coercion. Unknown/new filter fields deny dispatch; LOT_SIZE and MARKET_LOT_SIZE are
separate, disabled zero values explicit, notional market flags and average windows exact.
Missing account order/position proofs deny relevant constraints. Only MARKET/no submitted
price/no iceberg/algo/list/amend is in this helper's scope.

Repairs from review: tenant added to receipt identity; conflicting same-time publications
reject; quotePrecision bool rejected; negative BUY position projection rejected; newest
source timestamp cannot refresh older raw proof; raw S3 tamper detected. Execution now
requires the full matching receipt before reservation and again before one-send claim.
Source/config writes serialize with the tenant journal lock. Legacy prepared rows with no
rule reference remain unqualified; no retroactive grant. Restarted execution must configure
its source store. Cancellation/query settlement remain independent of market-rule freshness.

No five-minute average is manufactured from a last trade: current reference supports
window0 only; other average windows and real venue account limits require sourced data
before dispatch. Actual public BTCUSDT capture recognizes all11 current filters, quote
precision8; this does not supply missing account/average authority or certify elapsed time.
Production publisher roles/attestation are still Phase14. Actual venue quote amounts,
fee/currency/buffer accounting and complete account reconciliation remain pending.
