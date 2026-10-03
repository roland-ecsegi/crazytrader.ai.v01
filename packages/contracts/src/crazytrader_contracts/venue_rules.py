"""Additive immutable full official-SDK exchange-info provenance, no order authority."""

import json
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .codec import digest
from .market import Hash
from .models import Contract, Identifier, Timestamp, decimal_input


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate source JSON key")
        result[key] = value
    return result


class VenueTradingRules(Contract):
    schema_version: Literal["1"] = "1"
    environment: Literal["SANDBOX", "PUBLIC"]
    symbol: Identifier
    metadata_version: Hash
    source_sha256: Hash
    source_json: Annotated[str, Field(min_length=2, max_length=2_000_000)]
    observed_at: Timestamp

    def source(self) -> dict[str, object]:
        raw = json.loads(self.source_json, object_pairs_hook=strict_object)
        if not isinstance(raw, dict):
            raise ValueError("exchange-info object required")
        return raw

    def symbol_record(self) -> dict[str, object]:
        symbols = self.source().get("symbols")
        if not isinstance(symbols, list):
            raise ValueError("symbol source required")
        matches = [
            row for row in symbols if isinstance(row, dict) and row.get("symbol") == self.symbol
        ]
        if len(matches) != 1:
            raise ValueError("exactly one matching symbol source required")
        return matches[0]

    @property
    def quote_precision(self) -> int:
        value = self.symbol_record()["quoteAssetPrecision"]
        if type(value) is not int or not 0 <= value <= 18:
            raise ValueError("supported integer quote precision required")
        return value

    @model_validator(mode="after")
    def bound(self) -> Self:
        if digest(self.source_json) != self.source_sha256:
            raise ValueError("venue source hash mismatch")
        symbol = self.symbol_record()
        if (
            digest(json.dumps(symbol, sort_keys=True, separators=(",", ":")))
            != self.metadata_version
        ):
            raise ValueError("venue metadata version mismatch")
        for name in ("baseAsset", "quoteAsset", "status"):
            if not isinstance(symbol.get(name), str) or not symbol[name]:
                raise ValueError("venue instrument identity required")
        for name in ("baseAssetPrecision", "quoteAssetPrecision"):
            value = symbol.get(name)
            if type(value) is not int or not 0 <= value <= 18:
                raise ValueError("supported integer asset precision required")
        if "quotePrecision" in symbol and (
            type(symbol["quotePrecision"]) is not int
            or symbol["quotePrecision"] != self.quote_precision
        ):
            raise ValueError("ambiguous venue quote precision")
        if type(symbol.get("isSpotTradingAllowed")) is not bool:
            raise ValueError("explicit spot trading permission required")
        order_types = symbol.get("orderTypes")
        if not isinstance(order_types, list) or not all(
            isinstance(value, str) for value in order_types
        ):
            raise ValueError("explicit venue order types required")
        for filters in (symbol.get("filters"), self.source().get("exchangeFilters")):
            if not isinstance(filters, list) or not all(
                isinstance(value, dict) for value in filters
            ):
                raise ValueError("complete symbol and exchange filter arrays required")
            names = [value.get("filterType") for value in filters]
            if any(not isinstance(name, str) or not name for name in names) or len(
                set(names)
            ) != len(names):
                raise ValueError("unique named venue filters required")
            for rule in filters:
                for key, value in rule.items():
                    if key == "filterType":
                        continue
                    if isinstance(value, float):
                        raise ValueError("venue financial floats forbidden")
                    if key in {
                        "minPrice",
                        "maxPrice",
                        "tickSize",
                        "minQty",
                        "maxQty",
                        "stepSize",
                        "minNotional",
                        "maxNotional",
                        "maxPosition",
                        "multiplierUp",
                        "multiplierDown",
                        "bidMultiplierUp",
                        "bidMultiplierDown",
                        "askMultiplierUp",
                        "askMultiplierDown",
                    }:
                        if not isinstance(value, str) or decimal_input(value) < 0:
                            raise ValueError("venue nonnegative financial strings required")
        return self


class VenueRuleReceipt(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    rules: VenueTradingRules
