import os
from pathlib import Path

import httpx
import pytest
from crazytrader_risk.engine import evaluate
from crazytrader_risk.policy import OPAClient, request

from .test_engine import NOW, fixture, update

POLICY = Path("infra/policy/authorization.rego")


@pytest.mark.skipif(not os.getenv("CT_TEST_OPA_URL"), reason="actual OPA required")
def test_actual_opa_permissions_symbol_expiry_reduction_and_outage():
    intent, context = fixture()
    authorization = evaluate(intent, context, NOW)
    client = OPAClient(os.environ["CT_TEST_OPA_URL"], POLICY)
    assert (
        client.authorize(
            intent, context, authorization, NOW, ("risk.increase",), ("BTCUSDT",)
        ).decision.decision
        == "ALLOW"
    )
    assert (
        client.authorize(intent, context, authorization, NOW, (), ("BTCUSDT",)).decision.decision
        == "DENY"
    )
    assert (
        client.authorize(
            intent, context, authorization, NOW, ("risk.increase",), ()
        ).decision.decision
        == "DENY"
    )
    assert (
        client.authorize(
            intent,
            context,
            authorization,
            authorization.expires_at,
            ("risk.increase",),
            ("BTCUSDT",),
        ).decision.decision
        == "DENY"
    )
    sell, context = fixture("SELL")
    context = update(
        context,
        kill_scope="FLATTEN_APPROVED",
        daily_loss=None,
        drawdown=None,
        market=context.market.model_dump()
        | {"health": "DEGRADED", "reason_code": "STALE_OR_DISCONNECTED"},
        price=None,
    )
    authorization = evaluate(sell, context, NOW)
    assert (
        client.authorize(
            sell, context, authorization, NOW, ("risk.reduce",), ("BTCUSDT",)
        ).decision.decision
        == "ALLOW"
    )
    assert (
        client.authorize(
            sell, context, authorization, NOW, ("risk.increase",), ("BTCUSDT",)
        ).decision.decision
        == "DENY"
    )
    unavailable = OPAClient("http://127.0.0.1:1", POLICY)
    assert (
        unavailable.authorize(
            sell, context, authorization, NOW, ("risk.reduce",), ("BTCUSDT",)
        ).decision.decision
        == "DENY"
    )


def test_forged_allow_fails_before_policy_request():
    intent, context = fixture()
    context = update(context, daily_loss=None)
    authorization = evaluate(intent, context, NOW)
    forged = authorization.model_copy(
        update={"decision": authorization.decision.model_copy(update={"decision": "ALLOW"})}
    )
    with pytest.raises(ValueError, match="not bound"):
        request(intent, context, forged, NOW, ("risk.increase",), ("BTCUSDT",), "a" * 64)


@pytest.mark.parametrize("result", [{"allow": "true"}, {"allow": True}, {}, None])
def test_malformed_response_never_authorizes(monkeypatch, result):
    intent, context = fixture()
    authorization = evaluate(intent, context, NOW)
    original = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"result": result}))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=transport, **kwargs))
    decision = OPAClient("http://fixture.invalid", POLICY).authorize(
        intent, context, authorization, NOW, ("risk.increase",), ("BTCUSDT",)
    )
    assert decision.decision.decision == "DENY"
    assert decision.decision.reason_codes == ("POLICY_UNAVAILABLE_OR_INVALID",)


@pytest.mark.skipif(not os.getenv("CT_TEST_OPA_BINARY"), reason="pinned local OPA required")
def test_actual_local_opa_preserves_approved_reduction_during_http_outage():
    from crazytrader_risk.policy import LocalReductionPolicy, PolicyRouter

    local = LocalReductionPolicy(
        Path(os.environ["CT_TEST_OPA_BINARY"]),
        os.environ["CT_TEST_OPA_BINARY_SHA256"],
        POLICY,
        Path(os.environ["CT_TEST_OPA_DATA"]),
        enabled=True,
    )
    remote = OPAClient("http://127.0.0.1:1", POLICY)
    router = PolicyRouter(remote, local, lambda: NOW)
    sell, context = fixture("SELL")
    context = update(
        context,
        kill_scope="FLATTEN_APPROVED",
        price=None,
        daily_loss=None,
        drawdown=None,
        market=context.market.model_dump()
        | {"health": "DEGRADED", "reason_code": "STALE_OR_DISCONNECTED"},
    )
    authorization = evaluate(sell, context, NOW)
    result = router.authorize(sell, context, authorization, ("risk.reduce",), ("BTCUSDT",))
    assert result.decision.decision == "ALLOW"
    assert (
        router.authorize(sell, context, authorization, (), ("BTCUSDT",)).decision.decision == "DENY"
    )
    buy, context = fixture()
    assert (
        router.authorize(
            buy, context, evaluate(buy, context, NOW), ("risk.increase",), ("BTCUSDT",)
        ).decision.decision
        == "DENY"
    )
    disabled = LocalReductionPolicy(
        Path(os.environ["CT_TEST_OPA_BINARY"]),
        os.environ["CT_TEST_OPA_BINARY_SHA256"],
        POLICY,
        Path(os.environ["CT_TEST_OPA_DATA"]),
        enabled=False,
    )
    assert (
        disabled.authorize(
            sell,
            fixture("SELL")[1],
            evaluate(sell, fixture("SELL")[1], NOW),
            NOW,
            ("risk.reduce",),
            ("BTCUSDT",),
        ).decision.decision
        == "DENY"
    )
