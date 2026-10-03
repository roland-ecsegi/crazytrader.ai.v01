# Portfolio accounting primitives

Immutable Portfolio registration in `crazytrader_ledger.store` isolates tenant and
MATH/STRATEGY/RESERVE modes. Journal-backed snapshots distinguish available funds,
order reservations, inventory, per-asset fees and total held quantities. Exact
fill attribution/weighted-average cost reconstruction is a read view with explicit
valuation provenance and unknown third-asset conversion handling.

Internal allocation transfers cannot overdraw the source portfolio. These primitives
are not autonomous growth or owner-limit authorization: Hard Risk/OPA and the
Capital Growth phase compose those rules. No live funding, order or owner-bypass
endpoint is exposed.
