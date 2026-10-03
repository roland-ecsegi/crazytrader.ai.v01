"""Explicit modeled execution costs. Library funding evidence grants no authority."""

import json
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .codec import canonical, digest
from .market import Hash
from .models import Contract, Identifier, NonNegative, Positive, Timestamp, decimal_input
from .venue_rules import VenueRuleReceipt, strict_object


class SimulationCostProfile(Contract):
    schema_version: Literal["1"] = "1"
    profile_id: Identifier
    source: Literal["CONFIGURED_SIMULATION_ASSUMPTION"] = "CONFIGURED_SIMULATION_ASSUMPTION"
    taker_fee_bps: NonNegative
    maximum_slippage_bps: NonNegative
    fee_asset: Identifier

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.taker_fee_bps > 10000 or self.maximum_slippage_bps > 10000:
            raise ValueError("bounded simulation cost assumptions required")
        return self


class BuyFundingPlan(Contract):
    schema_version: Literal["1"] = "1"
    execution_mode: Literal["SIMULATION"] = "SIMULATION"
    certification_effect: Literal["NONE"] = "NONE"
    tenant_id: Identifier
    portfolio_id: Identifier
    order_id: Identifier
    portfolio_currency: Identifier
    budget_currency: Identifier
    quantity: Positive
    reference_price: Positive
    maximum_quote_debit: Positive
    costs: SimulationCostProfile
    cost_profile_sha256: Hash
    venue_rules: VenueRuleReceipt
    quote_notional_buffered: Positive
    quote_fee_buffer: NonNegative
    quote_reservation: Positive

    @model_validator(mode="after")
    def coherent(self) -> Self:
        symbol = self.venue_rules.rules.symbol_record()
        quote = symbol["quoteAsset"]
        if (
            self.venue_rules.tenant_id != self.tenant_id
            or self.portfolio_currency != quote
            or self.budget_currency != quote
        ):
            raise ValueError(
                "explicit identical quote/budget/portfolio currency required; FX unavailable"
            )
        if self.costs.fee_asset not in {quote, symbol["baseAsset"]}:
            raise ValueError("third-asset fee funding requires independent custody proof")
        if self.cost_profile_sha256 != digest(canonical(self.costs)):
            raise ValueError("simulation cost profile digest mismatch")
        with localcontext() as exact:
            exact.prec = 100
            quantum = Decimal(1).scaleb(-self.venue_rules.rules.quote_precision)
            notional = (
                self.quantity * self.reference_price * (1 + self.costs.maximum_slippage_bps / 10000)
            ).quantize(quantum, rounding=ROUND_CEILING)
            fee = (
                (notional * self.costs.taker_fee_bps / 10000).quantize(
                    quantum, rounding=ROUND_CEILING
                )
                if self.costs.fee_asset == quote
                else Decimal(0)
            )
            if (notional, fee, notional + fee) != (
                self.quote_notional_buffered,
                self.quote_fee_buffer,
                self.quote_reservation,
            ):
                raise ValueError("exact conservatively rounded funding plan required")
        if self.quote_reservation > self.maximum_quote_debit:
            raise ValueError("fee/slippage-inclusive quote debit exceeds configured cap")
        return self


class NativeSimulationJob(Contract):
    """Claimed protective request descriptor; models source, never grants approval."""

    schema_version: Literal["1"] = "1"
    engine_version: Literal["1.221.0"] = "1.221.0"
    execution_mode: Literal["SIMULATION"] = "SIMULATION"
    execution_request_id: Identifier
    order_id: Identifier
    request_sha256: Hash
    tenant_id: Identifier
    portfolio_id: Identifier
    venue_account_ref: Identifier
    client_order_id: Identifier
    symbol: Identifier
    side: Literal["SELL"] = "SELL"
    quantity: Positive
    reference_price: Positive
    reference_risk_record_sha256: Hash
    ledger_head_sha256: Hash
    venue_rules: VenueRuleReceipt
    costs: SimulationCostProfile
    starting_base: NonNegative
    starting_quote: NonNegative
    event_at: Timestamp
    quote_source: Literal["MODELED_FROM_APPROVED_REFERENCE"] = "MODELED_FROM_APPROVED_REFERENCE"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        symbol = self.venue_rules.rules.symbol_record()
        if (
            self.venue_rules.tenant_id != self.tenant_id
            or self.venue_rules.rules.symbol != self.symbol
            or self.starting_base < self.quantity
            or self.costs.fee_asset != symbol["quoteAsset"]
        ):
            raise ValueError("owned covered quote-fee simulation scope required")
        return self


