"""Deterministic stream readiness; parsing success never implies market health."""

from datetime import datetime, timedelta
from typing import Literal

from crazytrader_contracts.market import Hash, MarketTrade, Sequence, Symbol
from crazytrader_contracts.models import Contract, Timestamp, utc
from crazytrader_platform.storage import canonical, digest


class TradeCheckpoint(Contract):
    symbol: Symbol
    environment: Literal["SANDBOX", "PUBLIC"]
    metadata_version: Hash
    last_id: Sequence | None = None
    last_hash: Hash | None = None
    last_exchange_at: Timestamp | None = None
    last_received_at: Timestamp | None = None
    gap_target: Sequence | None = None
    conflict: bool = False
    fresh_samples: Sequence = 0


class TradeMonitor:
    def __init__(
        self, checkpoint: TradeCheckpoint, max_age: timedelta = timedelta(seconds=5)
    ) -> None:
        if max_age <= timedelta(0):
            raise ValueError("positive freshness limit required")
        self.checkpoint = checkpoint
        self.max_age = max_age
        # Restored data never establishes a healthy current connection.
        self.connected = False

    def _identity(self, trade: MarketTrade) -> None:
        state = self.checkpoint
        if (trade.symbol, trade.environment, trade.metadata_version) != (
            state.symbol,
            state.environment,
            state.metadata_version,
        ):
            raise ValueError("stream identity/metadata mismatch")

    def _replace(self, **updates: object) -> None:
        self.checkpoint = TradeCheckpoint.model_validate(self.checkpoint.model_dump() | updates)

    def observe(self, trade: MarketTrade, received_at: datetime) -> bool:
        self._identity(trade)
        utc(received_at)
        state = self.checkpoint
        if state.conflict:
            return False
        fingerprint = digest(canonical(trade))
        if state.last_id is not None and trade.trade_id <= state.last_id:
            if trade.trade_id == state.last_id and fingerprint != state.last_hash:
                self._replace(conflict=True, fresh_samples=0)
                self.connected = False
                raise ValueError("conflicting duplicate trade")
            return False  # never refresh freshness from duplicate/out-of-order data
        if state.gap_target is not None:
            return False
        if state.last_id is not None and trade.trade_id != state.last_id + 1:
            self._replace(gap_target=trade.trade_id, fresh_samples=0)
            return False
        if (
            trade.exchange_at > received_at
            or received_at - trade.exchange_at > self.max_age
            or (state.last_exchange_at is not None and trade.exchange_at < state.last_exchange_at)
            or (state.last_received_at is not None and received_at < state.last_received_at)
        ):
            self._replace(fresh_samples=0)
            self.connected = False
            return False
        self._replace(
            last_id=trade.trade_id,
            last_hash=fingerprint,
            last_exchange_at=trade.exchange_at,
            last_received_at=received_at,
            fresh_samples=state.fresh_samples + 1,
        )
        self.connected = True
        return True

    def recover(self, backfill: tuple[MarketTrade, ...], received_at: datetime) -> None:
        """Only a complete contiguous backfill reaching the observed gap clears it."""
        utc(received_at)
        state = self.checkpoint
        if state.conflict or state.gap_target is None or state.last_id is None or not backfill:
            raise ValueError("no recoverable gap")
        if state.last_received_at is not None and received_at < state.last_received_at:
            raise ValueError("backwards receipt time")
        expected = state.last_id + 1
        last_time = state.last_exchange_at
        for trade in backfill:
            self._identity(trade)
            if (
                trade.trade_id != expected
                or trade.exchange_at > received_at
                or (last_time is not None and trade.exchange_at < last_time)
            ):
                raise ValueError("invalid/noncontiguous backfill")
            last_time = trade.exchange_at
            expected += 1
        if backfill[-1].trade_id < state.gap_target:
            raise ValueError("backfill does not reach gap target")
        last = backfill[-1]
        self._replace(
            last_id=last.trade_id,
            last_hash=digest(canonical(last)),
            last_exchange_at=last.exchange_at,
            last_received_at=received_at,
            gap_target=None,
            fresh_samples=0,
        )
        self.connected = False  # new live observations must establish freshness

    def disconnect(self) -> None:
        self.connected = False
        self._replace(fresh_samples=0)

    def health(self, now: datetime) -> Literal["HEALTHY", "DEGRADED", "UNKNOWN"]:
        utc(now)
        state = self.checkpoint
        if state.conflict or state.gap_target is not None:
            return "DEGRADED"
        if state.last_exchange_at is None or state.last_received_at is None:
            return "UNKNOWN"
        if not self.connected or state.fresh_samples < 2:
            return "DEGRADED"
        if (
            now < state.last_received_at
            or now < state.last_exchange_at
            or now - state.last_received_at > self.max_age
            or now - state.last_exchange_at > self.max_age
        ):
            return "DEGRADED"
        return "HEALTHY"
