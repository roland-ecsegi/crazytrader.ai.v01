"""Full rule capture and deterministic MARKET checks; caller provides trusted venue facts.

A passing rule check is only one prerequisite, never risk/policy/certification authority.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from typing import Literal

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.models import decimal_input, utc
from crazytrader_contracts.venue_rules import VenueRuleReceipt, VenueTradingRules
from crazytrader_platform.storage import ConflictError, EventStore

from .archive import S3Artifacts


def capture_rules(
    raw: object, symbol: str, environment: Literal["SANDBOX", "PUBLIC"], now: datetime
) -> VenueTradingRules:
    if not isinstance(raw, dict) or not isinstance(raw.get("symbols"), list):
        raise ValueError("full exchange-info response required")
    matches = [
        row for row in raw["symbols"] if isinstance(row, dict) and row.get("symbol") == symbol
    ]
    if len(matches) != 1:
        raise ValueError("unique requested venue symbol required")
    source = json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return VenueTradingRules(
        symbol=symbol,
        environment=environment,
        observed_at=now,
        metadata_version=digest(json.dumps(matches[0], sort_keys=True, separators=(",", ":"))),
        source_json=source,
        source_sha256=digest(source),
    )


class TradingRuleArchive:
    def __init__(self, store: EventStore, objects: S3Artifacts) -> None:
        self.store, self.objects = store, objects

    def persist(self, tenant: str, rules: VenueTradingRules) -> str:
        rules = VenueTradingRules.model_validate(rules.model_dump())
        # Complete raw source is immutable/read-back checked before any operational receipt.
        self.objects.write(
            "market/rules/source/" + rules.source_sha256 + ".json", rules.source_json.encode()
        )
        body = canonical(VenueRuleReceipt(tenant_id=tenant, rules=rules))
        fingerprint = digest(body)
        with self.store.connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("ledger:" + tenant,)
            )
            conn.execute(
                "INSERT INTO ct_venue_rule_receipts"
                "(digest,tenant_id,environment,symbol,metadata_version,"
                "source_digest,body,observed_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    fingerprint,
                    tenant,
                    rules.environment,
                    rules.symbol,
                    rules.metadata_version,
                    rules.source_sha256,
                    body,
                    rules.observed_at,
                ),
            )
            previous = conn.execute(
                "SELECT digest,body FROM ct_venue_rule_receipts "
                "WHERE tenant_id=%s AND environment=%s AND symbol=%s AND observed_at=%s",
                (tenant, rules.environment, rules.symbol, rules.observed_at),
            ).fetchone()
            if previous is None or previous["digest"] != fingerprint or previous["body"] != body:
                raise ConflictError("venue rules source identity conflict")
        return fingerprint

    def latest(
        self,
        tenant: str,
        environment: Literal["SANDBOX", "PUBLIC"],
        symbol: str,
        now: datetime,
        max_age_seconds: int = 5,
    ) -> VenueRuleReceipt:
        utc(now)
        if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 30:
            raise ValueError("bounded venue rule freshness required")
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT digest,body FROM ct_venue_rule_receipts "
                "WHERE tenant_id=%s AND environment=%s AND symbol=%s "
                "ORDER BY observed_at DESC LIMIT 1",
                (tenant, environment, symbol),
            ).fetchone()
        if row is None:
            raise ValueError("venue rules source unavailable")
        receipt = VenueRuleReceipt.model_validate_json(str(row["body"]))
        rules = receipt.rules
        if digest(canonical(receipt)) != row["digest"] or (
            receipt.tenant_id,
            rules.environment,
            rules.symbol,
        ) != (tenant, environment, symbol):
            raise ConflictError("venue rules receipt integrity mismatch")
        if not timedelta(0) <= now - rules.observed_at <= timedelta(seconds=max_age_seconds):
            raise ValueError("venue rules source stale or future")
        source = self.objects.client.get_object(
            Bucket=self.objects.bucket, Key="market/rules/source/" + rules.source_sha256 + ".json"
        )["Body"]
        try:
            raw = source.read(2_000_001)
        finally:
            source.close()
        if raw != rules.source_json.encode():
            raise ConflictError("venue rules raw source integrity mismatch")
        return receipt


def check_market_rules(
    rules: VenueTradingRules,
    side: Literal["BUY", "SELL"],
    quantity: Decimal,
    now: datetime,
    *,
    reference_prices: dict[int, Decimal],
    reference_observed_at: datetime,
    symbol_open_orders: int | None = None,
    exchange_open_orders: int | None = None,
    projected_base_position: Decimal | None = None,
    max_age_seconds: int = 5,
) -> tuple[str, ...]:
    rules = VenueTradingRules.model_validate(rules.model_dump())
    utc(now)
    quantity = decimal_input(quantity)
    if (
        quantity <= 0
        or side not in {"BUY", "SELL"}
        or type(max_age_seconds) is not int
        or not 1 <= max_age_seconds <= 30
    ):
        raise ValueError("bounded exact MARKET rule input required")
    utc(reference_observed_at)
    if any(type(window) is not int or window < 0 for window in reference_prices):
        raise ValueError("strict reference windows required")
    reasons: list[str] = []
    if not timedelta(0) <= now - rules.observed_at <= timedelta(seconds=max_age_seconds):
        reasons.append("VENUE_RULES_STALE_OR_FUTURE")
    symbol = rules.symbol_record()
    if symbol["status"] != "TRADING" or symbol["isSpotTradingAllowed"] is not True:
        reasons.append("VENUE_SPOT_NOT_TRADING")
    order_types = symbol["orderTypes"]
    if not isinstance(order_types, list) or "MARKET" not in order_types:
        reasons.append("VENUE_MARKET_NOT_SUPPORTED")
    filters = symbol["filters"]
    global_filters = rules.source()["exchangeFilters"]
    if not isinstance(filters, list) or not isinstance(global_filters, list):
        raise ValueError("complete filter arrays required")
    if not any(rule.get("filterType") == "LOT_SIZE" for rule in filters):
        reasons.append("VENUE_LOT_RULE_MISSING")
    try:
        with localcontext() as exact:
            exact.prec = 100
            for rule in filters + global_filters:
                name = rule["filterType"]
                known_fields = {
                    "LOT_SIZE": {"minQty", "maxQty", "stepSize"},
                    "MARKET_LOT_SIZE": {"minQty", "maxQty", "stepSize"},
                    "MIN_NOTIONAL": {"minNotional", "applyToMarket", "avgPriceMins"},
                    "NOTIONAL": {
                        "minNotional",
                        "maxNotional",
                        "applyMinToMarket",
                        "applyMaxToMarket",
                        "avgPriceMins",
                    },
                    "MAX_NUM_ORDERS": {"maxNumOrders"},
                    "EXCHANGE_MAX_NUM_ORDERS": {"maxNumOrders"},
                    "MAX_POSITION": {"maxPosition"},
                    "PRICE_FILTER": {"minPrice", "maxPrice", "tickSize"},
                    "PERCENT_PRICE": {"multiplierUp", "multiplierDown", "avgPriceMins"},
                    "PERCENT_PRICE_BY_SIDE": {
                        "bidMultiplierUp",
                        "bidMultiplierDown",
                        "askMultiplierUp",
                        "askMultiplierDown",
                        "avgPriceMins",
                    },
                    "ICEBERG_PARTS": {"limit"},
                    "MAX_NUM_ALGO_ORDERS": {"maxNumAlgoOrders"},
                    "EXCHANGE_MAX_NUM_ALGO_ORDERS": {"maxNumAlgoOrders"},
                    "MAX_NUM_ICEBERG_ORDERS": {"maxNumIcebergOrders"},
                    "EXCHANGE_MAX_NUM_ICEBERG_ORDERS": {"maxNumIcebergOrders"},
                    "MAX_NUM_ORDER_LISTS": {"maxNumOrderLists"},
                    "EXCHANGE_MAX_NUM_ORDER_LISTS": {"maxNumOrderLists"},
                    "MAX_NUM_ORDER_AMENDS": {"maxNumOrderAmends"},
                    "TRAILING_DELTA": {
                        "minTrailingAboveDelta",
                        "maxTrailingAboveDelta",
                        "minTrailingBelowDelta",
                        "maxTrailingBelowDelta",
                    },
                }
                if name not in known_fields or set(rule) - {"filterType"} != known_fields[name]:
                    reasons.append("VENUE_FILTER_UNSUPPORTED_OR_INCOMPLETE")
                    continue
                if name in {"LOT_SIZE", "MARKET_LOT_SIZE"}:
                    minimum, maximum, step = (
                        decimal_input(rule[k]) for k in ("minQty", "maxQty", "stepSize")
                    )
                    if maximum and minimum > maximum:
                        raise ValueError("invalid quantity interval")
                    if (
                        (minimum and quantity < minimum)
                        or (maximum and quantity > maximum)
                        or (step and quantity % step)
                    ):
                        reasons.append("VENUE_" + name + "_VIOLATION")
                elif name in {"MIN_NOTIONAL", "NOTIONAL"}:
                    flags = (
                        ("applyToMarket",)
                        if name == "MIN_NOTIONAL"
                        else ("applyMinToMarket", "applyMaxToMarket")
                    )
                    if any(type(rule.get(flag)) is not bool for flag in flags):
                        raise ValueError("strict market notional flags required")
                    minutes = rule.get("avgPriceMins")
                    if type(minutes) is not int or minutes < 0:
                        raise ValueError("strict average price window required")
                    minimum_applies = rule[flags[0]]
                    maximum_applies = name == "NOTIONAL" and rule[flags[-1]]
                    if minimum_applies or maximum_applies:
                        price = reference_prices.get(minutes)
                        if price is None or not timedelta(
                            0
                        ) <= now - reference_observed_at <= timedelta(seconds=max_age_seconds):
                            reasons.append("VENUE_NOTIONAL_PRICE_UNKNOWN_OR_STALE")
                            continue
                        price = decimal_input(price)
                        if price <= 0:
                            raise ValueError("positive venue reference price required")
                        notional = quantity * price
                        if minimum_applies and notional < decimal_input(rule["minNotional"]):
                            reasons.append("VENUE_MIN_NOTIONAL_VIOLATION")
                        if maximum_applies and notional > decimal_input(rule["maxNotional"]):
                            reasons.append("VENUE_MAX_NOTIONAL_VIOLATION")
                elif name in {"MAX_NUM_ORDERS", "EXCHANGE_MAX_NUM_ORDERS"}:
                    count = symbol_open_orders if name == "MAX_NUM_ORDERS" else exchange_open_orders
                    limit = rule.get("maxNumOrders")
                    if type(limit) is not int or limit <= 0:
                        raise ValueError("strict venue order limit required")
                    if type(count) is not int or count < 0:
                        reasons.append("VENUE_ORDER_COUNT_UNKNOWN")
                    elif count >= limit:
                        reasons.append("VENUE_ORDER_COUNT_LIMIT")
                elif name == "MAX_POSITION":
                    if side == "BUY":
                        if projected_base_position is None:
                            reasons.append("VENUE_POSITION_UNKNOWN")
                        elif (
                            not Decimal(0)
                            <= decimal_input(projected_base_position)
                            <= decimal_input(rule["maxPosition"])
                        ):
                            reasons.append("VENUE_POSITION_LIMIT")
                elif name in {
                    "PRICE_FILTER",
                    "PERCENT_PRICE",
                    "PERCENT_PRICE_BY_SIDE",
                    "ICEBERG_PARTS",
                    "MAX_NUM_ALGO_ORDERS",
                    "EXCHANGE_MAX_NUM_ALGO_ORDERS",
                    "TRAILING_DELTA",
                    "MAX_NUM_ICEBERG_ORDERS",
                    "EXCHANGE_MAX_NUM_ICEBERG_ORDERS",
                    "MAX_NUM_ORDER_LISTS",
                    "EXCHANGE_MAX_NUM_ORDER_LISTS",
                    "MAX_NUM_ORDER_AMENDS",
                }:
                    # No submitted price, iceberg, algo, list or amend in this MARKET-only path.
                    continue
                else:
                    reasons.append("VENUE_FILTER_UNSUPPORTED")
    except (KeyError, TypeError, ValueError, ArithmeticError):
        reasons.append("VENUE_RULE_INPUT_INVALID")
    return tuple(dict.fromkeys(reasons))