class NativeSimulationReceipt(Contract):
    """Raw native cash/event provenance; additive and distinct from SDK observations."""

    schema_version: Literal["1"] = "1"
    source: Literal["UNMODIFIED_NAUTILUS_SIMULATION"] = "UNMODIFIED_NAUTILUS_SIMULATION"
    job: NativeSimulationJob
    job_sha256: Hash
    observed_at: Timestamp
    available: Annotated[bool, Field(strict=True)]
    raw_json: Annotated[str | None, Field(max_length=2_000_000)]
    certification_effect: Literal["NONE"] = "NONE"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.job_sha256 != digest(canonical(self.job)) or self.observed_at < self.job.event_at:
            raise ValueError("simulation job/time binding mismatch")
        if not self.available:
            return self
        raw = json.loads(self.raw_json or "", object_pairs_hook=strict_object)
        if (
            not isinstance(raw, dict)
            or raw.get("job_sha256") != self.job_sha256
            or raw.get("engine_version") != "1.221.0"
            or type(raw.get("orders")) is not int
            or raw.get("orders") != 1
            or not isinstance(raw.get("fills"), list)
            or len(raw["fills"]) != 1
        ):
            raise ValueError("bounded native filled source required")
        fill = raw["fills"][0]
        if not isinstance(fill, dict) or any(
            not isinstance(fill.get(key), str)
            for key in (
                "last_qty",
                "last_px",
                "commission",
                "client_order_id",
                "venue_order_id",
                "trade_id",
            )
        ):
            raise ValueError("exact native fill source required")
        qty, price = decimal_input(fill["last_qty"]), decimal_input(fill["last_px"])
        fee_text = fill["commission"].split(" ")
        if len(fee_text) != 2:
            raise ValueError("native commission amount/asset required")
        fee = decimal_input(fee_text[0])
        symbol = self.job.venue_rules.rules.symbol_record()
        base, quote = symbol["baseAsset"], symbol["quoteAsset"]
        if (
            qty != self.job.quantity
            or price <= 0
            or fee < 0
            or fee_text[1] != quote
            or fill.get("order_side") != "SELL"
            or fill.get("order_type") != "MARKET"
            or fill.get("currency") != quote
            or fill["client_order_id"] != self.job.client_order_id
            or fill.get("instrument_id") != self.job.symbol + ".BINANCE"
            or type(fill.get("ts_event")) is not int
        ):
            raise ValueError("native filled identity/cost scope mismatch")
        delta = self.job.event_at - datetime(1970, 1, 1, tzinfo=UTC)
        event_ns = (delta.days * 86400 + delta.seconds) * 1000000000 + delta.microseconds * 1000
        if fill["ts_event"] != event_ns:
            raise ValueError("native filled event time differs from job")
        if any(not isinstance(raw.get(key), dict) for key in ("before", "after")):
            raise ValueError("native cash objects required")
        for balances in (raw["before"], raw["after"]):
            if set(balances) != {base, quote} or any(
                not isinstance(v, str) for v in balances.values()
            ):
                raise ValueError("exact native cash source required")
        with localcontext() as exact:
            exact.prec = 100
            before_base, before_quote = (
                decimal_input(raw["before"][base]),
                decimal_input(raw["before"][quote]),
            )
            after_base, after_quote = (
                decimal_input(raw["after"][base]),
                decimal_input(raw["after"][quote]),
            )
            quantum = Decimal(1).scaleb(-self.job.venue_rules.rules.quote_precision)
            gross = after_quote - before_quote + fee
            if (
                before_base != self.job.starting_base
                or before_quote != self.job.starting_quote
                or after_base != before_base - qty
                or after_base < 0
                or after_quote < 0
                or before_quote % quantum != 0
                or after_quote % quantum != 0
                or fee % quantum != 0
                or gross < 0
                or gross % quantum != 0
                or abs(gross - qty * price) >= quantum
                or abs(fee - qty * price * self.job.costs.taker_fee_bps / 10000) >= quantum
                or abs(price - self.job.reference_price) * 10000
                > self.job.reference_price * self.job.costs.maximum_slippage_bps
            ):
                raise ValueError("native actual cash/fee differs from modeled source")
        return self
