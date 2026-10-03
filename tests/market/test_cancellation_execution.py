"""Actual OPA and signed SDK DELETE: durable ownership/claim, no receipt-based release."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.risk import CancellationRequest
from crazytrader_execution.cancellation import FixtureCancellationRunner
from crazytrader_ledger.store import LedgerStore
from crazytrader_risk.policy import OPAClient
from crazytrader_risk.store import StateUnavailable

from tests.execution.fixture_server import sdk_venue

from .test_fill_settlement import fill, ready, set_truth
from .test_sdk_timeout import transport

pytestmark = pytest.mark.skipif(
    not os.getenv("CT_TEST_S3") or not os.getenv("CT_TEST_OPA_URL"),
    reason="actual services required",
)


def cancellation(backbone, execution, request, endpoint, now=None):
    risk, objects, intent, context, config, policy, original_now = backbone
    now = now or original_now
    config = config.model_copy(
        update={
            "config_id": config.config_id + ":cancel",
            "actor_permissions": ("risk.reduce", "order.cancel"),
        }
    )
    risk.install_owner_configuration(config)
    cancel = CancellationRequest(
        request_id=intent.tenant_id + ":cancel",
        tenant_id=request.tenant_id,
        portfolio_id=request.portfolio_id,
        order_id=request.order_id,
        client_order_id=request.client_order_id,
        origin_intent_id=request.intent_id,
        origin_intent_sha256=request.intent_sha256,
        symbol=request.symbol,
        environment=request.environment,
        execution_mode=request.execution_mode,
        created_at=now,
        expires_at=now + timedelta(seconds=4),
    )
    runner = FixtureCancellationRunner(
        execution,
        transport(endpoint),
        OPAClient(os.environ["CT_TEST_OPA_URL"], Path("infra/policy/authorization.rego")),
        lambda: now,
    )
    return runner, cancel, config


def cancel_count(store, tenant):
    with store.connection() as conn:
        return conn.execute(
            "SELECT count(*) n FROM ct_test_wire_cancels WHERE tenant=%s", (tenant,)
        ).fetchone()["n"]


def reserved(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    return LedgerStore(risk.store).balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC")


def test_duplicate_cancel_is_one_signed_delete_and_stale_market_does_not_trap_reservation(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        # Original market/risk source has expired; cancellation uses registry ownership.
        runner, cancel, _ = cancellation(
            backbone, execution, request, endpoint, now + timedelta(seconds=120)
        )
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(
                    lambda _: runner.cancel_once(request.execution_request_id, cancel, "owner"),
                    range(2),
                )
            )
        assert sum(result is not None for result in results) == 1
        assert cancel_count(risk.store, intent.tenant_id) == 1
        assert execution.load(request.execution_request_id).state == OrderState.CANCEL_PENDING
        assert reserved(backbone) == Decimal("0.1")
        reconciler.clock = runner.clock
        assert reconciler.reconcile(request.execution_request_id).state == OrderState.CANCELLED
        assert reserved(backbone) == 0


def test_accepted_cancel_timeout_retains_reservation_until_query_proof(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(
        risk.store, intent.tenant_id, timeout_after_accept=False, timeout_after_cancel=True
    ) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        runner, cancel, _ = cancellation(backbone, execution, request, endpoint)
        receipt = runner.cancel_once(request.execution_request_id, cancel, "owner")
        assert receipt.outcome == "UNKNOWN"
        assert reserved(backbone) == Decimal("0.1")
        assert runner.cancel_once(request.execution_request_id, cancel, "owner") is None
        assert cancel_count(risk.store, intent.tenant_id) == 1
        assert reconciler.reconcile(request.execution_request_id).state == OrderState.CANCELLED
        assert reserved(backbone) == 0


def test_forged_actor_and_revoked_permission_cannot_reach_sdk(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        runner, cancel, cancel_config = cancellation(backbone, execution, request, endpoint)
        with pytest.raises(StateUnavailable, match="authenticated"):
            runner.cancel_once(request.execution_request_id, cancel, "other")
        risk.install_owner_configuration(
            cancel_config.model_copy(
                update={
                    "config_id": cancel_config.config_id + ":revoked",
                    "actor_permissions": (),
                }
            )
        )
        assert runner.cancel_once(request.execution_request_id, cancel, "owner") is None
        assert cancel_count(risk.store, intent.tenant_id) == 0
        assert execution.load(request.execution_request_id).state == OrderState.ACKNOWLEDGED
        assert reserved(backbone) == Decimal("0.1")
        assert any(
            e.event_type == "OrderCancellationDenied.v1"
            for e in risk.store.pending(limit=1000)
            if e.tenant_id == intent.tenant_id
        )


def test_audit_failure_rolls_back_cancel_claim_before_any_wire_send(backbone, monkeypatch):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        runner, cancel, _ = cancellation(backbone, execution, request, endpoint)

        def failure(*args):
            raise RuntimeError("audit fixture unavailable")

        monkeypatch.setattr(runner, "_audit", failure)
        with pytest.raises(RuntimeError, match="audit fixture"):
            runner.cancel_once(request.execution_request_id, cancel, "owner")
        assert cancel_count(risk.store, intent.tenant_id) == 0
        assert execution.load(request.execution_request_id).state == OrderState.ACKNOWLEDGED
        with risk.store.connection() as conn:
            assert (
                conn.execute(
                    "SELECT 1 FROM ct_cancellation_evaluations WHERE request_id=%s",
                    (cancel.request_id,),
                ).fetchone()
                is None
            )


def test_cancel_race_with_partial_fill_accounts_fee_before_releasing_remainder(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        set_truth(risk.store, request, [fill(request, now)], "PARTIALLY_FILLED")
        runner, cancel, _ = cancellation(backbone, execution, request, endpoint)
        runner.cancel_once(request.execution_request_id, cancel, "owner")
        assert reserved(backbone) == Decimal("0.1")
        state = reconciler.reconcile(request.execution_request_id)
        assert state.state == OrderState.CANCELLED
        assert state.filled_quantity == Decimal("0.04")
        assert reserved(backbone) == 0
        ledger = LedgerStore(risk.store)
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "AVAILABLE", "BTC") == Decimal(
            "0.96"
        )
        assert ledger.balance(
            intent.tenant_id, intent.portfolio_id, "AVAILABLE", "USDT"
        ) == Decimal("3.99")


def test_cancel_receipt_persistence_interruption_never_resends_after_restart(backbone, monkeypatch):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        runner, cancel, _ = cancellation(backbone, execution, request, endpoint)
        original = runner.transport.cancel

        def interrupted(*args):
            original(*args)
            raise RuntimeError("interrupted after venue cancellation")

        monkeypatch.setattr(runner.transport, "cancel", interrupted)
        with pytest.raises(RuntimeError, match="interrupted"):
            runner.cancel_once(request.execution_request_id, cancel, "owner")
        assert reserved(backbone) == Decimal("0.1")
        assert execution.load(request.execution_request_id).state == OrderState.CANCEL_PENDING
        restarted = FixtureCancellationRunner(
            execution, transport(endpoint), runner.policy, lambda: now
        )
        assert restarted.cancel_once(request.execution_request_id, cancel, "owner") is None
        assert cancel_count(risk.store, intent.tenant_id) == 1
        assert reconciler.reconcile(request.execution_request_id).state == OrderState.CANCELLED
        assert reserved(backbone) == 0


def test_known_unposted_incident_does_not_block_owned_cancellation(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        set_truth(risk.store, request, [fill(request, now, fee_asset="BNB")], "PARTIALLY_FILLED")
        assert reconciler.reconcile(request.execution_request_id).state == OrderState.ACKNOWLEDGED
        runner, cancel, _ = cancellation(backbone, execution, request, endpoint)
        assert runner.cancel_once(request.execution_request_id, cancel, "owner") is not None
        assert cancel_count(risk.store, intent.tenant_id) == 1
        # Cancellation protects the owned venue order; unposted fee truth still forbids release.
        assert reconciler.reconcile(request.execution_request_id).state == OrderState.CANCEL_PENDING
        assert reserved(backbone) == Decimal("0.1")
