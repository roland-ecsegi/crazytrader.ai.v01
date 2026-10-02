# Enterprise Local backbone — Phase 1

Run `make setup check integration`. `check` runs unit/static/schema checks; integration tests skip there unless `CT_TEST_DSN` is set. `integration` starts exact-digest PostgreSQL/NATS on random **loopback-only** ports, runs actual durable delivery/failure tests, then removes fixtures. Docker/event-loop socket access is required; managed restricted sandboxes may need escalation. CI runs both commands.

`storage.py`: typed service-health payloads, content hashes, atomic artifacts/events/outbox, consumer inbox, append-only audit and durable notification delivery metadata. SQL triggers reject history UPDATE/DELETE/TRUNCATE; production restricted roles/DDL denial remain Phase 14, since a schema administrator can disable triggers. Arbitrary financial payloads are rejected until their producer contracts/authority are implemented.

`transport.py`: durable file-backed NATS JetStream, explicit ACK after database commit, stable message dedup IDs and inbox idempotency. Broker ACK before database sent marker may redeliver; no exactly-once claim. Invalid messages are NAKed with bounded retries; after exhaustion an operator must inspect consumer state and replay a corrected/new event. Worker heartbeat expiration makes readiness degraded. Stream retention is seven days/64 MiB; PostgreSQL event history is durable replay truth and the outbox can be reset through an audited future operations workflow. Do not mistake this baseline capacity for live certification.

`notification.py`: local console alert sink, event-ID-only logging, durable failed attempts and three-attempt cap. No email/webhook is sent by cloud work. Delivery may repeat after a crash; sinks must deduplicate event IDs. Exhausted failures stay unhealthy pending owner-local operational repair. External delivery adapters remain future notification integration work.

`control.py`: public `/live`; owner bearer auth on `/ready`, `/metrics`, `/certification`. Readiness requires database, JetStream, delivery health and fresh audit/outbox/notification heartbeats. Error responses omit configuration/exception text. Certification is explicitly L0/live disabled; no orders/configuration mutation endpoint exists yet.

`runtime.py`: role selected via `CT_SERVICE_ROLE`; one role per process; database and NATS failures stop rather than silently use memory. Container restart policy restarts workers; heartbeat expiry reports stalls. OpenTelemetry spans instrument storage/consumption; production exporters/collection are Phase 15. Prometheus exposes authenticated readiness/auth-denial metrics. Tracing does not capture credential config.

See [developer deployment](../../infra/PLATFORM_DEVELOPMENT.md) and [Phase 1 plan](../../docs/plans/2026-10-02-phase-1-platform.md). Production TLS, NATS per-service authorization, database least-privilege credentials and OpenBao are mandatory later gates. No live exchange path exists.
