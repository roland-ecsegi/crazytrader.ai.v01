"""Requires real disposable PostgreSQL/NATS via make integration."""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_platform.control import ControlAPI
from crazytrader_platform.notification import NotificationWorker
from crazytrader_platform.storage import ConflictError, EventStore, HealthChange, canonical, digest
from crazytrader_platform.transport import CONSUMER, STREAM, SUBJECT, EventBus
from nats.js.api import AckPolicy, ConsumerConfig

pytestmark = pytest.mark.skipif(
    "CT_TEST_DSN" not in os.environ, reason="use make integration for real dependencies"
)


@pytest.fixture
def store() -> EventStore:
    store = EventStore(os.environ["CT_TEST_DSN"])
    store.migrate(Path("infra/migrations/001_platform.sql"))
    return store


def sample() -> tuple[EventEnvelope, HealthChange]:
    now = datetime.now(UTC)
    payload = HealthChange(
        service_id="market-data", health="DEGRADED", reason_code="STALE", occurred_at=now
    )
    hash_value = digest(canonical(payload))
    event = EventEnvelope(
        event_id="e_" + uuid.uuid4().hex,
        event_type="ServiceHealthChanged.v1",
        schema_version="1",
        occurred_at=now,
        tenant_id="local-owner",
        source_service="market-data",
        trace_id="trace_" + uuid.uuid4().hex,
        correlation_id="health_" + uuid.uuid4().hex,
        payload=PayloadReference(
            artifact_ref=hash_value, sha256=hash_value, payload_schema_ref="HealthChange.v1"
        ),
    )
    return event, payload


def scalar(store: EventStore, query: str, event_id: str) -> object:
    with store.connection() as conn:
        row = conn.execute(query, (event_id,)).fetchone()
        assert row is not None
        return next(iter(row.values()))


def test_append_atomic_idempotent_and_content_collisions_denied(store: EventStore) -> None:
    event, payload = sample()
    assert store.append(event, payload)
    assert not store.append(event, payload)
    assert scalar(store, "SELECT count(*) FROM ct_events WHERE event_id=%s", event.event_id) == 1
    changed = EventEnvelope.model_validate(event.model_dump() | {"trace_id": "changed"})
    with pytest.raises(ConflictError):
        store.append(changed, payload)
    broken = EventEnvelope.model_validate(
        event.model_dump() | {"payload": event.payload.model_dump() | {"sha256": "f" * 64}}
    )
    with pytest.raises(ValueError):
        store.append(broken, payload)
    assert any(e.event_id == event.event_id for e in store.pending())


def test_audit_inbox_notification_and_append_only_sql(store: EventStore) -> None:
    event, payload = sample()
    store.append(event, payload)
    assert store.consume_audit(event)
    assert not EventStore(os.environ["CT_TEST_DSN"]).consume_audit(event)
    assert scalar(store, "SELECT count(*) FROM ct_audit WHERE event_id=%s", event.event_id) == 1
    for table in ("ct_events", "ct_audit", "ct_inbox"):
        with pytest.raises(psycopg.Error), store.connection() as conn:
            conn.execute(f"DELETE FROM {table} WHERE event_id=%s", (event.event_id,))
    with pytest.raises(psycopg.Error), store.connection() as conn:
        conn.execute("TRUNCATE ct_audit")
    forged = EventEnvelope.model_validate(event.model_dump() | {"actor_id": "untrusted"})
    with pytest.raises(ConflictError):
        store.consume_audit(forged)

    def fail(_: str) -> None:
        raise RuntimeError("sensitive-sink-error-sentinel")

    worker = NotificationWorker(store, fail)
    worker.deliver()
    assert not store.delivery_health()
    assert (
        scalar(
            store, "SELECT error_category FROM ct_notifications WHERE event_id=%s", event.event_id
        )
        == "SINK_FAILED"
    )
    seen = []
    NotificationWorker(store, seen.append).deliver()
    assert event.event_id in seen
    assert (
        scalar(store, "SELECT status FROM ct_notifications WHERE event_id=%s", event.event_id)
        == "DELIVERED"
    )
    NotificationWorker(store, seen.append).deliver()
    assert seen.count(event.event_id) == 1


def test_notification_retries_bounded_and_remain_unhealthy(store: EventStore) -> None:
    event, payload = sample()
    store.append(event, payload)
    store.consume_audit(event)
    for _ in range(5):
        store.notification_attempt(event.event_id, False)
    assert (
        scalar(store, "SELECT attempts FROM ct_notifications WHERE event_id=%s", event.event_id)
        == 3
    )
    assert event.event_id not in store.notifications()
    assert not store.delivery_health()


