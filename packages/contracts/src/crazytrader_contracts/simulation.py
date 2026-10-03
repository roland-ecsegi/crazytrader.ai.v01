"""Explicit modeled execution costs. Library funding evidence grants no authority."""

from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Literal, Self

from pydantic import model_validator

from .codec import canonical, digest
from .market import Hash
from .models import Contract, Identifier, NonNegative, Positive
from .venue_rules import VenueRuleReceipt


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
