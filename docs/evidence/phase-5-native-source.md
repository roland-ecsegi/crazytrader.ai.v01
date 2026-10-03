# Phase5 isolated native simulation source boundary

L0, no financial adapter completion, certification, Phase5 gate or real venue call.
NativeSimulationJob binds original request/order/client/scope, approved risk reference,
journal head, tenant full rules and explicit modeled costs. NativeSimulationReceipt
retains unmodified Nautilus1.221.0 raw event/cash provenance, distinct from official
SDK observations. It binds one SELL/MARKET fill, exact strings, fee/quote asset,
modeled quote, job nanosecond time, actual cash delta and precision/cost envelope.

Isolated worker constructs an upstream CurrencyPair and BacktestEngine; no venue
execution client or credentials. Starting money/quantity/price conversions must
preserve exact approved Decimal values. Root transport inherits only PATH/SYSTEMROOT
and controlled contract import path/loopback exclusions. Native version pinned.

Durable private claim file is exclusively created, file/directory synced before
worker dispatch. Result is written/synced then atomically renamed and directory
synced before response. A known result is reused after restart/response interruption;
a claim without a result remains unavailable and cannot rerun. Unsupported native
precision likewise stays unavailable, with immutable result/claim. PostgreSQL request
binding and financial settlement are the next increment, not claimed here.

Native environment now included in make setup/CI so actual native boundary tests run
instead of silently skipping. Seven actual isolated-engine cases cover response loss,
restart/no-repeat, claim without result, no precision loss, altered cash, boolean order
count, changed event time and wrong quote currency (some cases parametrized).
Final make check/build results recorded in STATUS. Published existing schemas unchanged.
