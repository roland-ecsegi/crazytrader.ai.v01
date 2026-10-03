"""Transactional event/audit state. Failure never silently falls back to memory."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import psycopg
from crazytrader_contracts.codec import canonical as canonical
from crazytrader_contracts.codec import digest as digest
from crazytrader_contracts.events import EventEnvelope
from crazytrader_contracts.execution import (
    TRANSITION_EVENTS,
    CancellationEvaluationRecord,
    CancellationReceipt,
    ExecutionIncident,
    ExecutionTransition,
)
from crazytrader_contracts.ledger import LedgerTransaction, VenueFillLedgerTransaction
from crazytrader_contracts.market import BookDelta, MarketCandle, MarketStatus, MarketTrade
from crazytrader_contracts.models import Contract, Identifier, Timestamp
from crazytrader_contracts.risk import PolicyAuthorization, RiskAuthorization, RiskBoundaryRejection
from opentelemetry import trace
from psycopg.rows import dict_row

TRACER = trace.get_tracer(__name__)


class HealthChange(Contract):
    service_id: Identifier
    health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    reason_code: Identifier
    occurred_at: Timestamp


PAYLOAD_TYPES: dict[str, type[Contract]] = {
    "ServiceHealthChanged.v1": HealthChange,
    "MarketTradeReceived.v1": MarketTrade,
    "MarketCandleClosed.v1": MarketCandle,
    "MarketBookUpdated.v1": BookDelta,
    "LedgerEntryAppended.v1": LedgerTransaction,
    "LedgerVenueFillAppended.v1": VenueFillLedgerTransaction,
    "RiskDecisionDenied.v1": RiskBoundaryRejection,
    "TradeIntentRiskApproved.v1": RiskAuthorization,
    "TradeIntentRiskDenied.v1": RiskAuthorization,
    "TradeIntentPolicyApproved.v1": PolicyAuthorization,
    "TradeIntentPolicyDenied.v1": PolicyAuthorization,
    "MarketDataStale.v1": MarketStatus,
    "MarketDataRecovered.v1": MarketStatus,
    "MarketSequenceGapDetected.v1": MarketStatus,
}

PAYLOAD_TYPES.update({name: ExecutionTransition for name in TRANSITION_EVENTS.values()})
PAYLOAD_TYPES["ExecutionPreparationChanged.v1"] = ExecutionTransition
PAYLOAD_TYPES["ReconciliationCriticalMismatch.v1"] = ExecutionIncident
PAYLOAD_TYPES["OrderCancellationAuthorized.v1"] = CancellationEvaluationRecord
PAYLOAD_TYPES["OrderCancellationDenied.v1"] = CancellationEvaluationRecord
PAYLOAD_TYPES["OrderCancellationReceiptRecorded.v1"] = CancellationReceipt


def validate_payload(event: EventEnvelope, payload: Contract) -> Contract:
    expected_type = PAYLOAD_TYPES.get(event.event_type)
    if expected_type is None or type(payload) is not expected_type:
        raise ValueError("unsupported typed event payload")
    payload = expected_type.model_validate(payload.model_dump())
    if event.payload.payload_schema_ref != type(payload).__name__ + ".v1":
        raise ValueError("payload schema mismatch")
    if isinstance(payload, HealthChange):
        source, occurred = payload.service_id, payload.occurred_at
    elif isinstance(payload, CancellationEvaluationRecord):
        source, occurred = "execution", payload.authorization.evaluated_at
        if (
            event.tenant_id != payload.context.tenant_id
            or event.actor_id != payload.context.actor_id
        ):
            raise ValueError("cancellation evaluation ownership mismatch")
        if (event.event_type == "OrderCancellationAuthorized.v1") != (
            payload.authorization.decision == "ALLOW"
        ):
            raise ValueError("cancellation verdict mismatch")
    elif isinstance(payload, CancellationReceipt):
        source, occurred = "execution", payload.observed_at
        if event.tenant_id != payload.tenant_id or event.actor_id != payload.actor_id:
            raise ValueError("cancellation receipt ownership mismatch")
    elif isinstance(payload, ExecutionIncident):
        source, occurred = "reconciliation", payload.occurred_at
        if event.tenant_id != payload.tenant_id or event.actor_id != payload.actor_id:
            raise ValueError("reconciliation incident ownership mismatch")
    elif isinstance(payload, ExecutionTransition):
        source, occurred = "execution", payload.occurred_at
        if event.tenant_id != payload.tenant_id or event.actor_id != payload.actor_id:
            raise ValueError("execution event ownership mismatch")
        expected = TRANSITION_EVENTS.get(
            payload.resulting_state.state, "ExecutionPreparationChanged.v1"
        )
        if event.event_type != expected:
            raise ValueError("execution event state mismatch")
    elif isinstance(payload, RiskBoundaryRejection):
        source, occurred = "risk-engine", payload.occurred_at
        if event.tenant_id != payload.tenant_id or event.actor_id != payload.actor_id:
            raise ValueError("boundary denial ownership mismatch")
    elif isinstance(payload, (RiskAuthorization, PolicyAuthorization)):
        risk = payload if isinstance(payload, RiskAuthorization) else payload.risk_authorization
        source = "risk-engine" if isinstance(payload, RiskAuthorization) else "policy-engine"
        occurred = payload.evaluated_at
        if event.tenant_id != risk.tenant_id or event.actor_id != risk.actor_id:
            raise ValueError("decision ownership mismatch")
        if ("Approved" in event.event_type) != (payload.decision.decision == "ALLOW"):
            raise ValueError("decision event verdict mismatch")
    elif isinstance(payload, (LedgerTransaction, VenueFillLedgerTransaction)):
        source, occurred = "ledger", payload.timestamp
        if event.tenant_id != payload.tenant_id or event.actor_id != payload.actor_id:
            raise ValueError("ledger event ownership mismatch")
    elif isinstance(payload, MarketStatus):
        source, occurred = "market-data", payload.occurred_at
        if (event.event_type == "MarketDataRecovered.v1") != (payload.health == "HEALTHY"):
            raise ValueError("market recovery health mismatch")
        if (event.event_type == "MarketSequenceGapDetected.v1") != (
            payload.reason_code == "SEQUENCE_GAP"
        ):
            raise ValueError("market gap status mismatch")
    elif isinstance(payload, MarketCandle):
        source, occurred = "market-data", payload.closed_at
    elif isinstance(payload, (MarketTrade, BookDelta)):
        source, occurred = "market-data", payload.exchange_at
    else:
        raise ValueError("unsupported payload")
    if event.source_service != source or event.occurred_at != occurred:
        raise ValueError("payload/envelope provenance mismatch")
    return payload


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

    def append(self, event: EventEnvelope, payload: Contract) -> bool:
        """Persist payload, event and outbox atomically; reject changed ID content."""
        payload = validate_payload(event, payload)
        with TRACER.start_as_current_span("platform.event.append"), self.connection() as conn:
            return self.append_in_transaction(conn, event, payload)

    def append_in_transaction(
        self, conn: psycopg.Connection[dict[str, object]], event: EventEnvelope, payload: Contract
    ) -> bool:
        payload = validate_payload(event, payload)
        schema_ref = type(payload).__name__ + ".v1"
        body = canonical(payload)
        expected = digest(body)
        if event.payload.sha256 != expected or event.payload.artifact_ref != expected:
            raise ValueError("payload reference/hash mismatch")
        envelope = canonical(event)
        event_digest = digest(envelope)
        inserted = conn.execute(
            "INSERT INTO ct_artifacts(digest,tenant_id,schema_ref,body) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING RETURNING digest",
            (expected, event.tenant_id, schema_ref, body),
        ).fetchone()
        if inserted is None:
            existing = conn.execute(
                "SELECT body,tenant_id,schema_ref FROM ct_artifacts WHERE digest=%s",
                (expected,),
            ).fetchone()
            if existing != {
                "body": body,
                "tenant_id": event.tenant_id,
                "schema_ref": schema_ref,
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
            payload_type = PAYLOAD_TYPES.get(event.event_type)
            if payload_type is None:
                raise ValueError("unsupported persisted payload")
            payload = payload_type.model_validate_json(str(row["body"]))
            payload = validate_payload(event, payload)
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
            if isinstance(payload, ExecutionIncident) or (
                isinstance(payload, (HealthChange, MarketStatus)) and payload.health != "HEALTHY"
            ):
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
