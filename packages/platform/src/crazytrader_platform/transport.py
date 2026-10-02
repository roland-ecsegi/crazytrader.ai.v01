"""NATS JetStream at-least-once delivery with durable explicit acknowledgments."""

import asyncio

import nats
from crazytrader_contracts.events import EventEnvelope
from nats.aio.client import Client
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.api import AckPolicy, ConsumerConfig, RetentionPolicy, StorageType, StreamConfig
from nats.js.client import JetStreamContext
from nats.js.errors import NotFoundError

from crazytrader_platform.storage import EventStore

STREAM = "CRAZYTRADER_PLATFORM_V1"
SUBJECT = "ct.platform.v1"
CONSUMER = "audit-v1"


class EventBus:
    def __init__(self, server: str) -> None:
        self._server = server
        self.client: Client | None = None
        self.js: JetStreamContext | None = None

    @staticmethod
    async def safe_error(_: Exception) -> None:
        # Broker URI errors may contain authentication material; health exposes
        # connection state without forwarding raw exception strings.
        return None

    async def connect(self) -> None:
        self.client = await nats.connect(
            self._server,
            connect_timeout=2,
            max_reconnect_attempts=2,
            reconnect_time_wait=0.2,
            allow_reconnect=True,
            error_cb=self.safe_error,
        )
        self.js = self.client.jetstream(timeout=2)
        try:
            info = await self.js.stream_info(STREAM)
        except NotFoundError:
            await self.js.add_stream(
                config=StreamConfig(
                    name=STREAM,
                    subjects=[SUBJECT],
                    storage=StorageType.FILE,
                    retention=RetentionPolicy.LIMITS,
                    max_bytes=64 * 1024 * 1024,
                    max_age=7 * 86400,
                    duplicate_window=120,
                )
            )
        else:
            if info.config.subjects != [SUBJECT] or info.config.storage != StorageType.FILE:
                raise ValueError("incompatible durable stream configuration")

    async def healthy(self) -> bool:
        if self.client is None or not self.client.is_connected or self.js is None:
            return False
        try:
            await self.js.stream_info(STREAM)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self.client is not None and not self.client.is_closed:
            await self.client.close()

    async def publish_outbox(self, store: EventStore) -> int:
        if self.js is None:
            raise RuntimeError("broker unavailable")
        acknowledged = 0
        for event in await asyncio.to_thread(store.pending):
            try:
                ack = await self.js.publish(
                    SUBJECT,
                    event.model_dump_json().encode(),
                    headers={"Nats-Msg-Id": event.event_id},
                )
                if ack.stream != STREAM:
                    raise RuntimeError("unexpected stream acknowledgment")
            except Exception:
                await asyncio.to_thread(store.publish_attempt, event.event_id, False)
                raise RuntimeError("event broker delivery failed") from None
            await asyncio.to_thread(store.publish_attempt, event.event_id, True)
            acknowledged += 1
        return acknowledged

    async def consume_audit(self, store: EventStore, timeout: float = 1) -> int:
        if self.js is None:
            raise RuntimeError("broker unavailable")
        sub = await self.js.pull_subscribe(
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
        try:
            try:
                messages = await sub.fetch(batch=10, timeout=timeout)
            except (NatsTimeoutError, TimeoutError):
                return 0
            for message in messages:
                try:
                    event = EventEnvelope.model_validate_json(message.data)
                    await asyncio.to_thread(store.consume_audit, event)
                except Exception:
                    # No ACK on invalid delivery or database failure. Bounded redelivery
                    # remains visible via JetStream consumer info and dependency health.
                    await message.nak(delay=1)
                    raise RuntimeError("audit delivery rejected or unavailable") from None
                await message.ack_sync(timeout=2)
            return len(messages)
        finally:
            await sub.unsubscribe()
