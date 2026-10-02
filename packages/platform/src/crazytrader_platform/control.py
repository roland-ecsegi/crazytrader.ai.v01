"""Read-only Enterprise Local owner API; no order or credential endpoints."""

import asyncio
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest

from crazytrader_platform.storage import EventStore


class ControlAPI:
    def __init__(
        self, store: EventStore, broker_health: Callable[[], Awaitable[bool]], owner_token: str
    ) -> None:
        if len(owner_token) < 32:
            raise ValueError("owner authentication token must be at least 32 characters")
        self.store = store
        self._owner_token = owner_token.encode()
        self.broker_health = broker_health
        registry = CollectorRegistry()
        auth_denials = Counter(
            "ct_auth_denials", "Rejected owner authentication", registry=registry
        )
        ready_gauge = Gauge(
            "ct_platform_ready", "Database/event/notification readiness", registry=registry
        )
        app = FastAPI(
            title="CrazyTrader Enterprise Local", docs_url=None, redoc_url=None, openapi_url=None
        )
        self.app = app

        def owner(authorization: str | None = Header(default=None)) -> None:
            supplied = (
                authorization.removeprefix("Bearer ")
                if authorization and authorization.startswith("Bearer ")
                else ""
            )
            if not secrets.compare_digest(supplied.encode(), self._owner_token):
                auth_denials.inc()
                raise HTTPException(status_code=401, detail="owner authentication required")

        @app.get("/live")
        def live() -> dict[str, str]:
            return {"status": "alive"}

        @app.get("/ready", dependencies=[Depends(owner)])
        async def ready() -> Response:
            database, broker = await asyncio.gather(
                asyncio.to_thread(store.healthy), self.broker_health(), return_exceptions=True
            )
            alerts = False
            if database is True:
                try:
                    alerts = await asyncio.to_thread(
                        store.delivery_health
                    ) and await asyncio.to_thread(store.workers_healthy)
                except Exception:
                    alerts = False
            healthy = database is True and broker is True and alerts
            ready_gauge.set(int(healthy))
            # No exception text/connection configuration can reach the response.
            return Response(
                content='{"status":"'
                + ("ready" if healthy else "degraded")
                + '","certification":"L0"}',
                status_code=200 if healthy else 503,
                media_type="application/json",
            )

        @app.get("/certification", dependencies=[Depends(owner)])
        def certification() -> dict[str, str]:
            return {"level": "L0", "status": "DEVELOPMENT", "live_activation": "DISABLED"}

        @app.get("/metrics", dependencies=[Depends(owner)])
        def metrics() -> Response:
            return Response(
                content=generate_latest(registry), media_type="text/plain; version=0.0.4"
            )
