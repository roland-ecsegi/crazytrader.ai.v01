"""Additive actual-quote evidence; independent of risk/execution import direction."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .codec import digest
from .market import Hash, Sequence
from .models import Contract, Fill, Identifier, NonNegative


class QuoteFillIdentity(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    venue_account_ref: Identifier
    execution_request_id: Identifier
    client_order_id: Identifier
    venue_order_id: Identifier
    symbol: Identifier
    side: Literal["BUY", "SELL"]
    raw_trade_id: Sequence
    fill: Fill

    @model_validator(mode="after")
    def identity(self) -> Self:
        import json

        scope = digest(
            json.dumps(
                [self.tenant_id, self.venue_account_ref, self.symbol, self.raw_trade_id],
                separators=(",", ":"),
            )
        )
        if self.fill.venue_fill_id != "vfill:" + scope or self.fill.fill_id != "fill:" + scope:
            raise ValueError("fill identity must include account and symbol scope")
        return self


class VenueQuoteFill(Contract):
    """Authoritative actual quote amount, independently bound to preserved trade row."""

    schema_version: Literal["1"] = "1"
    identity: QuoteFillIdentity
    quote_quantity: NonNegative
    quote_precision: Annotated[int, Field(strict=True, ge=0, le=18)]
    venue_rule_receipt_sha256: Hash
    raw_trade_json: Annotated[str, Field(min_length=2, max_length=65536)]

    @property
    def tenant_id(self) -> Identifier:
        return self.identity.tenant_id

    @property
    def venue_account_ref(self) -> Identifier:
        return self.identity.venue_account_ref

    @property
    def execution_request_id(self) -> Identifier:
        return self.identity.execution_request_id

    @property
    def client_order_id(self) -> Identifier:
        return self.identity.client_order_id

    @property
    def venue_order_id(self) -> Identifier:
        return self.identity.venue_order_id

    @property
    def symbol(self) -> Identifier:
        return self.identity.symbol

    @property
    def side(self) -> Literal["BUY", "SELL"]:
        return self.identity.side

    @property
    def raw_trade_id(self) -> Sequence:
        return self.identity.raw_trade_id

    @property
    def fill(self) -> Fill:
        return self.identity.fill

    @model_validator(mode="after")
    def source_bound(self) -> Self:
        from .models import decimal_input
        from .venue_rules import strict_object

        row = json.loads(self.raw_trade_json, object_pairs_hook=strict_object)
        fill = self.identity.fill
        if not isinstance(row, dict) or any(
            type(row.get(name)) is not int for name in ("id", "orderId", "time")
        ):
            raise ValueError("exact venue quote fill identity required")
        if any(
            not isinstance(row.get(name), str)
            for name in ("qty", "price", "quoteQty", "commission", "commissionAsset")
        ):
            raise ValueError("exact venue quote financial strings required")
        if (
            row.get("symbol"),
            row["id"],
            str(row["orderId"]),
            row.get("isBuyer"),
            decimal_input(row["qty"]),
            decimal_input(row["price"]),
            decimal_input(row["quoteQty"]),
            decimal_input(row["commission"]),
            row["commissionAsset"],
        ) != (
            self.identity.symbol,
            self.identity.raw_trade_id,
            self.identity.venue_order_id,
            self.identity.side == "BUY",
            fill.quantity,
            fill.price,
            self.quote_quantity,
            fill.fee_amount,
            fill.fee_asset,
        ) or type(row.get("isBuyer")) is not bool:
            raise ValueError("actual quote fill differs from preserved source")
        if not 0 <= row["time"] <= 253402300799999:
            raise ValueError("bounded venue quote fill time required")
        if datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=row["time"]) != fill.timestamp:
            raise ValueError("actual quote fill time mismatch")
        with localcontext() as exact:
            exact.prec = 100
            quantum = Decimal(1).scaleb(-self.quote_precision)
            if self.quote_quantity % quantum != 0:
                raise ValueError("actual quote amount violates venue precision")
            if abs(self.quote_quantity - fill.quantity * fill.price) >= quantum:
                raise ValueError("actual quote amount differs beyond one venue quantum")
        return self
