# ADR-0003 — Risk Direction and Emergency Reduction

Status: Accepted

## Context

A fail-closed system that denies every order during degraded state can accidentally trap an open position.

## Decision

TradeIntent explicitly classifies RISK_INCREASING, RISK_REDUCING or RISK_NEUTRAL.

Unknown/degraded safety state denies new risk by default while preserving a deterministic, policy-governed path for cancellation and exposure reduction where venue state permits.

## Consequences

Risk/OPA/execution tests must separately validate increase and reduction behavior. Global Kill policy must specify cancel-only vs flatten-approved semantics.
