"""Transactional event/audit state. Failure never silently falls back to memory."""

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import psycopg
from crazytrader_contracts.events import EventEnvelope
from crazytrader_contracts.models import Contract, Identifier, Timestamp
from opentelemetry import trace
from psycopg.rows import dict_row

TRACER = trace.get_tracer(__name__)


class HealthChange(Contract):
    service_id: Identifier
    health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    reason_code: Identifier
    occurred_at: Timestamp


def canonical(model: Contract) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def digest(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


class ConflictError(ValueError):
    """An immutable identifier was reused with different content."""


class EventStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[dict[str, object]]]:
        with psycopg.connect(self._dsn, row_factory=dict_row, connect_timeout=3) as conn:
            yield conn

    def migrate(self, migration: Path) -> None:
        with self.connection() as conn:
            conn.execute(migration.read_text())

    def healthy(self) -> bool:
        try:
            with self.connection() as conn:
                row = conn.execute("SELECT version FROM ct_migrations WHERE version=1").fetchone()
                return row is not None
        except psycopg.Error:
            return False

    def append(self, event: EventEnvelope, payload: HealthChange) -> bool:
        """Persist payload, event and outbox atomically; reject changed ID content."""
        if event.event_type != "ServiceHealthChanged.v1":
            raise ValueError("Phase 1 supports only typed service-health payloads")
        body = canonical(payload)
        expected = digest(body)
        if event.payload.sha256 != expected or event.payload.artifact_ref != expected:
            raise ValueError("payload reference/hash mismatch")
        if event.payload.payload_schema_ref != "HealthChange.v1":
            raise ValueError("payload schema mismatch")
        if event.source_service != payload.service_id or event.occurred_at != payload.occurred_at:
            raise ValueError("payload/envelope provenance mismatch")
        envelope = canonical(event)
        event_digest = digest(envelope)
        with TRACER.start_as_current_span("platform.event.append"), self.connection() as conn:
            inserted = conn.execute(
                "INSERT INTO ct_artifacts(digest,tenant_id,schema_ref,body) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING digest",
                (expected, event.tenant_id, "HealthChange.v1", body),
            ).fetchone()
            if inserted is None:
                existing = conn.execute(
                    "SELECT body,tenant_id,schema_ref FROM ct_artifacts WHERE digest=%s",
                    (expected,),
                ).fetchone()
                if existing != {
                    "body": body,
                    "tenant_id": event.tenant_id,
                    "schema_ref": "HealthChange.v1",
                }:
                    raise ConflictError("artifact ownership/content collision")
            inserted = conn.execute(
                "INSERT INTO ct_events "
                "(event_id,tenant_id,event_type,digest,envelope,payload_digest) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                (
                    event.event_id,
                    event.tenant_id,
                    event.event_type,
                    event_digest,
                    envelope,
                    expected,
                ),
            ).fetchone()
            if inserted is None:
                row = conn.execute(
                    "SELECT digest FROM ct_events WHERE event_id=%s", (event.event_id,)
                ).fetchone()
                if row is None or row["digest"] != event_digest:
                    raise ConflictError("event ID reused with different content")
                return False
            conn.execute("INSERT INTO ct_outbox(event_id) VALUES (%s)", (event.event_id,))
            return True

    def pending(self, limit: int = 100) -> tuple[EventEnvelope, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("invalid batch size")
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT e.envelope FROM ct_events e JOIN ct_outbox o USING(event_id) "
                "WHERE o.sent_at IS NULL ORDER BY e.created_at,e.event_id LIMIT %s",
                (limit,),
            ).fetchall()
            return tuple(EventEnvelope.model_validate_json(str(row["envelope"])) for row in rows)

    def publish_attempt(self, event_id: str, acknowledged: bool) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE ct_outbox SET attempts=attempts+1, "
                "sent_at=CASE WHEN %s THEN now() ELSE sent_at END WHERE event_id=%s",
                (acknowledged, event_id),
            )

    def consume_audit(self, event: EventEnvelope) -> bool:
        """Verify persisted event and payload, atomically inbox/audit/alert then ACK."""
        with TRACER.start_as_current_span("platform.audit.consume"), self.connection() as conn:
            row = conn.execute(
                "SELECT e.digest,a.body FROM ct_events e JOIN ct_artifacts a "
                "ON a.digest=e.payload_digest WHERE e.event_id=%s",
                (event.event_id,),
            ).fetchone()
            if row is None or row["digest"] != digest(canonical(event)):
                raise ConflictError("unpersisted or altered delivery")
            payload = HealthChange.model_validate_json(str(row["body"]))
            if digest(canonical(payload)) != event.payload.sha256:
                raise ConflictError("persisted payload integrity failure")
            inserted = conn.execute(
                "INSERT INTO ct_inbox(consumer,event_id,digest) VALUES ('audit',%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING event_id",
                (event.event_id, row["digest"]),
            ).fetchone()
            if inserted is None:
                return False
            conn.execute(
                "INSERT INTO ct_audit "
                "(audit_id,event_id,tenant_id,actor_id,action,trace_id,payload_digest) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    "audit:" + event.event_id,
                    event.event_id,
                    event.tenant_id,
                    event.actor_id or event.source_service,
                    event.event_type,
                    event.trace_id,
                    event.payload.sha256,
                ),
            )
            if payload.health != "HEALTHY":
                conn.execute(
                    "INSERT INTO ct_notifications(event_id,status) VALUES (%s,'PENDING')",
                    (event.event_id,),
                )
            return True

    def notifications(self) -> tuple[str, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT event_id FROM ct_notifications WHERE status != 'DELIVERED' "
                "AND attempts < 3 ORDER BY updated_at LIMIT 100"
            ).fetchall()
            return tuple(str(row["event_id"]) for row in rows)

    def notification_attempt(self, event_id: str, delivered: bool) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE ct_notifications SET status=%s,attempts=attempts+1,error_category=%s, "
                "updated_at=now() WHERE event_id=%s AND status!='DELIVERED' AND attempts<3",
                (
                    "DELIVERED" if delivered else "FAILED",
                    None if delivered else "SINK_FAILED",
                    event_id,
                ),
            )

    def record_heartbeat(self, service_id: str, healthy: bool) -> None:
        if service_id not in {"audit", "outbox", "notification"}:
            raise ValueError("unknown platform service identity")
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO ct_service_health(service_id,health) VALUES (%s,%s) "
                "ON CONFLICT(service_id) DO UPDATE SET health=excluded.health,heartbeat_at=now()",
                (service_id, "HEALTHY" if healthy else "DEGRADED"),
            )

    def delivery_health(self) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS failures FROM ct_notifications WHERE status='FAILED' "
                "OR (status='PENDING' AND updated_at < now()-interval '5 seconds')"
            ).fetchone()
            failed_alerts = row is None or row["failures"] != 0
            row = conn.execute(
                "SELECT count(*) AS pending FROM ct_outbox WHERE sent_at IS NULL AND attempts>0"
            ).fetchone()
            failed_outbox = row is None or row["pending"] != 0
            return not failed_alerts and not failed_outbox

    def workers_healthy(self) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS active FROM ct_service_health WHERE health='HEALTHY' "
                "AND heartbeat_at > now()-interval '5 seconds'"
            ).fetchone()
            return row is not None and row["active"] == 3
