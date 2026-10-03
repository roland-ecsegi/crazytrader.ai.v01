"""Bounded read-only market poller. Each invocation persists an exact checkpoint.

No polling result establishes websocket operation or elapsed paper certification.
"""

from datetime import UTC, datetime

from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.market import InstrumentMetadata, MarketStatus, MarketTrade
from crazytrader_platform.storage import ConflictError, EventStore, canonical, digest

from .adapter import PublicMarketClient, normalize_trade
from .archive import HistoricalIngestor
from .monitor import TradeCheckpoint, TradeMonitor


class MarketWorker:
    def __init__(
        self,
        tenant: str,
        metadata: InstrumentMetadata,
        client: PublicMarketClient,
        archive: HistoricalIngestor,
        store: EventStore,
    ) -> None:
        if metadata.environment != client.environment:
            raise ValueError("market environment mismatch")
        self.tenant, self.metadata, self.client = tenant, metadata, client
        self.archive, self.store = archive, store
        with store.connection() as conn:
            row = conn.execute(
                "SELECT body FROM ct_market_checkpoints WHERE "
                "tenant_id=%s AND environment=%s AND symbol=%s",
                self.identity,
            ).fetchone()
        state = (
            TradeCheckpoint.model_validate_json(str(row["body"]))
            if row
            else TradeCheckpoint(
                symbol=metadata.symbol,
                environment=metadata.environment,
                metadata_version=metadata.metadata_version,
            )
        )
        if state.metadata_version != metadata.metadata_version:
            raise ValueError("metadata change requires explicit stream resynchronization")
        self.monitor = TradeMonitor(state)

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.tenant, self.metadata.environment, self.metadata.symbol

    def persist(self, now: datetime) -> None:
        health = self.monitor.health(now)
        state = self.monitor.checkpoint
        reason = (
            "CONTENT_CONFLICT"
            if state.conflict
            else "SEQUENCE_GAP"
            if state.gap_target is not None
            else "NO_OBSERVATIONS"
            if health == "UNKNOWN"
            else "FRESH"
            if health == "HEALTHY"
            else "STALE_OR_DISCONNECTED"
        )
        with self.store.connection() as conn:
            conn.execute(
                "INSERT INTO ct_market_checkpoints "
                "(tenant_id,environment,symbol,body,health) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(tenant_id,environment,symbol) DO UPDATE SET "
                "body=excluded.body,health=excluded.health,heartbeat_at=now()",
                (*self.identity, canonical(self.monitor.checkpoint), self.monitor.health(now)),
            )

        status = MarketStatus.model_validate(
            {
                "environment": self.metadata.environment,
                "symbol": self.metadata.symbol,
                "metadata_version": self.metadata.metadata_version,
                "health": health,
                "reason_code": reason,
                "occurred_at": now,
                "last_trade_id": state.last_id,
                "gap_target": state.gap_target,
                "last_exchange_at": state.last_exchange_at,
                "last_received_at": state.last_received_at,
            }
        )
        fingerprint = digest(canonical(status))
        event_type = (
            "MarketDataRecovered.v1"
            if health == "HEALTHY"
            else "MarketSequenceGapDetected.v1"
            if state.gap_target is not None
            else "MarketDataStale.v1"
        )
        key = digest(str(self.identity) + fingerprint)
        self.store.append(
            EventEnvelope(
                event_id="market-status:" + key,
                event_type=event_type,
                schema_version="1",
                occurred_at=now,
                tenant_id=self.tenant,
                source_service="market-data",
                trace_id="market:" + key,
                correlation_id="market:" + key,
                payload=PayloadReference(
                    artifact_ref=fingerprint,
                    sha256=fingerprint,
                    payload_schema_ref="MarketStatus.v1",
                ),
            ),
            status,
        )

    def poll(self, now: datetime | None = None) -> int:
        # Single symbol writer. Session lock releases even on crash/connection loss.
        with self.store.connection() as conn:
            lock = conn.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS acquired",
                ("market-worker:" + str(self.identity),),
            ).fetchone()
            if lock is None or lock["acquired"] is not True:
                raise RuntimeError("market symbol already has a writer")
            row = conn.execute(
                "SELECT body FROM ct_market_checkpoints WHERE "
                "tenant_id=%s AND environment=%s AND symbol=%s",
                self.identity,
            ).fetchone()
            if row is not None and str(row["body"]) != canonical(self.monitor.checkpoint):
                self.monitor = TradeMonitor(TradeCheckpoint.model_validate_json(str(row["body"])))
            return self._poll(now)

    def emit(self, trade: MarketTrade) -> None:
        fingerprint = digest(canonical(trade))
        identity_hash = digest(str((self.identity, trade.trade_id)))
        event = EventEnvelope(
            event_id="market-trade:" + identity_hash,
            event_type="MarketTradeReceived.v1",
            schema_version="1",
            occurred_at=trade.exchange_at,
            tenant_id=self.tenant,
            source_service="market-data",
            trace_id="market:" + identity_hash,
            correlation_id="market:" + identity_hash,
            payload=PayloadReference(
                artifact_ref=fingerprint, sha256=fingerprint, payload_schema_ref="MarketTrade.v1"
            ),
        )
        self.store.append(event, trade)

    def _poll(self, now: datetime | None = None) -> int:
        observed_at = now or datetime.now(UTC)
        cursor = self.monitor.checkpoint.last_id
        try:
            raw = self.client.read(
                "agg_trades", self.metadata.symbol, 1000, None if cursor is None else cursor + 1
            )
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise ValueError("invalid aggregate-trade response")
            if not raw:
                self.monitor.disconnect()
                return 0
            observed_at = now or datetime.now(UTC)
            trades = tuple(normalize_trade(item, self.metadata) for item in raw)
            if cursor is not None and trades[0].trade_id > cursor + 1:
                self.monitor.observe(trades[0], observed_at)
                raise ValueError("missing historical range; backfill required")
            # Full-ID immutable archive validates old duplicates before readiness updates.
            self.archive.ingest(self.tenant, self.metadata, raw)
            for trade in trades:
                self.emit(trade)
            accepted = sum(self.monitor.observe(trade, observed_at) for trade in trades)
            if self.monitor.checkpoint.gap_target is not None:
                last_id = self.monitor.checkpoint.last_id
                if last_id is None:
                    raise ValueError("missing recovery baseline")
                backfill = tuple(trade for trade in trades if trade.trade_id > last_id)
                self.monitor.recover(backfill, observed_at)
                # Archive and complete contiguous recovery proven; still needs fresh warmup.
            return accepted
        except ConflictError:
            self.monitor.checkpoint = TradeCheckpoint.model_validate(
                self.monitor.checkpoint.model_dump() | {"conflict": True, "fresh_samples": 0}
            )
            self.monitor.disconnect()
            raise
        except Exception:
            self.monitor.disconnect()
            raise RuntimeError("market poll failed; readiness degraded") from None
        finally:
            self.persist(now or datetime.now(UTC))
