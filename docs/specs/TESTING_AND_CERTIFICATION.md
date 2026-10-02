# Testing and Certification V1

## Principle

Passing unit tests does not make the platform real-money ready.

Certification is a cumulative evidence process.

## Test layers

### Unit

Required for:

- domain rules;
- state machines;
- risk calculations;
- policy inputs;
- decimal math;
- schema validation.

### Contract

Required for:

- service APIs;
- events;
- TradeIntent;
- RiskDecision;
- PolicyDecision;
- exchange adapter normalization.

### Integration

Required for:

- PostgreSQL;
- ClickHouse;
- NATS;
- OPA;
- OpenBao;
- MLflow;
- exchange test interfaces.

### Simulation

Required for:

- order lifecycle;
- partial fills;
- cancellation;
- latency;
- market-data gaps;
- execution-cost modeling.

### Failure and chaos

Required scenarios include:

1. Network timeout immediately after order submission.
2. Binance returns an error after local submission state changes.
3. WebSocket disconnect and sequence gap.
4. Duplicate NATS delivery.
5. Service restart during open order.
6. Reconciliation mismatch.
7. PostgreSQL temporary outage.
8. NATS consumer restart.
9. Claude becomes unavailable.
10. Risk engine unavailable.
11. OPA unavailable.
12. Secret store unavailable.
13. Clock skew outside tolerance.
14. Market data stale while a new TradeIntent arrives.

## Mandatory example: unknown order state

Given:

- an approved execution request;
- the HTTP/WebSocket response is lost after the venue may have accepted the order.

Expected:

- order enters UNKNOWN;
- no blind retry;
- reconciliation starts;
- venue is queried using stable identifiers;
- existing order is recovered if present;
- only if absence is proven and the intent remains valid may a safe retry occur;
- all state transitions are audited.

## Mandatory example: Claude failure

Given:

- an open position;
- Claude/AI provider becomes unavailable.

Expected:

- hard risk remains active;
- reconciliation remains active;
- deterministic protective actions remain active;
- no new AI-dependent trades are initiated unless policy explicitly permits an offline deterministic strategy;
- the system records degraded agent status.

## Certification ladder

### L0 DEVELOPMENT

No claim of trading readiness.

### L1 BACKTEST READY

Requires:

- reproducible data/config;
- fees modeled;
- slippage model;
- immutable strategy version;
- repeatable result.

### L2 SIMULATION READY

Requires:

- event-driven order simulation;
- failure-path simulation;
- restart tests;
- portfolio accounting simulation.

### L3 PAPER READY

Requires:

- real-time market data;
- simulated orders;
- real-time risk;
- audit;
- stable continuous operation.

### L4 SHADOW READY

Requires:

- live Binance market/account observation where permitted;
- real TradeIntent generation;
- no live order submission;
- reconciliation checks;
- execution-estimate comparison.

### L5 CANARY READY

Requires:

- live execution path technically enabled;
- withdrawal disabled;
- hard risk active;
- kill switch active;
- reconciliation healthy;
- tiny owner-approved capital cap;
- incident procedures tested.

### L6 LIVE CERTIFIED

Requires:

- canary evidence accepted;
- no unresolved critical execution defects;
- no unresolved critical reconciliation defects;
- duplicate-order protection verified;
- recovery verified;
- kill switch verified;
- monitoring verified;
- explicit owner activation.

## Capital ramp

Capital increase is not automatic proof of safety.

Use controlled steps with explicit policy caps and evidence review.

## Evidence

Each certification level must store machine-readable evidence references and blockers.

The application must refuse live activation below L6.
