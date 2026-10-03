"""Additive execution coordination evidence; existing Order.v1 remains unchanged."""

from typing import Literal, Self

from pydantic import model_validator

from .market import Hash, Sequence
from .models import Contract, Identifier, NonNegative, OrderState, Positive, Timestamp


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
