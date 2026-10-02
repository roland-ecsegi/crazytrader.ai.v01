# Testing and Certification V1

Working code/backtests are not real-money certification.

Test layers: unit; schema/contract; integration; simulation; security; failure/chaos; restart/recovery; idempotency; data-quality; supply-chain/license checks.

Mandatory failures include lost order response/UNKNOWN state, WebSocket gap, duplicate NATS delivery, service/DB/NATS restart, reconciliation mismatch, Claude unavailable, risk/OPA/OpenBao unavailable, clock skew, stale data and attempted risk increase during degraded state. Also prove authorized risk reduction/cancellation remains available in intended degraded modes.

## Ladder

**L0 DEVELOPMENT** — no readiness claim.

**L1 BACKTEST READY** — reproducible data/config, realistic costs, immutable artifact, leakage controls, repeatable result.

**L2 SIMULATION READY** — event-driven orders/portfolio, partial fills/cancel/latency/failure/restart simulation.

**L3 PAPER READY** — real-time data, simulated execution, real-time risk/ledger/audit, stable continuous operation.

**L4 SHADOW READY** — live market/account observation where permitted, real TradeIntents, no live orders, reconciliation and execution-estimate validation.

**L5 CANARY AUTHORIZED** — live path technically ready; withdrawal disabled; hard risk/OPA/kill/reconciliation/monitoring healthy; tiny owner-defined cap; incident/runbooks ready; explicit owner authorization. Actual bounded canary runs on owner-controlled Enterprise Local deployment, never Codex Cloud.

**L6 LIVE CERTIFIED** — real canary evidence accepted; no unresolved critical execution/reconciliation/ledger/risk/security defects; duplicate-order/recovery/kill evidence; monitoring/backups/runbooks verified; explicit owner activation.

Do not fabricate elapsed-market evidence. Paper/shadow/canary require real observation. Codex may continue independent engineering while evidence accumulates.

Missing owner live credentials/activation means BLOCKED at the relevant L5/L6 gate, not Enterprise Local complete.

Capital increases are stepwise, reversible, owner-capped and evidence-based.
