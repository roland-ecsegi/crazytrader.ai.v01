# Testing and Certification V1

## Principle

Working code or a strong backtest is not real-money certification. Certification is cumulative evidence.

## Test layers

### Unit
Domain rules, decimal math, state machines, risk calculations, schemas.

### Contract
Service APIs, events, TradeIntent, RiskDecision, PolicyDecision, exchange-normalization contracts.

### Integration
PostgreSQL, ClickHouse, NATS, OPA, OpenBao, MLflow, object store, test exchange interfaces.

### Simulation
Order lifecycle, partial fills, cancellation, latency, slippage/cost model, gaps and portfolio accounting.

### Failure / chaos
At minimum:
1. network timeout after venue may have accepted order;
2. venue error after local state transition;
3. WebSocket disconnect/sequence gap;
4. duplicate NATS delivery;
5. service restart during open order;
6. reconciliation mismatch;
7. PostgreSQL outage;
8. NATS consumer restart;
9. Claude/provider unavailable;
10. Hard Risk unavailable;
11. OPA unavailable;
12. OpenBao unavailable;
13. clock skew;
14. stale market data;
15. attempted new risk during degraded state;
16. authorized risk reduction during degraded state;
17. duplicate fill/event replay;
18. secret-redaction failure injection.

## Mandatory UNKNOWN-order scenario

Expected:
- state becomes UNKNOWN;
- no blind retry;
- reconciliation queries venue with stable identifiers;
- existing order recovered if present;
- safe retry only after absence is established and intent remains valid;
- all transitions audited;
- no duplicate exposure.

## Mandatory AI outage scenario

With an open position and Claude unavailable:
- Hard Risk remains active;
- reconciliation remains active;
- deterministic protective logic remains active;
- no new AI-dependent opportunity is created unless separately certified deterministic strategy permits it;
- agent/provider degradation is recorded.

## Certification ladder

### L0 DEVELOPMENT
No readiness claim.

### L1 BACKTEST READY
Reproducible dataset/config, realistic fee/slippage assumptions, leakage controls, immutable artifact and repeatable results.

### L2 SIMULATION READY
Event-driven order/portfolio simulation with failure/restart and accounting evidence.

### L3 PAPER READY
Real-time market data, simulated execution, live risk/ledger/audit, stable continuous operation.

### L4 SHADOW READY
Live venue/account observation where permitted, real TradeIntents, no live order submission, reconciliation and execution-estimate validation.

### L5 CANARY AUTHORIZED
Live path technically ready; withdrawal disabled; Hard Risk/OPA/kill/reconciliation/monitoring healthy; tiny owner-defined capital cap; incident/runbooks ready; explicit owner authorization.

Actual canary trades are executed only on the owner-controlled Enterprise Local deployment.

### L6 LIVE CERTIFIED
Requires real canary evidence meeting predefined criteria; no unresolved critical execution/reconciliation/ledger/risk/security defects; duplicate-order/recovery/kill-switch evidence; monitoring/backups/runbooks verified; explicit owner live activation.

## Observation-time honesty

Do not fabricate elapsed-market evidence or claim unobserved regimes. Paper/shadow/canary stages consume real time. Continue independent engineering while time-based evidence accumulates.

## Completion truth

Missing owner credentials/activation => BLOCKED at L5/L6, not complete.

## Capital ramp

Stepwise, reversible, owner-capped and evidence-based. Exact amounts are configuration, not a profit-guarantee mechanism.
