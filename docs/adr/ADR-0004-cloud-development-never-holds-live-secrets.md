# ADR-0004 — Codex Cloud Never Holds Live Trading Secrets

Status: Accepted

## Context

Codex Cloud builds/tests the product, while Enterprise Local later manages real funds.

## Decision

Codex Cloud never receives Binance live credentials, owner Claude subscription auth/session material, or OpenBao bootstrap/unseal secrets.

Final Claude local-auth and Binance canary/live validation occur on the owner-controlled deployment.

## Consequences

Cloud tests use mocks/testnet/non-secret configuration. L5/L6 may legitimately block for a minimal owner-local setup action.
