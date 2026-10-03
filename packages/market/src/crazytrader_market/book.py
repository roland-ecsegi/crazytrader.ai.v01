"""Binance Spot depth snapshot/delta alignment; no exchange timestamp invented."""

from datetime import datetime, timedelta
from decimal import Decimal

from crazytrader_contracts.market import BookDelta, BookSnapshot
from crazytrader_contracts.models import utc
from crazytrader_platform.storage import canonical, digest


class BookMonitor:
    def __init__(self, max_age: timedelta = timedelta(seconds=5)) -> None:
        if max_age <= timedelta(0):
            raise ValueError("positive freshness limit required")
        self.max_age = max_age
        self.snapshot: BookSnapshot | None = None
        self.sequence: int | None = None
        self.bids: dict[Decimal, Decimal] = {}
        self.asks: dict[Decimal, Decimal] = {}
        self.last_exchange_at: datetime | None = None
        self.last_received_at: datetime | None = None
        self.last_hash: str | None = None
        self.aligned = False
        self.failed = False

    def resync(self, snapshot: BookSnapshot, now: datetime) -> None:
        utc(now)
        if snapshot.observed_at > now or now - snapshot.observed_at > self.max_age:
            raise ValueError("stale/future snapshot")
        for levels in (snapshot.bids, snapshot.asks):
            if len({level.price for level in levels}) != len(levels):
                raise ValueError("duplicate snapshot level")
            if any(level.quantity == 0 for level in levels):
                raise ValueError("empty snapshot level")
        bids = {level.price: level.quantity for level in snapshot.bids}
        asks = {level.price: level.quantity for level in snapshot.asks}
        if not bids or not asks or max(bids) >= min(asks):
            raise ValueError("empty/crossed snapshot")
        self.snapshot = snapshot
        self.sequence = snapshot.last_sequence
        self.bids, self.asks = bids, asks
        self.last_exchange_at = self.last_received_at = None
        self.last_hash = None
        self.aligned = self.failed = False

    def observe(self, delta: BookDelta, received_at: datetime) -> bool:
        utc(received_at)
        snapshot = self.snapshot
        if snapshot is None or self.sequence is None or self.failed:
            return False
        if (delta.symbol, delta.environment, delta.metadata_version) != (
            snapshot.symbol,
            snapshot.environment,
            snapshot.metadata_version,
        ):
            self.failed = True
            raise ValueError("book identity mismatch")
        fingerprint = digest(canonical(delta))
        if delta.last_sequence <= self.sequence:
            if delta.last_sequence == self.sequence and self.last_hash is not None:
                if fingerprint != self.last_hash:
                    self.failed = True
                    raise ValueError("conflicting depth duplicate")
            return False
        # First delta must bridge snapshot+1; following deltas must start at next ID.
        next_id = self.sequence + 1
        if not delta.first_sequence <= next_id <= delta.last_sequence or (
            self.aligned and delta.first_sequence != next_id
        ):
            self.failed = True
            return False
        if (
            delta.exchange_at > received_at
            or received_at - delta.exchange_at > self.max_age
            or received_at - snapshot.observed_at > self.max_age
            and not self.aligned
            or self.last_exchange_at is not None
            and delta.exchange_at < self.last_exchange_at
            or self.last_received_at is not None
            and received_at < self.last_received_at
        ):
            self.failed = True
            return False
        bids, asks = self.bids.copy(), self.asks.copy()
        for book, levels in ((bids, delta.bids), (asks, delta.asks)):
            if len({level.price for level in levels}) != len(levels):
                self.failed = True
                raise ValueError("duplicate delta level")
            for level in levels:
                if level.quantity == 0:
                    book.pop(level.price, None)
                else:
                    book[level.price] = level.quantity
        if not bids or not asks or max(bids) >= min(asks):
            self.failed = True
            return False
        self.bids, self.asks = bids, asks
        self.sequence = delta.last_sequence
        self.last_hash = fingerprint
        self.last_exchange_at = delta.exchange_at
        self.last_received_at = received_at
        self.aligned = True
        return True

    def healthy(self, now: datetime) -> bool:
        utc(now)
        return (
            self.aligned
            and not self.failed
            and self.last_exchange_at is not None
            and self.last_received_at is not None
            and timedelta(0) <= now - self.last_exchange_at <= self.max_age
            and timedelta(0) <= now - self.last_received_at <= self.max_age
        )

    def disconnect(self) -> None:
        self.failed = True  # requires a new snapshot and aligned fresh delta