def test_real_jetstream_delivery_restart_and_ack_before_mark_replay(store: EventStore) -> None:
    async def run() -> None:
        bus = EventBus(os.environ["CT_TEST_NATS_URL"])
        await bus.connect()
        assert await bus.healthy()
        event, payload = sample()
        store.append(event, payload)
        assert await bus.publish_outbox(store) >= 1
        while await bus.consume_audit(store):
            pass
        assert scalar(store, "SELECT count(*) FROM ct_audit WHERE event_id=%s", event.event_id) == 1
        # Simulate publisher restart after broker ACK but before DB sent_at commit.
        with store.connection() as conn:
            conn.execute("UPDATE ct_outbox SET sent_at=NULL WHERE event_id=%s", (event.event_id,))
        await bus.close()
        restored = EventBus(os.environ["CT_TEST_NATS_URL"])
        await restored.connect()
        assert await restored.publish_outbox(store) >= 1
        # Broker may deduplicate within window; inbox separately proves redelivery.
        assert not store.consume_audit(event)
        assert scalar(store, "SELECT count(*) FROM ct_audit WHERE event_id=%s", event.event_id) == 1
        await restored.close()

    asyncio.run(run())


def test_real_broker_failure_retains_outbox(store: EventStore) -> None:
    async def run() -> None:
        bus = EventBus(os.environ["CT_TEST_NATS_URL"])
        await bus.connect()
        await bus.close()
        event, payload = sample()
        store.append(event, payload)
        with pytest.raises(RuntimeError, match="delivery failed"):
            await bus.publish_outbox(store)
        assert any(e.event_id == event.event_id for e in store.pending())
        assert not await bus.healthy()

    asyncio.run(run())


def test_unacked_consumer_delivery_survives_worker_restart(store: EventStore) -> None:
    async def run() -> None:
        bus = EventBus(os.environ["CT_TEST_NATS_URL"])
        await bus.connect()
        event, payload = sample()
        store.append(event, payload)
        await bus.publish_outbox(store)
        assert bus.js is not None
        sub = await bus.js.pull_subscribe(
            SUBJECT,
            durable=CONSUMER,
            stream=STREAM,
            config=ConsumerConfig(
                durable_name=CONSUMER,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=2,
                max_deliver=10,
                max_ack_pending=100,
            ),
        )
        messages = await sub.fetch(10, timeout=3)
        assert messages
        for message in messages:
            store.consume_audit(EventEnvelope.model_validate_json(message.data))
        # Crash before ACK; durable consumer must redeliver after restart.
        await bus.close()
        await asyncio.sleep(2.1)
        recovered = EventBus(os.environ["CT_TEST_NATS_URL"])
        await recovered.connect()
        assert await recovered.consume_audit(store, timeout=3) >= 1
        assert scalar(store, "SELECT count(*) FROM ct_audit WHERE event_id=%s", event.event_id) == 1
        await recovered.close()

    asyncio.run(run())


def test_readiness_requires_fresh_worker_heartbeats(store: EventStore) -> None:
    assert not store.workers_healthy()
    for role in ("audit", "outbox", "notification"):
        store.record_heartbeat(role, True)
    assert store.workers_healthy()
    store.record_heartbeat("audit", False)
    assert not store.workers_healthy()
    store.record_heartbeat("audit", True)
    with store.connection() as conn:
        conn.execute(
            "UPDATE ct_service_health SET heartbeat_at=now()-interval '10 seconds' "
            "WHERE service_id='audit'"
        )
    assert not store.workers_healthy()
    with pytest.raises(ValueError):
        store.record_heartbeat("owner-unknown", True)


def test_full_owner_readiness_healthy_then_worker_stale(store: EventStore) -> None:
    # Clear only delivery metadata from prior tests; append-only audit stays intact.
    with store.connection() as conn:
        conn.execute("UPDATE ct_outbox SET sent_at=now() WHERE sent_at IS NULL")
        conn.execute("UPDATE ct_notifications SET status='DELIVERED',error_category=NULL")
    for role in ("audit", "outbox", "notification"):
        store.record_heartbeat(role, True)

    async def run() -> None:
        bus = EventBus(os.environ["CT_TEST_NATS_URL"])
        await bus.connect()
        token = "fixture-" + "x" * 32
        api = ControlAPI(store, bus.healthy, token)
        # ASGI client in same event loop as broker avoids cross-loop access.
        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://fixture"
        ) as client:
            response = await client.get("/ready", headers={"Authorization": "Bearer " + token})
            assert response.status_code == 200
            store.record_heartbeat("audit", False)
            response = await client.get("/ready", headers={"Authorization": "Bearer " + token})
            assert response.status_code == 503
        await bus.close()

    asyncio.run(run())
