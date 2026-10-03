"""Actual official SDK signed dummy-auth loopback, accepted timeout and durable one-send."""

import os
from decimal import Decimal
from pathlib import Path

import pytest
from crazytrader_contracts.models import OrderState
from crazytrader_execution.fixture_transport import SDKFixtureTransport
from crazytrader_execution.reconciliation import FixtureReconciler
from crazytrader_execution.runner import FixtureExecutionRunner
from crazytrader_execution.store import ExecutionStore
from crazytrader_ledger.store import LedgerStore
from crazytrader_platform.storage import EventStore

from tests.execution.fixture_server import sdk_venue

from .test_execution_boundary import prepared_request

pytestmark = pytest.mark.skipif(
    not os.getenv("CT_TEST_S3") or not os.getenv("CT_TEST_OPA_URL"),
    reason="actual journal/source/OPA and SDK required",
)
ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "services/market-data/sdk/.venv/bin/python"
CHILD = ROOT / "services/execution/sdk_fixture_transport.py"


def transport(endpoint):
    return SDKFixtureTransport(endpoint, PYTHON, CHILD)


def test_sdk_accepted_timeout_persists_unknown_never_resends_and_query_after_restart(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    with sdk_venue(risk.store, intent.tenant_id) as endpoint:
        runner = FixtureExecutionRunner(execution, transport(endpoint), lambda: now)
        assert runner.submit_once(request.execution_request_id).state == OrderState.UNKNOWN
        assert runner.submit_once(request.execution_request_id).state == OrderState.UNKNOWN
    restarted = ExecutionStore(EventStore(os.environ["CT_TEST_DSN"]))
    assert restarted.claim_submission(request.execution_request_id, now) is None
    # Query only, stable ID, after BOTH application object and fixture HTTP restart.
    with sdk_venue(risk.store, intent.tenant_id) as endpoint:
        observation = transport(endpoint).query(
            restarted.load(request.execution_request_id).request, now
        )
        assert observation.status == "NEW"
        assert observation.venue_order_id == "101"
        assert observation.client_order_id == request.client_order_id
        reconciler = FixtureReconciler(restarted, transport(endpoint), lambda: now)
        recovered = reconciler.recover(request.execution_request_id)
        assert recovered.state == OrderState.ACKNOWLEDGED
        assert recovered.venue_order_id == "101"
        assert reconciler.recover(request.execution_request_id) == recovered
        assert restarted.claim_submission(request.execution_request_id, now) is None
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_test_wire_posts WHERE tenant=%s", (intent.tenant_id,)
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_test_wire_orders WHERE tenant=%s", (intent.tenant_id,)
            ).fetchone()["n"]
            == 1
        )
    assert LedgerStore(risk.store).balance(
        intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC"
    ) == Decimal("0.1")


def test_sdk_preserves_exact_decimal_string_on_the_wire(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    # Isolated serializer/fault fixture, not a financially approved alternative size.
    precise = request.model_copy(update={"quantity": Decimal("0.100000000000000001")})
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        observation = transport(endpoint).submit(precise, now)
        assert observation.status == "NEW"
    with risk.store.connection() as conn:
        body = conn.execute(
            "SELECT body FROM ct_test_wire_orders WHERE tenant=%s", (intent.tenant_id,)
        ).fetchone()["body"]
        import json

        assert json.loads(body)["origQty"] == "0.100000000000000001"


def test_sdk_endpoint_cannot_target_binance_or_owner_credentials():
    for endpoint in (
        "https://api.binance.com",
        "http://localhost:8080",
        "http://127.0.0.1:8080/path",
        "http://owner:secret@127.0.0.1:8080",
        "http://127.0.0.1:8080?endpoint=binance",
    ):
        with pytest.raises(ValueError, match="loopback"):
            transport(endpoint)


def test_not_found_is_unresolved_and_reservation_never_released(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    execution.claim_submission(request.execution_request_id, now)
    execution.recover_interrupted_submission(request.execution_request_id, now)
    with sdk_venue(risk.store, intent.tenant_id) as endpoint:
        reconciler = FixtureReconciler(execution, transport(endpoint), lambda: now)
        unresolved = reconciler.recover(request.execution_request_id)
        assert unresolved.state == OrderState.RECOVERY_REQUIRED
        assert reconciler.recover(request.execution_request_id) == unresolved
        assert execution.claim_submission(request.execution_request_id, now) is None
    assert LedgerStore(risk.store).balance(
        intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC"
    ) == Decimal("0.1")


def test_crash_after_venue_acceptance_before_local_receipt_persistence(backbone, monkeypatch):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        runner = FixtureExecutionRunner(execution, transport(endpoint), lambda: now)

        def interrupted(observation):
            raise RuntimeError("injected process interruption before receipt persistence")

        monkeypatch.setattr(execution, "record_submission", interrupted)
        with pytest.raises(RuntimeError, match="interruption"):
            runner.submit_once(request.execution_request_id)
        assert runner.submit_once(request.execution_request_id).state == OrderState.SUBMITTING
    restarted = ExecutionStore(EventStore(os.environ["CT_TEST_DSN"]))
    assert (
        restarted.recover_interrupted_submission(request.execution_request_id, now).state
        == OrderState.UNKNOWN
    )
    with sdk_venue(risk.store, intent.tenant_id) as endpoint:
        assert (
            FixtureReconciler(restarted, transport(endpoint), lambda: now)
            .recover(request.execution_request_id)
            .state
            == OrderState.ACKNOWLEDGED
        )
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_test_wire_posts WHERE tenant=%s", (intent.tenant_id,)
            ).fetchone()["n"]
            == 1
        )
