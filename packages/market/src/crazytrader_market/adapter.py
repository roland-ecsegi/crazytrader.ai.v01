"""Narrow official-SDK subprocess adapter and typed public response normalization."""

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Literal

from crazytrader_contracts.market import (
    BookDelta,
    BookLevel,
    BookSnapshot,
    InstrumentMetadata,
    MarketCandle,
    MarketTrade,
)
from crazytrader_contracts.models import Positive
from crazytrader_platform.storage import digest
from pydantic import BaseModel, ConfigDict, Field

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def aligned(value: Decimal, step: Decimal) -> bool:
    # Contract supports 38 digits/18 scale; ambient Decimal precision is only 28.
    with localcontext() as context:
        context.prec = 80
        return value % step == 0


class RawAggregateTrade(BaseModel):
    model_config = ConfigDict(extra="ignore")
    trade_id: int = Field(alias="a", strict=True, ge=0)
    price: Positive = Field(alias="p")
    quantity: Positive = Field(alias="q")
    timestamp_ms: int = Field(alias="T", strict=True, ge=0)
    buyer_is_maker: bool = Field(alias="m", strict=True)


def normalize_trade(raw: object, metadata: InstrumentMetadata) -> MarketTrade:
    trade = RawAggregateTrade.model_validate(raw)
    if not aligned(trade.price, metadata.tick_size) or not aligned(
        trade.quantity, metadata.quantity_step
    ):
        raise ValueError("trade violates versioned venue precision")
    return MarketTrade(
        environment=metadata.environment,
        symbol=metadata.symbol,
        metadata_version=metadata.metadata_version,
        trade_id=trade.trade_id,
        price=trade.price,
        quantity=trade.quantity,
        taker_side="SELL" if trade.buyer_is_maker else "BUY",
        exchange_at=EPOCH + timedelta(milliseconds=trade.timestamp_ms),
    )


class PublicMarketClient:
    def __init__(
        self,
        sdk_python: Path,
        sdk_script: Path,
        environment: Literal["SANDBOX", "PUBLIC"] = "SANDBOX",
    ) -> None:
        if environment not in {"SANDBOX", "PUBLIC"}:
            raise ValueError("invalid read-only environment")
        self._python = sdk_python
        self._script = sdk_script
        self.environment = environment

    def read(
        self,
        operation: Literal["exchange_info", "agg_trades", "depth"],
        symbol: str,
        limit: int = 100,
        from_id: int | None = None,
    ) -> object:
        if operation not in {"exchange_info", "agg_trades", "depth"}:
            raise ValueError("unsupported read-only operation")
        # Preserve proxy/CA trust, never inherit owner auth or venue credentials.
        permitted = {
            "PATH",
            "SYSTEMROOT",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "no_proxy",
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
        }
        env = {name: value for name, value in os.environ.items() if name in permitted}
        request = {
            "environment": self.environment,
            "operation": operation,
            "symbol": symbol,
            "limit": limit,
            "from_id": from_id,
        }
        result = subprocess.run(
            [str(self._python), str(self._script)],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            env=env,
            timeout=15,
        )
        if result.returncode:
            raise RuntimeError("read-only venue request unavailable")
        return json.loads(result.stdout)


