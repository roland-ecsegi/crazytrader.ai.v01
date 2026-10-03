import os
from datetime import timedelta
from pathlib import Path

import pytest
from crazytrader_contracts.risk import CancellationContext, CancellationRequest
from crazytrader_risk.cancellation import cancellation_input
from crazytrader_risk.policy import LocalProtectivePolicy, OPAClient, PolicyRouter

from .test_engine import NOW

POLICY = Path("infra/policy/authorization.rego")


def fixture():
    cancel = CancellationRequest(
        request_id="cancel-fixture",
        tenant_id="fixture",
        portfolio_id="math",
        order_id="order1",
        client_order_id="client1",
        origin_intent_id="intent1",
        origin_intent_sha256="a" * 64,
        symbol="BTCUSDT",
        environment="SANDBOX",
        execution_mode="SIMULATION",
        created_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
    )
    context = CancellationContext(
        tenant_id="fixture",
        actor_id="owner",
        portfolio_id="math",
        order_id="order1",
        client_order_id="client1",
        origin_intent_id="intent1",
        origin_intent_sha256="a" * 64,
        symbol="BTCUSDT",
        environment="SANDBOX",
        execution_mode="SIMULATION",
        ownership_proof_ref="order-registry.v1",
        venue_account_ref="fixture-account",
        order_state="UNKNOWN",
        observed_at=NOW,
        max_age_seconds=5,
        owner_cancel_authorized=True,
        certification_level="L0",
        owner_live_activated=False,
    )
    return cancel, context


def test_cancel_guard_survives_unknown_order_and_rejects_foreign_expired_and_final():
    cancel, context = fixture()
    assert cancellation_input(cancel, context, NOW, ("order.cancel",), "a" * 64)["cancel_guard"]
    for changed in (
        {"tenant_id": "foreign"},
        {"order_state": "FILLED"},
        {"owner_cancel_authorized": False},
        {"observed_at": NOW - timedelta(seconds=6)},
        {"observed_at": NOW + timedelta(seconds=1)},
    ):
        state = CancellationContext.model_validate(context.model_dump() | changed)
        assert not cancellation_input(cancel, state, NOW, ("order.cancel",), "a" * 64)[
            "cancel_guard"
        ]
    assert not cancellation_input(cancel, context, cancel.expires_at, ("order.cancel",), "a" * 64)[
        "cancel_guard"
    ]
    assert not cancellation_input(cancel, context, NOW, (), "a" * 64)["cancel_guard"]


@pytest.mark.skipif(not os.getenv("CT_TEST_OPA_BINARY"), reason="actual OPA HTTP/CLI required")
def test_actual_cancel_permission_and_offline_protection():
    cancel, context = fixture()
    remote = OPAClient(os.environ["CT_TEST_OPA_URL"], POLICY)
    allowed = remote.authorize_cancel(cancel, context, NOW, ("order.cancel",))
    assert allowed.decision == "ALLOW"
    assert allowed.expires_at == NOW + timedelta(seconds=5)
    assert remote.authorize_cancel(cancel, context, NOW, ()).decision == "DENY"
    foreign = CancellationContext.model_validate(context.model_dump() | {"tenant_id": "foreign"})
    assert remote.authorize_cancel(cancel, foreign, NOW, ("order.cancel",)).decision == "DENY"
    local = LocalProtectivePolicy(
        Path(os.environ["CT_TEST_OPA_BINARY"]),
        os.environ["CT_TEST_OPA_BINARY_SHA256"],
        POLICY,
        Path(os.environ["CT_TEST_OPA_DATA"]),
        enabled=True,
    )
    router = PolicyRouter(OPAClient("http://127.0.0.1:1", POLICY), local, lambda: NOW)
    assert router.authorize_cancel(cancel, context, ("order.cancel",)).decision == "ALLOW"
    assert router.authorize_cancel(cancel, context, ()).decision == "DENY"
