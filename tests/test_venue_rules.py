"""Complete rule provenance and conservative MARKET-only venue constraints."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from crazytrader_contracts.venue_rules import VenueTradingRules
from crazytrader_market.rules import capture_rules, check_market_rules

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def exchange_info():
    return {
        "exchangeFilters": [],
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "baseAssetPrecision": 8,
                "quoteAssetPrecision": 8,
                "quotePrecision": 8,
                "status": "TRADING",
                "isSpotTradingAllowed": True,
                "orderTypes": ["MARKET", "LIMIT"],
                "filters": [
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.001",
                        "maxQty": "10",
                        "stepSize": "0.001",
                    },
                    {
                        "filterType": "MARKET_LOT_SIZE",
                        "minQty": "0",
                        "maxQty": "1",
                        "stepSize": "0",
                    },
                    {
                        "filterType": "NOTIONAL",
                        "minNotional": "5",
                        "maxNotional": "50",
                        "applyMinToMarket": True,
                        "applyMaxToMarket": True,
                        "avgPriceMins": 5,
                    },
                ],
            }
        ],
    }


def check(raw=None, **kwargs):
    return check_market_rules(
        capture_rules(raw or exchange_info(), "BTCUSDT", "SANDBOX", NOW),
        "SELL",
        Decimal("0.1"),
        NOW,
        reference_prices={5: Decimal("100")},
        reference_observed_at=NOW,
        **kwargs,
    )


def test_complete_source_hash_precision_and_market_lot_zero_disable_are_exact():
    raw = exchange_info()
    rules = capture_rules(raw, "BTCUSDT", "SANDBOX", NOW)
    assert rules.quote_precision == 8
    assert check() == ()
    with pytest.raises(ValueError, match="source hash"):
        VenueTradingRules.model_validate(rules.model_dump() | {"source_json": "{}"})
    changed = deepcopy(raw)
    changed["symbols"][0]["quotePrecision"] = True
    with pytest.raises(ValueError, match="precision"):
        capture_rules(changed, "BTCUSDT", "SANDBOX", NOW)


@pytest.mark.parametrize(
    "quantity,reason",
    [
        ("0.1001", "VENUE_LOT_SIZE_VIOLATION"),
        ("1.1", "VENUE_MARKET_LOT_SIZE_VIOLATION"),
        ("0.01", "VENUE_MIN_NOTIONAL_VIOLATION"),
        ("0.6", "VENUE_MAX_NOTIONAL_VIOLATION"),
    ],
)
def test_distinct_lot_and_notional_constraints(quantity, reason):
    result = check_market_rules(
        capture_rules(exchange_info(), "BTCUSDT", "SANDBOX", NOW),
        "SELL",
        Decimal(quantity),
        NOW,
        reference_prices={5: Decimal("100")},
        reference_observed_at=NOW,
    )
    assert reason in result


def test_notional_flags_do_not_invent_market_requirement_but_unknown_flags_fail():
    raw = exchange_info()
    rule = raw["symbols"][0]["filters"][-1]
    rule.update(applyMinToMarket=False, applyMaxToMarket=False)
    rules = capture_rules(raw, "BTCUSDT", "SANDBOX", NOW)
    assert (
        check_market_rules(
            rules, "SELL", Decimal("0.1"), NOW, reference_prices={}, reference_observed_at=NOW
        )
        == ()
    )
    rule["applyMinToMarket"] = "false"
    assert "VENUE_RULE_INPUT_INVALID" in check(raw)


def test_reference_window_must_match_and_clock_staleness_is_not_refreshed():
    rules = capture_rules(exchange_info(), "BTCUSDT", "SANDBOX", NOW)
    assert "VENUE_NOTIONAL_PRICE_UNKNOWN_OR_STALE" in check_market_rules(
        rules,
        "SELL",
        Decimal("0.1"),
        NOW,
        reference_prices={0: Decimal("100")},
        reference_observed_at=NOW,
    )
    result = check_market_rules(
        rules,
        "SELL",
        Decimal("0.1"),
        NOW + timedelta(seconds=6),
        reference_prices={5: Decimal("100")},
        reference_observed_at=NOW,
    )
    assert "VENUE_RULES_STALE_OR_FUTURE" in result
    assert "VENUE_NOTIONAL_PRICE_UNKNOWN_OR_STALE" in result


def test_unknown_or_new_filter_fields_deny_instead_of_being_discarded():
    raw = exchange_info()
    raw["symbols"][0]["filters"][0]["newSafetyLimit"] = "0.05"
    assert "VENUE_FILTER_UNSUPPORTED_OR_INCOMPLETE" in check(raw)
    raw = exchange_info()
    raw["exchangeFilters"] = [{"filterType": "NEW_GLOBAL_RESTRICTION", "limit": 1}]
    assert "VENUE_FILTER_UNSUPPORTED_OR_INCOMPLETE" in check(raw)


def test_venue_order_count_requires_account_proof_even_when_market_is_healthy():
    raw = exchange_info()
    raw["symbols"][0]["filters"].append({"filterType": "MAX_NUM_ORDERS", "maxNumOrders": 2})
    assert "VENUE_ORDER_COUNT_UNKNOWN" in check(raw)
    assert "VENUE_ORDER_COUNT_LIMIT" in check(raw, symbol_open_orders=2)
    assert check(raw, symbol_open_orders=1) == ()


@pytest.mark.parametrize(
    "change",
    [
        {"baseAssetPrecision": True},
        {"quoteAssetPrecision": 19},
        {"isSpotTradingAllowed": "true"},
    ],
)
def test_precision_or_permission_coercion_never_creates_authority(change):
    raw = exchange_info()
    raw["symbols"][0].update(change)
    with pytest.raises(ValueError):
        capture_rules(raw, "BTCUSDT", "SANDBOX", NOW)


def test_buy_position_limit_cannot_be_bypassed_by_negative_or_unknown_projection():
    raw = exchange_info()
    raw["symbols"][0]["filters"].append({"filterType": "MAX_POSITION", "maxPosition": "1"})
    rules = capture_rules(raw, "BTCUSDT", "SANDBOX", NOW)
    for projected, reason in (
        (None, "VENUE_POSITION_UNKNOWN"),
        (Decimal("-1"), "VENUE_POSITION_LIMIT"),
        (Decimal("1.1"), "VENUE_POSITION_LIMIT"),
    ):
        assert reason in check_market_rules(
            rules,
            "BUY",
            Decimal("0.1"),
            NOW,
            reference_prices={5: Decimal("100")},
            reference_observed_at=NOW,
            projected_base_position=projected,
        )
