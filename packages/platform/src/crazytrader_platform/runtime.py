"""Service entrypoints configured by owner-local environment, no secret discovery."""

import asyncio
import os
import signal

import uvicorn
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from crazytrader_platform.control import ControlAPI
from crazytrader_platform.notification import NotificationWorker
from crazytrader_platform.storage import EventStore
from crazytrader_platform.transport import EventBus


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"missing required configuration {name}")
    return value


async def run() -> None:
    role = os.environ.get("CT_SERVICE_ROLE", "control-api")
    if role not in {"control-api", "audit", "notification", "outbox"}:
        raise ValueError("unsupported service role")
    store = EventStore(required("CT_DATABASE_DSN"))
    trace.set_tracer_provider(TracerProvider())
    if os.environ.get("CT_APPLY_MIGRATIONS") == "1":
        raise ValueError("use the separate migration administration entrypoint")
    if role == "notification":
        worker = NotificationWorker(store)
        while True:
            await asyncio.to_thread(worker.deliver)
            await asyncio.to_thread(store.record_heartbeat, role, store.delivery_health())
            await asyncio.sleep(1)
    bus = EventBus(required("CT_NATS_URL"))
    await bus.connect()
    try:
        if role == "control-api":
            api = ControlAPI(store, bus.healthy, required("CT_OWNER_TOKEN"))
            server = uvicorn.Server(
                uvicorn.Config(
                    api.app,
                    host=os.environ.get("CT_BIND_HOST", "127.0.0.1"),
                    port=8080,
                    access_log=False,
                )
            )
            await server.serve()
        else:
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop.set)
            while not stop.is_set():
                if role == "audit":
                    await bus.consume_audit(store)
                else:
                    await bus.publish_outbox(store)
                await asyncio.to_thread(store.record_heartbeat, role, True)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=0.2)
                except TimeoutError:
                    pass
    finally:
        await bus.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except Exception:
        # Configuration/socket exceptions may contain credential-bearing DSNs.
        raise SystemExit("platform service stopped: configuration/dependency failure") from None


if __name__ == "__main__":
    main()
