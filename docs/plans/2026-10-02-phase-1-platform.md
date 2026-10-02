# Phase 1 ExecPlan — Platform backbone

## Goal
Durable PostgreSQL event/outbox/inbox audit, NATS JetStream transport, notification delivery state, owner-authenticated health/control API and baseline telemetry. Prove redelivery/restart/outage behavior with real local dependencies.

## Non-goals
No exchange/financial order path or certified trading. No external email/webhook dispatch in cloud tests. No SaaS.

## Architecture context
SERVICE_CONTRACTS, DATA_AND_LEDGER, EVENT_CATALOG, LOCAL_DEPLOYMENT and AGENTS.md. Critical consumers assume at-least-once delivery. Authenticated service identities and owner-local secrets; no cloud live credentials.

## Current state
Phase 0 published b610027. Phase 0.5 probes in progress; Phase 1 cannot be declared passed before its adoption gate. PostgreSQL/NATS exact digest candidates available.

## Proposed design
Psycopg PostgreSQL transactions: immutable content-addressed artifact/event records, unique event IDs, transactional outbox and consumer inbox. NATS adapter uses explicit durable stream and bounded publish; mark sent only after acknowledgment. Durable audit uses event inbox to make duplicate delivery idempotent and rejects changed content under same ID. Notification outbox uses bounded delivery states; configured sink failures remain observable. FastAPI owner bearer authentication, no mutation/trading endpoints, public liveness and authenticated readiness/metrics/certification. OpenTelemetry spans and Prometheus health counters.

## Files and ownership
packages/platform: shared configuration/storage/events; services/audit and notification: consumer modules; apps/control-api: HTTP entrypoint. infra/migrations: additive PostgreSQL DDL; tests/platform: real database/NATS integration and HTTP authentication. Core contracts evolve only where a typed operational payload is needed.

## Dependencies and licensing
FastAPI MIT; Uvicorn BSD-3-Clause; psycopg LGPL-3.0 (unmodified dynamic dependency; replaceable DB wrapper); nats-py Apache-2.0; Prometheus client Apache-2.0; OpenTelemetry Apache-2.0; httpx BSD-3-Clause for test transport. Exact selected versions and hashes in uv.lock. Platform image license hashes in Phase 0.5 evidence; these do not establish CVE clearance.

## Failure modes
Database/NATS down: unhealthy, outbox retained, no success claims. ACK-before-mark crash may redeliver, inbox prevents duplicate mutation. Duplicate ID changed bytes is rejected. Alert sink failures persist attempts/error category without sensitive exception text. No readiness => no future new financial authority. API errors never leak DSN/token values. Risk-reduction execution is future below-boundary work independent of this API.

## Security and financial-risk impact
No exchange credentials. Tenant/source identifiers are explicit but not SaaS isolation claim. Owner token required for operational topology. Do not log token/DSN/raw content. Production least-privilege SQL roles/TLS are Phase 14 gate; development fixtures are loopback only.

## Data/event migrations
Initial transactional tables with append-only triggers for audit/artifacts/events, unique inbox identity, and mutable outbox delivery metadata. Migration idempotent; future versioned changes additive. No prior database state.

## Implementation steps
- [x] Finish Phase 0.5 gate and checkpoint.
- [x] Implement initial DDL and storage/outbox/inbox.
- [x] NATS transport and audit/notification consumers.
- [x] Control API/health/telemetry and reproducible dev runtime.
- [x] Real dependency integration/failure tests, review and checkpoint.

## Test plan
make check; isolated loopback PostgreSQL/NATS integration tests via infra test harness; FastAPI TestClient auth/error redaction. Explicit verify event replay after worker restart, collision denial, outbox retention on broker failure, notification delivery failure/retry, append-only SQL rejection and dependency outage readiness.

## Acceptance criteria
All delivered responsibilities above with actual integration evidence; no mock presented as runtime proof; all checks PASS and independent failure review repaired. L0 unchanged.

## Rollback/recovery
Stop workers; preserve persistent event/audit tables; revert application version. Do not drop durable production data. Test fixture volumes disposable. Retained outbox replays idempotently after restart.

## Resume checkpoint
Branch codex/enterprise-local-autonomous; last durable 8de8c80231f91208529c82d29f49d7c1c76327fc (Phase 1 published). Current: Phase 1 gate passed. Next: Phase 2 ExecPlan and normalized market freshness/data ingestion. Uncommitted: checkpoint only. Blockers: none. Usage: active. Verification: Phase 1 local checks/integration/build/actual runtime smoke PASS; hosted CI run 37068956651 PASS.

## Progress log
2026-10-02: designed transactional persistence and service responsibility boundaries.

## Decisions
Durable audit/notification state comes before convenience UI. Runtime must not silently downgrade to in-memory/SQLite when PostgreSQL or NATS is unavailable.

## Completion summary
PASS. Shipped PostgreSQL transactional artifacts/events/outbox/inbox/audit/alert state, durable JetStream adapter, console notification worker with failure state, freshness-aware health API, auth/metrics/spans, explicit migration, non-root image and loopback/internal Compose. 44 unit/contract tests pass; 8 actual integration tests plus API test pass; actual Compose smoke passes migration/auth/UID/worker-stop/restart. Adversarial self-review repaired heartbeat blindness, copied source permissions and internal-network port publishing. No external alert adapter, production TLS/SQL/NATS role isolation, backup readiness or live authority claim. Next Phase 2.
