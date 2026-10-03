"""Additive execution coordination evidence; existing Order.v1 remains unchanged."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .codec import digest
from .market import Hash, Sequence
from .models import Contract, Fill, Identifier, NonNegative, OrderState, Positive, Timestamp


class ExecutionRequest(Contract):
    schema_version: Literal["1"] = "1"
    execution_request_id: Identifier
    order_id: Identifier
    tenant_id: Identifier
    portfolio_id: Identifier
    actor_id: Identifier
    intent_id: Identifier
    intent_sha256: Hash
    risk_record_sha256: Hash
    owner_config_id: Identifier
    policy_bundle_sha256: Hash
    client_order_id: Identifier
    venue_account_ref: Identifier
    symbol: Identifier
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"]
    quantity: Positive
    limit_price: Positive | None
    metadata_version: Hash
    execution_mode: Literal["SIMULATION", "TESTNET", "PAPER", "SHADOW", "LIVE"]
    environment: Literal["SANDBOX", "PUBLIC"]
    created_at: Timestamp
    expires_at: Timestamp

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.expires_at <= self.created_at:
            raise ValueError("execution request must have a positive lifetime")
        if (self.order_type == "LIMIT") != (self.limit_price is not None):
            raise ValueError("LIMIT requires an explicit verified price")
        if self.execution_mode == "TESTNET" and self.environment != "SANDBOX":
            raise ValueError("test execution must use sandbox")
        if self.execution_mode == "LIVE" and self.environment != "PUBLIC":
            raise ValueError("live environment mismatch")
        return self


class ExecutionState(Contract):
    schema_version: Literal["1"] = "1"
    request: ExecutionRequest
    revision: Sequence
    state: OrderState
    filled_quantity: NonNegative
    venue_order_id: Identifier | None
    created_at: Timestamp
    updated_at: Timestamp

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.filled_quantity > self.request.quantity:
            raise ValueError("execution overfill requires reconciliation incident")
        if self.state == OrderState.FILLED and self.filled_quantity != self.request.quantity:
            raise ValueError("FILLED requires full cumulative quantity")
        if (
            self.state == OrderState.PARTIALLY_FILLED
            and not 0 < self.filled_quantity < self.request.quantity
        ):
            raise ValueError("partial state requires partial cumulative fill")
        if self.updated_at < self.created_at or self.created_at != self.request.created_at:
            raise ValueError("execution timestamp mismatch")
        return self


class ExecutionTransition(Contract):
    schema_version: Literal["1"] = "1"
    transition_id: Identifier
    tenant_id: Identifier
    actor_id: Identifier
    execution_request_id: Identifier
    order_id: Identifier
    client_order_id: Identifier
    previous_state: OrderState | None
    previous_revision: Sequence | None
    resulting_state: ExecutionState
    reason_code: Identifier
    evidence_ref: Identifier
    occurred_at: Timestamp

    @model_validator(mode="after")
    def coherent(self) -> Self:
        request = self.resulting_state.request
        if (
            self.tenant_id,
            self.actor_id,
            self.execution_request_id,
            self.order_id,
            self.client_order_id,
        ) != (
            request.tenant_id,
            request.actor_id,
            request.execution_request_id,
            request.order_id,
            request.client_order_id,
        ):
            raise ValueError("execution transition ownership/identity mismatch")
        if self.occurred_at != self.resulting_state.updated_at:
            raise ValueError("transition timestamp mismatch")
        if self.previous_state is None:
            if (
                self.previous_revision is not None
                or self.resulting_state.revision != 0
                or self.resulting_state.state != OrderState.CREATED
            ):
                raise ValueError("initial state must be CREATED revision zero")
        elif (
            self.previous_revision is None
            or self.resulting_state.revision != self.previous_revision + 1
        ):
            raise ValueError("transition revision must advance exactly once")
        return self


TRANSITION_EVENTS = {
    OrderState.SUBMITTING: "OrderSubmissionStarted.v1",
    OrderState.SUBMITTED: "OrderSubmitted.v1",
    OrderState.ACKNOWLEDGED: "OrderAcknowledged.v1",
    OrderState.UNKNOWN: "OrderStateUnknown.v1",
    OrderState.RECOVERY_REQUIRED: "OrderRecoveryStarted.v1",
    OrderState.PARTIALLY_FILLED: "OrderPartiallyFilled.v1",
    OrderState.FILLED: "OrderFilled.v1",
    OrderState.CANCEL_PENDING: "OrderCancelRequested.v1",
    OrderState.CANCELLED: "OrderCancelled.v1",
    OrderState.REJECTED: "OrderRejected.v1",
    OrderState.EXPIRED: "OrderExpired.v1",
}


class VenueOrderObservation(Contract):
    """Mature SDK fixture observation; no claim of external venue certification."""

    schema_version: Literal["1"] = "1"
    source: Literal["OFFICIAL_SDK_LOOPBACK_FIXTURE"] = "OFFICIAL_SDK_LOOPBACK_FIXTURE"
    action: Literal["SUBMIT", "QUERY"]
    tenant_id: Identifier
    venue_account_ref: Identifier
    execution_request_id: Identifier
    request_sha256: Hash
    client_order_id: Identifier
    venue_order_id: Identifier | None
    symbol: Identifier
    side: Literal["BUY", "SELL"]
    requested_quantity: Positive
    filled_quantity: NonNegative
    status: Literal[
        "UNKNOWN", "NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED"
    ]
    observed_at: Timestamp

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.status != "UNKNOWN" and self.venue_order_id is None:
            raise ValueError("observed order requires a verified venue ID")
        if self.filled_quantity > self.requested_quantity:
            raise ValueError("venue overfill requires incident")
        if self.status == "FILLED" and self.filled_quantity != self.requested_quantity:
            raise ValueError("venue FILLED quantity mismatch")
        return self


class VenueFillEvidence(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    venue_account_ref: Identifier
    execution_request_id: Identifier
    client_order_id: Identifier
    venue_order_id: Identifier
    symbol: Identifier
    side: Literal["BUY", "SELL"]
    raw_trade_id: Sequence
    fill: Fill

    @model_validator(mode="after")
    def identity(self) -> Self:
        import json

        scope = digest(
            json.dumps(
                [self.tenant_id, self.venue_account_ref, self.symbol, self.raw_trade_id],
                separators=(",", ":"),
            )
        )
        if self.fill.venue_fill_id != "vfill:" + scope or self.fill.fill_id != "fill:" + scope:
            raise ValueError("fill identity must include account and symbol scope")
        return self


class VenueFillBatch(Contract):
    schema_version: Literal["1"] = "1"
    order_observation: VenueOrderObservation
    source: Literal["OFFICIAL_SDK_LOOPBACK_FIXTURE"] = "OFFICIAL_SDK_LOOPBACK_FIXTURE"
    tenant_id: Identifier
    venue_account_ref: Identifier
    execution_request_id: Identifier
    request_sha256: Hash
    client_order_id: Identifier
    venue_order_id: Identifier
    symbol: Identifier
    side: Literal["BUY", "SELL"]
    available: Annotated[bool, Field(strict=True)]
    complete: Annotated[bool, Field(strict=True)]
    fills: Annotated[tuple[VenueFillEvidence, ...], Field(max_length=1000)]
    raw_json: Annotated[str | None, Field(max_length=2_000_000)]
    observed_at: Timestamp

    @model_validator(mode="after")
    def identity(self) -> Self:
        observation = self.order_observation
        if observation.action != "QUERY" or (
            observation.tenant_id,
            observation.venue_account_ref,
            observation.execution_request_id,
            observation.request_sha256,
            observation.client_order_id,
            observation.venue_order_id,
            observation.symbol,
            observation.side,
        ) != (
            self.tenant_id,
            self.venue_account_ref,
            self.execution_request_id,
            self.request_sha256,
            self.client_order_id,
            self.venue_order_id,
            self.symbol,
            self.side,
        ):
            raise ValueError("fill batch must bind exact query order proof")
        if observation.observed_at > self.observed_at:
            raise ValueError("fill batch cannot predate order query")
        if self.complete and not self.available:
            raise ValueError("unavailable fills cannot claim completeness")
        if not self.available and self.fills:
            raise ValueError("unvalidated batch cannot grant typed fill authority")
        if self.available and self.raw_json is None:
            raise ValueError("validated batch requires preserved source")
        if len({entry.fill.venue_fill_id for entry in self.fills}) != len(self.fills):
            raise ValueError("duplicate fill IDs require explicit source resolution")
        if self.available:
            try:
                rows = json.loads(self.raw_json or "")
                if not isinstance(rows, list) or len(rows) != len(self.fills):
                    raise ValueError("raw fill count mismatch")
                for row, entry in zip(rows, self.fills, strict=True):
                    if not isinstance(row, dict) or any(
                        type(row.get(name)) is not int for name in ("id", "orderId", "time")
                    ):
                        raise ValueError("raw fill integer identity required")
                    if any(
                        not isinstance(row.get(name), str)
                        for name in ("qty", "price", "quoteQty", "commission", "commissionAsset")
                    ):
                        raise ValueError("raw financial strings required")
                    with localcontext() as exact:
                        exact.prec = 100
                        values = (
                            Decimal(row["qty"]),
                            Decimal(row["price"]),
                            Decimal(row["commission"]),
                        )
                        if any(not value.is_finite() for value in values):
                            raise ValueError("non-finite raw financial value")
                        if Decimal(row["quoteQty"]) != values[0] * values[1]:
                            raise ValueError("raw quote amount mismatch")
                    if (
                        row.get("symbol") != self.symbol
                        or str(row["orderId"]) != self.venue_order_id
                        or row["id"] != entry.raw_trade_id
                        or type(row.get("isBuyer")) is not bool
                        or row["isBuyer"] != (self.side == "BUY")
                        or values != (entry.fill.quantity, entry.fill.price, entry.fill.fee_amount)
                        or row["commissionAsset"] != entry.fill.fee_asset
                        or datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=row["time"])
                        != entry.fill.timestamp
                    ):
                        raise ValueError("normalized fill differs from preserved source")
            except (KeyError, TypeError, ArithmeticError, OverflowError) as exc:
                raise ValueError("invalid raw fill source") from exc
        for entry in self.fills:
            if (
                entry.tenant_id,
                entry.venue_account_ref,
                entry.execution_request_id,
                entry.client_order_id,
                entry.venue_order_id,
                entry.symbol,
                entry.side,
            ) != (
                self.tenant_id,
                self.venue_account_ref,
                self.execution_request_id,
                self.client_order_id,
                self.venue_order_id,
                self.symbol,
                self.side,
            ):
                raise ValueError("fill batch ownership/scope mismatch")
        return self


class ExecutionIncident(Contract):
    schema_version: Literal["1"] = "1"
    incident_id: Identifier
    tenant_id: Identifier
    actor_id: Identifier
    execution_request_id: Identifier
    source_digest: Hash
    severity: Literal["CRITICAL"] = "CRITICAL"
    blocks_new_risk: Literal[True] = True
    reason_code: Literal[
        "UNPROVEN_FILL_BATCH",
        "ACCOUNTING_ATTRIBUTION_FAILED",
        "FILL_ID_CONFLICT",
        "CUMULATIVE_MISMATCH",
        "TERMINAL_STATE_CONFLICT",
    ]
    occurred_at: Timestamp
