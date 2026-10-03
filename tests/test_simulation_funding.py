"""Explicit same-currency fee/slippage-inclusive funding, no execution authority."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.simulation import BuyFundingPlan, SimulationCostProfile
from crazytrader_contracts.venue_rules import VenueRuleReceipt
from crazytrader_execution.funding import plan_simulation_buy_funding
from crazytrader_market.rules import capture_rules

from tests.test_venue_rules import exchange_info


def plan(cap="14", currency="USDT", fee_asset="USDT"):
    now = datetime(2026, 10, 3, tzinfo=UTC)
    rules = capture_rules(exchange_info(), "BTCUSDT", "SANDBOX", now)
    receipt = VenueRuleReceipt(tenant_id="tenant", rules=rules)
    costs = SimulationCostProfile(
        profile_id="fixture-costs",
        taker_fee_bps="10",
        maximum_slippage_bps="25",
        fee_asset=fee_asset,
    )
    return plan_simulation_buy_funding(
        "tenant",
        "portfolio",
        "order",
        currency,
        currency,
        Decimal("0.100000000000000001"),
        Decimal("133.33333333"),
        Decimal(cap),
        costs,
        receipt,
    )


def test_buy_debit_ceiling_includes_slippage_and_rounded_quote_fee():
    result = plan()
    assert result.quote_notional_buffered == Decimal("13.36666667")
    assert result.quote_fee_buffer == Decimal("0.01336667")
    assert result.quote_reservation == Decimal("13.38003334")
    assert result.certification_effect == "NONE"
    assert result.cost_profile_sha256 == digest(canonical(result.costs))


@pytest.mark.parametrize("change", [{"cap": "13.38"}, {"currency": "USD"}, {"fee_asset": "BNB"}])
def test_ambiguous_currency_unfunded_third_fee_and_fee_inclusive_cap_fail(change):
    with pytest.raises(ValueError):
        plan(**change)


def test_mutated_profile_or_downward_rounded_reservation_cannot_validate():
    source = plan()
    for altered in (
        source.model_dump() | {"quote_reservation": Decimal("13.38")},
        source.model_dump() | {"cost_profile_sha256": "f" * 64},
    ):
        with pytest.raises(ValueError):
            BuyFundingPlan.model_validate(altered)
