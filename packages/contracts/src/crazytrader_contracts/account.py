"""Additive fixture account-read provenance and bounded reconciliation reports."""

import json
from decimal import Decimal, localcontext
from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from .market import Hash
from .models import Contract, Identifier, Timestamp, decimal_input
from .venue_rules import strict_object

Finding = Literal[
    "COMPARISON_FAILED",
    "SOURCE_UNAVAILABLE",
    "SOURCE_CHANGED",
    "CONCURRENT_STATE",
    "UNSUPPORTED_ACCOUNT_SCOPE",
    "PERMISSION_MISMATCH",
    "BALANCE_MISMATCH",
    "UNOWNED_ORDER",
    "ORDER_MISMATCH",
    "UNPOSTED_FILL",
    "FILL_MISMATCH",
    "QUOTE_MISMATCH",
    "RESERVATION_MISMATCH",
    "ATTRIBUTION_MISMATCH",
    "STATE_UNRESOLVED",
]


def account_balances(account: dict[str, Any]) -> dict[str, Decimal]:
    if not isinstance(account.get("balances"), list):
        raise ValueError("account balances required")
    result = {}
    for row in account["balances"]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("asset"), str)
            or not row["asset"]
            or row["asset"] in result
        ):
            raise ValueError("unique account asset required")
        if any(not isinstance(row.get(k), str) for k in ("free", "locked")):
            raise ValueError("exact account balance strings required")
        free, locked = decimal_input(row["free"]), decimal_input(row["locked"])
        if free < 0 or locked < 0:
            raise ValueError("negative venue balance")
        with localcontext() as exact:
            exact.prec = 100
            result[row["asset"]] = decimal_input(free + locked)
    if any(type(account.get(k)) is not bool for k in ("canTrade", "canWithdraw")):
        raise ValueError("strict account permission flags required")
    return result


def history_rows(pages: Any, identity: str, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(pages, list) or not 1 <= len(pages) <= 20:
        raise ValueError("bounded completed history pages required")
    result = []
    previous = -1
    for index, page in enumerate(pages):
        if not isinstance(page, list) or len(page) > 1000:
            raise ValueError("bounded history page required")
        if (index == len(pages) - 1) != (len(page) < 1000):
            raise ValueError("short final page must prove pagination completion")
        for row in page:
            if (
                not isinstance(row, dict)
                or type(row.get(identity)) is not int
                or row[identity] <= previous
                or row.get("symbol") != symbol
            ):
                raise ValueError("strict ascending scoped history identity required")
            previous = row[identity]
            result.append(row)
    return result


def validate_order(row: dict[str, Any]) -> None:
    if not isinstance(row, dict):
        raise ValueError("order source object required")
    if type(row.get("orderId")) is not int or row["orderId"] < 0:
        raise ValueError("exact order identity required")
    if row.get("side") not in {"BUY", "SELL"} or not isinstance(row.get("clientOrderId"), str):
        raise ValueError("order scope required")
    for key in ("origQty", "executedQty", "cummulativeQuoteQty"):
        if not isinstance(row.get(key), str) or decimal_input(row[key]) < 0:
            raise ValueError("exact order quantity strings required")
    if decimal_input(row["origQty"]) <= 0 or decimal_input(row["executedQty"]) > decimal_input(
        row["origQty"]
    ):
        raise ValueError("order quantity incoherent")


class VenueAccountRead(Contract):
    schema_version: Literal["1"] = "1"
    source: Literal["OFFICIAL_SDK_LOOPBACK_FIXTURE"] = "OFFICIAL_SDK_LOOPBACK_FIXTURE"
    execution_mode: Literal["SIMULATION"] = "SIMULATION"
    tenant_id: Identifier
    venue_account_ref: Identifier
    anchor_request_id: Identifier
    anchor_request_sha256: Hash
    symbols: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=32)]
    started_at: Timestamp
    finished_at: Timestamp
    available: Annotated[bool, Field(strict=True)]
    raw_json: Annotated[str | None, Field(max_length=10_000_000)]

    def raw(self) -> dict[str, Any]:
        body = json.loads(self.raw_json or "{}", object_pairs_hook=strict_object)
        if not isinstance(body, dict):
            raise ValueError("account source object required")
        return body

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.finished_at < self.started_at or len(set(self.symbols)) != len(self.symbols):
            raise ValueError("account observation scope/time invalid")
        if not self.available:
            return self
        body = self.raw()
        if any(not isinstance(body.get(key), dict) for key in ("before", "after", "history")):
            raise ValueError("complete account source required")
        account_balances(body["before"])
        account_balances(body["after"])
        if set(body["history"]) != set(self.symbols) or not isinstance(body["open"], list):
            raise ValueError("complete configured-symbol history required")
        seen = set()
        for row in body["open"]:
            validate_order(row)
            key = (row.get("symbol"), row["orderId"])
            if key in seen:
                raise ValueError("duplicate open order")
            seen.add(key)
        for symbol in self.symbols:
            if not isinstance(body["history"][symbol], dict) or set(body["history"][symbol]) != {
                "orders",
                "fills",
            }:
                raise ValueError("complete symbol history required")
            for row in history_rows(body["history"][symbol]["orders"], "orderId", symbol):
                validate_order(row)
            for row in history_rows(body["history"][symbol]["fills"], "id", symbol):
                if (
                    type(row.get("orderId")) is not int
                    or type(row.get("time")) is not int
                    or type(row.get("isBuyer")) is not bool
                ):
                    raise ValueError("strict trade identity required")
                for finance_key in ("qty", "price", "quoteQty", "commission"):
                    if (
                        not isinstance(row.get(finance_key), str)
                        or decimal_input(row[finance_key]) < 0
                    ):
                        raise ValueError("exact trade quantity strings required")
                if not isinstance(row.get("commissionAsset"), str):
                    raise ValueError("trade fee asset required")
        return self


class AccountReconciliationReport(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    actor_id: Identifier
    venue_account_ref: Identifier
    source_sha256: Hash
    internal_head_sha256: Hash
    status: Literal["MATCHED", "MISMATCH", "UNAVAILABLE"]
    findings: tuple[Finding, ...]
    occurred_at: Timestamp
    certification_effect: Literal["NONE"] = "NONE"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (self.status == "MATCHED") != (not self.findings) or len(set(self.findings)) != len(
            self.findings
        ):
            raise ValueError("account report findings/verdict mismatch")
        return self
