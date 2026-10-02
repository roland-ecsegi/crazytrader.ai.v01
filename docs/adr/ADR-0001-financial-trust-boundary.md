# ADR-0001 — Financial Trust Boundary

Status: Accepted

## Context

CrazyTrader.ai intentionally uses LLMs and autonomous agents. These components are powerful but nondeterministic and may produce incorrect output or become unavailable.

The platform will eventually manage real money.

## Decision

LLMs and agents remain above a strict financial trust boundary.

They may:

- analyze;
- research;
- propose;
- explain;
- create TradeIntent proposals.

They may not:

- bypass hard risk;
- bypass policy;
- directly use Binance secrets;
- directly submit live orders.

Below the boundary, safety-critical financial behavior is implemented through deterministic services:

- schema validation;
- certification enforcement;
- Hard Risk Engine;
- OPA;
- execution;
- reconciliation;
- ledger;
- kill switches.

## Consequences

Benefits:

- AI can evolve without becoming the final financial authority.
- Claude outages do not disable core safety.
- model changes do not require redesigning execution safety.
- live behavior is more auditable.

Costs:

- more services and contracts;
- extra latency;
- more engineering effort.

The additional complexity is accepted because it protects the real-money system.
