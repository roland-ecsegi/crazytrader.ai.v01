"""Explicit durable coordination. Ambiguous send and crash require reconciliation."""

from datetime import datetime
from decimal import Decimal

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.execution import ExecutionRequest, ExecutionState, ExecutionTransition
from crazytrader_contracts.models import OrderState, utc

ALLOWED: dict[OrderState, frozenset[OrderState]] = {
    OrderState.CREATED: frozenset({OrderState.RISK_PENDING, OrderState.DENIED, OrderState.EXPIRED}),
    OrderState.RISK_PENDING: frozenset(
        {OrderState.AUTHORIZED, OrderState.DENIED, OrderState.EXPIRED}
    ),
    OrderState.AUTHORIZED: frozenset(
        {OrderState.SUBMITTING, OrderState.DENIED, OrderState.EXPIRED}
    ),
    OrderState.SUBMITTING: frozenset(
        {OrderState.SUBMITTED, OrderState.UNKNOWN, OrderState.REJECTED}
    ),
    OrderState.SUBMITTED: frozenset(
        {
            OrderState.ACKNOWLEDGED,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.UNKNOWN,
            OrderState.REJECTED,
        }
    ),
    OrderState.ACKNOWLEDGED: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.CANCEL_PENDING: frozenset(
        {OrderState.CANCELLED, OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.UNKNOWN}
    ),
    OrderState.UNKNOWN: frozenset({OrderState.RECOVERY_REQUIRED}),
    OrderState.RECOVERY_REQUIRED: frozenset(
        {
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
        }
    ),
}


def client_order_id(request_id: str, tenant: str, account: str) -> str:
    # Binance client IDs have a bounded ASCII alphabet and maximum36 chars.
    return "ct_" + digest(canonical_identity(request_id, tenant, account))[:32]


def canonical_identity(request_id: str, tenant: str, account: str) -> str:
    import json

    return json.dumps([tenant, account, request_id], separators=(",", ":"))


def initial(request: ExecutionRequest) -> ExecutionState:
    request = ExecutionRequest.model_validate(request.model_dump())
    if request.client_order_id != client_order_id(
        request.execution_request_id, request.tenant_id, request.venue_account_ref
    ):
        raise ValueError("client order ID must derive from durable request identity")
    return ExecutionState(
        request=request,
        revision=0,
        state=OrderState.CREATED,
        filled_quantity="0",
        venue_order_id=None,
        created_at=request.created_at,
        updated_at=request.created_at,
    )


def transition(
    current: ExecutionState,
    target: OrderState,
    now: datetime,
    reason: str,
    evidence: str,
    *,
    filled: Decimal | None = None,
    venue_id: str | None = None,
) -> ExecutionTransition:
    current = ExecutionState.model_validate(current.model_dump())
    utc(now)
    if target not in ALLOWED.get(current.state, frozenset()):
        raise ValueError("illegal execution transition")
    if now < current.updated_at:
        raise ValueError("execution clock moved backwards")
    if (
        target in {OrderState.AUTHORIZED, OrderState.SUBMITTING}
        and now >= current.request.expires_at
    ):
        raise ValueError("expired execution authorization")
    if target == OrderState.REJECTED and (
        reason != "VENUE_EXPLICIT_REJECTION" or current.filled_quantity > 0
    ):
        raise ValueError("only authoritative unfilled rejection can release exposure")
    if current.state == OrderState.RECOVERY_REQUIRED and not evidence.startswith("reconciliation:"):
        raise ValueError("recovery requires canonical reconciliation evidence")
    quantity = current.filled_quantity if filled is None else filled
    if quantity < current.filled_quantity:
        raise ValueError("cumulative fills cannot decrease")
    if quantity > current.filled_quantity and target not in {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
    }:
        raise ValueError("fill change requires explicit accounting transition")
    venue = current.venue_order_id if venue_id is None else venue_id
    if current.venue_order_id is not None and venue != current.venue_order_id:
        raise ValueError("venue order identity cannot change")
    result = ExecutionState.model_validate(
        current.model_dump()
        | {
            "state": target,
            "revision": current.revision + 1,
            "updated_at": now,
            "filled_quantity": quantity,
            "venue_order_id": venue,
        }
    )
    request = current.request
    key = digest(canonical(result) + reason + evidence)
    return ExecutionTransition(
        transition_id="transition:" + key,
        tenant_id=request.tenant_id,
        actor_id=request.actor_id,
        execution_request_id=request.execution_request_id,
        order_id=request.order_id,
        client_order_id=request.client_order_id,
        previous_state=current.state,
        previous_revision=current.revision,
        resulting_state=result,
        reason_code=reason,
        evidence_ref=evidence,
        occurred_at=now,
    )