def normalize_metadata(
    raw: object, environment: Literal["SANDBOX", "PUBLIC"], observed_at: datetime
) -> InstrumentMetadata:
    if not isinstance(raw, dict):
        raise ValueError("invalid symbol metadata")
    filters = raw.get("filters")
    if not isinstance(filters, list) or not all(isinstance(f, dict) for f in filters):
        raise ValueError("missing venue filters")
    by_type = {f.get("filterType"): f for f in filters}
    if len(by_type) != len(filters):
        raise ValueError("duplicate venue filter")
    if "PRICE_FILTER" not in by_type or "LOT_SIZE" not in by_type:
        raise ValueError("missing price/quantity filters")
    notional = by_type.get("NOTIONAL", by_type.get("MIN_NOTIONAL"))
    if notional is None:
        raise ValueError("missing minimum notional filter")
    # Hash complete raw venue metadata, including filters not yet used for sizing.
    metadata_version = digest(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    return InstrumentMetadata.model_validate(
        {
            "environment": environment,
            "symbol": raw.get("symbol"),
            "base_asset": raw.get("baseAsset"),
            "quote_asset": raw.get("quoteAsset"),
            "status": raw.get("status"),
            "tick_size": by_type["PRICE_FILTER"].get("tickSize"),
            "quantity_step": by_type["LOT_SIZE"].get("stepSize"),
            "min_quantity": by_type["LOT_SIZE"].get("minQty"),
            "max_quantity": by_type["LOT_SIZE"].get("maxQty"),
            "min_notional": notional.get("minNotional"),
            "metadata_version": metadata_version,
            "observed_at": observed_at,
        }
    )


def normalize_snapshot(
    raw: object, metadata: InstrumentMetadata, observed_at: datetime
) -> BookSnapshot:
    if not isinstance(raw, dict) or type(raw.get("lastUpdateId")) is not int:
        raise ValueError("invalid depth snapshot")
    return BookSnapshot(
        environment=metadata.environment,
        symbol=metadata.symbol,
        metadata_version=metadata.metadata_version,
        last_sequence=raw["lastUpdateId"],
        observed_at=observed_at,
        bids=normalize_levels(raw.get("bids"), metadata),
        asks=normalize_levels(raw.get("asks"), metadata),
    )


def normalize_levels(raw: object, metadata: InstrumentMetadata) -> tuple[BookLevel, ...]:
    if not isinstance(raw, list) or len(raw) > 5000:
        raise ValueError("invalid bounded depth levels")
    result = []
    for level in raw:
        if not isinstance(level, list) or len(level) != 2:
            raise ValueError("invalid depth level")
        parsed = BookLevel(price=level[0], quantity=level[1])
        if not aligned(parsed.price, metadata.tick_size) or not aligned(
            parsed.quantity, metadata.quantity_step
        ):
            raise ValueError("depth violates venue precision")
        result.append(parsed)
    return tuple(result)


def normalize_delta(raw: object, metadata: InstrumentMetadata) -> BookDelta:
    if (
        not isinstance(raw, dict)
        or raw.get("e") != "depthUpdate"
        or raw.get("s") != metadata.symbol
    ):
        raise ValueError("depth event/source mismatch")
    if type(raw.get("E")) is not int or raw["E"] < 0:
        raise ValueError("invalid depth timestamp")
    return BookDelta.model_validate(
        {
            "environment": metadata.environment,
            "symbol": metadata.symbol,
            "metadata_version": metadata.metadata_version,
            "first_sequence": raw.get("U"),
            "last_sequence": raw.get("u"),
            "exchange_at": EPOCH + timedelta(milliseconds=raw["E"]),
            "bids": normalize_levels(raw.get("b"), metadata),
            "asks": normalize_levels(raw.get("a"), metadata),
        }
    )


def normalize_candle(raw: object, metadata: InstrumentMetadata) -> MarketCandle:
    if not isinstance(raw, dict) or raw.get("e") != "kline" or raw.get("s") != metadata.symbol:
        raise ValueError("candle event/source mismatch")
    candle = raw.get("k")
    if not isinstance(candle, dict) or candle.get("x") is not True:
        raise ValueError("closed candle required")
    if any(type(candle.get(key)) is not int for key in ("t", "T", "n")):
        raise ValueError("invalid candle integer fields")
    return MarketCandle.model_validate(
        {
            "environment": metadata.environment,
            "symbol": metadata.symbol,
            "metadata_version": metadata.metadata_version,
            "interval": candle.get("i"),
            "opened_at": EPOCH + timedelta(milliseconds=candle["t"]),
            "closed_at": EPOCH + timedelta(milliseconds=candle["T"]),
            "open_price": candle.get("o"),
            "high_price": candle.get("h"),
            "low_price": candle.get("l"),
            "close_price": candle.get("c"),
            "volume": candle.get("v"),
            "trade_count": candle["n"],
        }
    )
