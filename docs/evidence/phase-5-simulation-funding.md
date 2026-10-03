# Phase5 modeled funding and mature simulation baseline

L0, no execution authority/certification/Phase5 gate. SimulationCostProfile declares
configured assumptions, not verified Binance fees. BuyFundingPlan requires matching
quote/budget/portfolio currencies, tenant-bound full venue receipt and cost-profile
SHA. It ceilings slippage-buffered notional and quote fee separately at venue quote
precision, checks fee-inclusive cap and rejects unsupported third-asset fee funding.
The library does not grant risk/policy/certification or dispatch permission; actual
ExecutionStore BUY remains denied at L0.

Five new unit regressions PASS; actual quote journal3 cases PASS (1.70s): modeled
reserve13.38003334, actual quote+fee13.34333333, remainder0.03670001 returned to original
cash; repeated reserve/release do not duplicate; no execution request exists.
155 repository tests/mypy47/114 schemas/scan/offline SDK/wheel-sdist PASS.

Pinned unmodified dynamically imported Nautilus1.221.0 restored. Offline baseline
infra/spikes/python/simulation.py uses fixed modeled quotes and its instrument
fixture fee0.001. Two native engine runs produce identical financial facts: one
stable-ID SELL0.100000 at100.00, native commission0.01000000 USDT; native covered
cash balances BTC0.9 and USDT109.99 from BTC1/USDT100. Native event UUIDs remain
captured and are not mistaken for financial divergence. Raw native events retained
in docs/evidence/spikes/nautilus-simulation.json. No venue transport is configured.

This is a mature-engine baseline, not completed durable execution/ledger integration.
Next: native simulation source contracts, durable job/result boundary and journal
adapter/restart proofs; preserve native provenance rather than pretending native
fills are Binance SDK observations. Above-L0 assertions and live boundary stay denied.
