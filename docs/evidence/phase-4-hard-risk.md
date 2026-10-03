# Phase4 Hard Risk and OPA gate

Scope: deterministic typed evidence, bound Rego authorization, dedicated protective
reduction/cancel policy, internal trusted-state boundary and immutable audit. L0.
No exchange submission, owner credentials, continuous-market or live certification.

Validation (2026-10-03):
- make check:109 unit/contract/API tests PASS; actual-dependency tests skip explicitly;
  strict mypy31 modules, Ruff,76 schema artifacts, source scan, isolated official SDK
  nested serialization/unsigned signatures PASS. Wheel/source build PASS.
- actual OPA1.8.0 adopted digest:38 deterministic/policy/cancel tests PASS, including
  HTTP and hash-verified local CLI, network outage, malformed replies, permission,
  symbol/expiry, forged authorization, LIVE L0/L5 denial and protective path.
- actual PostgreSQL/NATS regression:17 tests PASS (8 ledger, platform/API).
- actual PostgreSQL/ClickHouse/Seaweed market/risk integration:13 tests required PASS;
  journal/archive provenance, restarted reader, duplicate audit/replay, changed state,
  source identity collision, stale proofs, forged metrics, configuration activation
  history, certification assertion, terminal intent immutability and outage denial.

Risk approvals carry exact intent/context/limits hashes and source-bounded expiry.
Policy approvals bind full risk evidence and verified code digest. Missing/invalid
OPA denies; owner-opted local same-policy path grants only bounded reduction/cancel.
RiskService reloads internal state and owner permissions, accepts no raw context from
agents, and persists audit/outbox before returning. Boundary failures emit sanitized
RiskDecisionDenied evidence without manufactured balances or healthy flags.

Trust producers are internal service publishers, not agent APIs. SQL roles/TLS and
artifact signing remain the explicit later security gate. Lifecycle and above-L0
claims deny until verified registries. Allocation reference validation integrates
with the later capital registry. Final execution rechecks and reservations are Phase5.

Review: docs/evidence/reviews/2026-10-03-phase-4-gate.md. Future L5/L6 authority conflict
remains documented; invariant10 enforced. Foundation engineering gate is not L6.
