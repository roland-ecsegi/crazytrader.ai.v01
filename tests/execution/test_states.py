from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from crazytrader_contracts.execution import ExecutionRequest
from crazytrader_contracts.models import OrderState
from crazytrader_execution.state import client_order_id, initial, transition

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def request():
    return ExecutionRequest(
        execution_request_id="exec.v1",
        order_id="order.v1",
        tenant_id="fixture",
        portfolio_id="math",
        actor_id="owner",
        intent_id="intent.v1",
        intent_sha256="a" * 64,
        risk_record_sha256="b" * 64,
        owner_config_id="cfg.v1",
        policy_bundle_sha256="c" * 64,
        client_order_id=client_order_id("exec.v1", "fixture", "fixture-account"),
        venue_account_ref="fixture-account",
        symbol="BTCUSDT",
        side="SELL",
        order_type="MARKET",
        quantity="1",
        limit_price=None,
        metadata_version="d" * 64,
        execution_mode="SIMULATION",
        environment="SANDBOX",
        created_at=NOW,
        expires_at=NOW + timedelta(seconds=5),
    )


def authorized():
    state = initial(request())
    for target in (OrderState.RISK_PENDING, OrderState.AUTHORIZED):
        state = transition(state, target, NOW, "FIXTURE", "fixture").resulting_state
    return state


def test_unknown_is_not_retryable_and_identity_is_stable():
    state = transition(
        authorized(), OrderState.SUBMITTING, NOW, "FIXTURE", "fixture"
    ).resulting_state
    unknown = transition(
        state, OrderState.UNKNOWN, NOW, "AMBIGUOUS_TIMEOUT", "fixture"
    ).resulting_state
    with pytest.raises(ValueError, match="illegal"):
        transition(unknown, OrderState.SUBMITTING, NOW, "RETRY", "fixture")
    recovery = transition(
        unknown, OrderState.RECOVERY_REQUIRED, NOW, "RECOVER", "fixture"
    ).resulting_state
    with pytest.raises(ValueError, match="reconciliation"):
        transition(recovery, OrderState.ACKNOWLEDGED, NOW, "FOUND", "caller-boolean")
    found = transition(
        recovery,
        OrderState.ACKNOWLEDGED,
        NOW,
        "FOUND",
        "reconciliation:fixture",
        venue_id="venue.v1",
    ).resulting_state
    assert found.request.client_order_id == state.request.client_order_id
    with pytest.raises(ValueError, match="identity"):
        transition(found, OrderState.CANCEL_PENDING, NOW, "CANCEL", "fixture", venue_id="changed")


def test_expired_or_backwards_clock_cannot_submit():
    state = authorized()
    with pytest.raises(ValueError, match="expired"):
        transition(state, OrderState.SUBMITTING, state.request.expires_at, "FIXTURE", "fixture")
    with pytest.raises(ValueError, match="backwards"):
        transition(state, OrderState.SUBMITTING, NOW - timedelta(seconds=1), "FIXTURE", "fixture")


def test_timeout_cannot_be_mapped_to_rejected():
    state = transition(
        authorized(), OrderState.SUBMITTING, NOW, "FIXTURE", "fixture"
    ).resulting_state
    with pytest.raises(ValueError, match="authoritative"):
        transition(state, OrderState.REJECTED, NOW, "NETWORK_TIMEOUT", "fixture")
    rejection = transition(state, OrderState.REJECTED, NOW, "VENUE_EXPLICIT_REJECTION", "fixture")
    with pytest.raises(ValueError, match="illegal"):
        transition(rejection.resulting_state, OrderState.SUBMITTING, NOW, "RETRY", "fixture")


def test_partial_fill_cancel_and_terminal_state_are_monotonic():
    state = transition(
        authorized(), OrderState.SUBMITTING, NOW, "FIXTURE", "fixture"
    ).resulting_state
    for target in (OrderState.SUBMITTED, OrderState.ACKNOWLEDGED):
        state = transition(state, target, NOW, "FIXTURE", "fixture").resulting_state
    partial = transition(
        state, OrderState.PARTIALLY_FILLED, NOW, "FILL", "fixture", filled=Decimal("0.4")
    ).resulting_state
    with pytest.raises(ValueError, match="decrease"):
        transition(
            partial, OrderState.PARTIALLY_FILLED, NOW, "FILL", "fixture", filled=Decimal("0.3")
        )
    cancel = transition(
        partial, OrderState.CANCEL_PENDING, NOW, "CANCEL", "fixture"
    ).resulting_state
    closed = transition(
        cancel, OrderState.CANCELLED, NOW, "CANCEL_ACK", "fixture", filled=Decimal("0.5")
    ).resulting_state
    assert closed.filled_quantity == Decimal("0.5")
    with pytest.raises(ValueError, match="illegal"):
        transition(closed, OrderState.SUBMITTING, NOW, "RETRY", "fixture")


def test_request_id_uses_unambiguous_account_tenant_scope():
    assert client_order_id("ab", "c", "d") != client_order_id("a", "bc", "d")
    assert len(client_order_id("exec", "tenant", "account")) == 35
    with pytest.raises(ValueError, match="derive"):
        initial(request().model_copy(update={"client_order_id": "caller-free-form"}))
