"""Typed simulation funding math only. ExecutionStore still denies BUY at L0."""

from decimal import ROUND_CEILING, Decimal, localcontext

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.models import decimal_input
from crazytrader_contracts.simulation import BuyFundingPlan, SimulationCostProfile
from crazytrader_contracts.venue_rules import VenueRuleReceipt


def plan_simulation_buy_funding(
    tenant: str,
    portfolio: str,
    order: str,
    portfolio_currency: str,
    budget_currency: str,
    quantity: Decimal,
    reference_price: Decimal,
    maximum_quote_debit: Decimal,
    costs: SimulationCostProfile,
    rules: VenueRuleReceipt,
) -> BuyFundingPlan:
    costs = SimulationCostProfile.model_validate(costs.model_dump())
    rules = VenueRuleReceipt.model_validate(rules.model_dump())
    quantity, price, cap = map(decimal_input, (quantity, reference_price, maximum_quote_debit))
    with localcontext() as exact:
        exact.prec = 100
        quantum = Decimal(1).scaleb(-rules.rules.quote_precision)
        notional = (quantity * price * (1 + costs.maximum_slippage_bps / 10000)).quantize(
            quantum, rounding=ROUND_CEILING
        )
        fee = (
            (notional * costs.taker_fee_bps / 10000).quantize(quantum, rounding=ROUND_CEILING)
            if costs.fee_asset == rules.rules.symbol_record()["quoteAsset"]
            else Decimal(0)
        )
        reserve = notional + fee
    return BuyFundingPlan(
        tenant_id=tenant,
        portfolio_id=portfolio,
        order_id=order,
        portfolio_currency=portfolio_currency,
        budget_currency=budget_currency,
        quantity=quantity,
        reference_price=price,
        maximum_quote_debit=cap,
        costs=costs,
        cost_profile_sha256=digest(canonical(costs)),
        venue_rules=rules,
        quote_notional_buffered=notional,
        quote_fee_buffer=fee,
        quote_reservation=reserve,
    )
