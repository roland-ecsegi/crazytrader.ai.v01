# Phase5 bounded account reconciliation milestone

L0, no Phase5 gate, certification grant, owner credential, Binance connection or
new execution permission. Reads use the isolated official SDK with fixed dummy auth
and literal loopback SIMULATION SELL anchor. SOURCE/REPORT contracts are additive.

The reader captures before/after account balances and permission flags, all open
orders and configured/registered symbol histories. Order/fill pages begin at ID0,
advance monotonically, require a short final page, cap1000 rows/page and20 pages.
An incomplete source is unavailable, never fabricated empty history. Partial SDK
truth survives a later read failure. Source rows commit before comparison, including
interruption/concurrent-state cases; full financial strings remain immutable.

Comparison binds tenant/account/request, current registered states and journal/config
heads; detects concurrent internal changes, changing venue snapshots, unsupported
account scope, withdrawal/trading permission, aggregate controlled-asset balances,
unowned/open/recent orders, order state/quantity, canonical posted fills/fees/time,
cumulative quote quantity, per-order reservation and cost-attribution provenance.
Equal total balances cannot conceal under-reservation or incorrect quote totals.
SELL from externally funded inventory without acquired cost provenance explicitly
fails attribution; no fictional cost/PnL is supplied.

Typed reports have certification_effect NONE. Mismatch/unavailable/comparison failure
latches healthy-risk assertions, preparation and already-prepared claim safety.
Typed audit/critical notification accompanies mismatch; cancellation remains independent.
Reports never automatically clear historical incidents; controlled resolution pending.

Validation: full50 actual combined cases PASS (219.07s), then nine final account cases
PASS (50.55s), actual platform/ledger17 PASS (7.92s),150 units/mypy45/110 schemas/scan/
offline SDK PASS. Final10 account cases PASS (53.17s); subsequent unchanged-fault alert repair: ten
other cases PASS (58.10s combined run), repaired dedup case PASS (7.76s). Every
receipt remains audited; one critical alert for unchanged fault. Final150 units/
mypy45/110 schemas/build PASS.
Wheel/sdist PASS; final publication checks recorded in STATUS.

Scope limits: fixture histories prove bounded fixture coverage. Real Binance history
retention and owner-local cursor/discovery/bootstrap are not certified by fixture ID0
pagination. Multiple venue accounts sharing one tenant journal are rejected. BUY
reservation/fee buffers and unknown funding cost remain explicit dependencies. No
controlled absence retry or production account-health assertion is granted.
