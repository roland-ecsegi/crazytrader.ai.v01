"""Immutable Binance Spot market data, never an execution authority."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .models import Contract, Identifier, NonNegative, Positive, Timestamp

Sequence = Annotated[int, Field(strict=True, ge=0)]
Symbol = Annotated[str, Field(pattern=r"^[A-Z0-9]{2,30}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class MarketIdentity(Contract):
    venue: Literal["BINANCE"] = "BINANCE"
    environment: Literal["SANDBOX", "PUBLIC"]
    symbol: Symbol
    metadata_version: Hash


class MarketTrade(MarketIdentity):
    schema_version: Literal["1"] = "1"
    trade_id: Sequence
    price: Positive
    quantity: Positive
    taker_side: Literal["BUY", "SELL"]
    exchange_at: Timestamp


class MarketCandle(MarketIdentity):
    schema_version: Literal["1"] = "1"
    interval: Literal["1m", "5m", "15m", "1h", "4h", "1d"]
    opened_at: Timestamp
    closed_at: Timestamp
    open_price: Positive
    high_price: Positive
    low_price: Positive
    close_price: Positive
    volume: NonNegative
    trade_count: Sequence

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.closed_at <= self.opened_at:
            raise ValueError("candle close must follow open")
        if not self.low_price <= min(self.open_price, self.close_price):
            raise ValueError("candle prices below low")
        if not self.high_price >= max(self.open_price, self.close_price, self.low_price):
            raise ValueError("candle prices above high")
        return self


class BookLevel(Contract):
    price: Positive
    quantity: NonNegative  # zero deletes a level


class BookSnapshot(MarketIdentity):
    schema_version: Literal["1"] = "1"
    last_sequence: Sequence
    observed_at: Timestamp  # REST depth has no exchange timestamp
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]


class BookDelta(MarketIdentity):
    schema_version: Literal["1"] = "1"
    first_sequence: Sequence
    last_sequence: Sequence
    exchange_at: Timestamp
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]

    @model_validator(mode="after")
    def sequence(self) -> Self:
        if self.first_sequence > self.last_sequence:
            raise ValueError("invalid book sequence range")
        return self


class InstrumentMetadata(Contract):
    schema_version: Literal["1"] = "1"
    venue: Literal["BINANCE"] = "BINANCE"
    environment: Literal["SANDBOX", "PUBLIC"]
    symbol: Symbol
    base_asset: Identifier
    quote_asset: Identifier
    market_type: Literal["SPOT"] = "SPOT"
    status: Literal["TRADING", "HALT", "BREAK"]
    tick_size: Positive
    quantity_step: Positive
    min_quantity: NonNegative
    max_quantity: Positive
    min_notional: NonNegative
    metadata_version: Hash
    observed_at: Timestamp

    @model_validator(mode="after")
    def quantity_range(self) -> Self:
        if self.min_quantity > self.max_quantity:
            raise ValueError("minimum quantity exceeds maximum")
        return self


class MarketStatus(MarketIdentity):
    schema_version: Literal["1"] = "1"
    health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    reason_code: Literal[
        "FRESH", "STALE_OR_DISCONNECTED", "SEQUENCE_GAP", "CONTENT_CONFLICT", "NO_OBSERVATIONS"
    ]
    occurred_at: Timestamp
    last_trade_id: Sequence | None
    gap_target: Sequence | None
    last_exchange_at: Timestamp | None
    last_received_at: Timestamp | None
