"""Additive signed loopback lookup source; lookup alone never establishes absence."""

import json
from datetime import timedelta
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .account import VenueAccountRead, history_rows
from .codec import canonical, digest
from .execution import ExecutionRequest, ExecutionState
from .market import Hash
from .models import Contract, Identifier, OrderState, Timestamp
from .venue_rules import strict_object


class FixtureOrderLookup(Contract):
    schema_version: Literal["1"] = "1"
    source: Literal["OFFICIAL_SDK_LOOPBACK_FIXTURE"] = "OFFICIAL_SDK_LOOPBACK_FIXTURE"
    request: ExecutionRequest
    started_at: Timestamp
    finished_at: Timestamp
    available: Annotated[bool, Field(strict=True)]
    http_status: Annotated[int, Field(strict=True, ge=100, le=599)] | None
    raw_json: Annotated[str | None, Field(max_length=64_000)]

    def raw(self) -> dict[str, object]:
        value = json.loads(self.raw_json or "{}", object_pairs_hook=strict_object)
        if not isinstance(value, dict):
            raise ValueError("lookup source object required")
        return value

    @property
    def explicitly_not_found(self) -> bool:
        if not self.available or self.http_status != 400:
            return False
        raw = self.raw()
        return (
            set(raw) == {"code", "msg"}
            and type(raw.get("code")) is int
            and raw.get("code") == -2013
            and isinstance(raw.get("msg"), str)
            and bool(raw.get("msg"))
        )

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (
            self.finished_at < self.started_at
            or self.request.execution_mode != "SIMULATION"
            or self.request.side != "SELL"
        ):
            raise ValueError("scoped simulation lookup clock required")
        if self.available:
            if self.http_status is None or self.raw_json is None:
                raise ValueError("captured HTTP source required")
            self.raw()
        return self


class FixtureAbsenceAssessment(Contract):
    schema_version: Literal["1"] = "1"
    coverage: Literal["SEQUENTIAL_ID_ZERO_COMPLETE_LOOPBACK_FIXTURE"] = (
        "SEQUENTIAL_ID_ZERO_COMPLETE_LOOPBACK_FIXTURE"
    )
    state: ExecutionState
    lookup: FixtureOrderLookup
    account: VenueAccountRead
    internal_head_sha256: Hash
    actor_id: Identifier
    verdict: Literal["PROVEN", "DENIED"]
    findings: tuple[Identifier, ...]
    occurred_at: Timestamp
    certification_effect: Literal["NONE"] = "NONE"
    financial_effect: Literal["NONE"] = "NONE"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        request = self.state.request
        if (
            request != self.lookup.request
            or request.actor_id != self.actor_id
            or (
                self.account.tenant_id,
                self.account.venue_account_ref,
                self.account.anchor_request_id,
                self.account.anchor_request_sha256,
            )
            != (
                request.tenant_id,
                request.venue_account_ref,
                request.execution_request_id,
                digest(canonical(request)),
            )
            or request.symbol not in self.account.symbols
            or (self.verdict == "PROVEN") != (not self.findings)
            or len(set(self.findings)) != len(self.findings)
        ):
            raise ValueError("absence assessment scope/verdict mismatch")
        if self.verdict == "PROVEN":
            raw = self.account.raw()
            if (
                self.state.state not in {OrderState.UNKNOWN, OrderState.RECOVERY_REQUIRED}
                or self.state.filled_quantity != 0
                or self.state.venue_order_id is not None
                or not self.lookup.explicitly_not_found
                or not self.account.available
                or raw["before"] != raw["after"]
                or not self.state.updated_at
                <= self.lookup.started_at
                <= self.lookup.finished_at
                <= self.account.started_at
                <= self.account.finished_at
                <= self.occurred_at
                or self.occurred_at - self.lookup.started_at > timedelta(seconds=10)
                or self.occurred_at - self.account.finished_at > timedelta(seconds=5)
            ):
                raise ValueError("bounded original zero-fill absence sources required")
            for account in (raw["before"], raw["after"]):
                if (
                    account.get("canTrade") is not True
                    or account.get("canWithdraw") is not False
                    or account.get("permissions") != ["SPOT"]
                    or account.get("accountType") != "SPOT"
                ):
                    raise ValueError("absence source account permission mismatch")
            orders = raw["open"] + [
                r
                for symbol in self.account.symbols
                for r in history_rows(raw["history"][symbol]["orders"], "orderId", symbol)
            ]
            if any(row["clientOrderId"] == request.client_order_id for row in orders):
                raise ValueError("original order is present in absence source")
        return self


class FixtureTimedOrderLookup(Contract):
    schema_version: Literal["1"] = "1"
    lookup: FixtureOrderLookup
    raw_server_date: Annotated[str | None, Field(max_length=128)]
    server_date: Timestamp | None
    maximum_signature_window_ms: Literal[5000] = 5000
    clock_source: Literal["LOOPBACK_HTTP_DATE_HEADER"] = "LOOPBACK_HTTP_DATE_HEADER"

    @model_validator(mode="after")
    def source_clock(self) -> Self:
        if (self.raw_server_date is None) != (self.server_date is None):
            raise ValueError("paired original server clock source required")
        if self.server_date is not None:
            from email.utils import parsedate_to_datetime

            if parsedate_to_datetime(self.raw_server_date or "") != self.server_date:
                raise ValueError("server clock differs from captured HTTP date")
        return self
