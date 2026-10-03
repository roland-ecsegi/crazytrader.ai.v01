"""Native simulation financial provenance, never impersonating Binance fill sources."""

import json
from decimal import Decimal, localcontext
from typing import Literal, Self

from pydantic import model_validator

from .codec import canonical, digest
from .market import Hash
from .models import Contract, Fill, Identifier, NonNegative, Timestamp, decimal_input
from .simulation import NativeSimulationReceipt
from .venue_rules import strict_object


def sourced_fill(receipt: NativeSimulationReceipt) -> tuple[Fill, Decimal]:
    receipt = NativeSimulationReceipt.model_validate(receipt.model_dump())
    if not receipt.available:
        raise ValueError("available native filled source required")
    raw = json.loads(receipt.raw_json or "", object_pairs_hook=strict_object)
    event, job = raw["fills"][0], receipt.job
    symbol = job.venue_rules.rules.symbol_record()
    identity = digest(canonical(job) + ":" + event["trade_id"])
    fee = decimal_input(event["commission"].split(" ")[0])
    with localcontext() as exact:
        exact.prec = 100
        gross = (
            decimal_input(raw["after"][symbol["quoteAsset"]])
            - decimal_input(raw["before"][symbol["quoteAsset"]])
            + fee
        )
    return Fill(
        fill_id="native-fill:" + identity,
        order_id=job.order_id,
        venue_fill_id="native-trade:" + identity,
        quantity=event["last_qty"],
        price=event["last_px"],
        fee_amount=fee,
        fee_asset=symbol["quoteAsset"],
        timestamp=job.event_at,
    ), gross


class NativeSimulationFill(Contract):
    schema_version: Literal["1"] = "1"
    source: Literal["UNMODIFIED_NAUTILUS_SIMULATION"] = "UNMODIFIED_NAUTILUS_SIMULATION"
    receipt: NativeSimulationReceipt
    fill: Fill
    quote_quantity: NonNegative

    @model_validator(mode="after")
    def sourced(self) -> Self:
        expected, gross = sourced_fill(self.receipt)
        if self.fill != expected or self.quote_quantity != gross:
            raise ValueError("native financial fill disagrees with raw cash/event source")
        return self


class NativeSimulationIncident(Contract):
    schema_version: Literal["1"] = "1"
    incident_id: Identifier
    tenant_id: Identifier
    actor_id: Identifier
    execution_request_id: Identifier
    receipt_digest: Hash
    reason: Literal["SOURCE_UNAVAILABLE", "FINANCIAL_ATTRIBUTION_FAILED"]
    occurred_at: Timestamp
