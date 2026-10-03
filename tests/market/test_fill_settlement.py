"""Actual SDK fill/fee source, exact atomic journal and terminal remainder/suspense."""

import json
import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from crazytrader_contracts.models import OrderState
from crazytrader_execution.reconciliation import FixtureReconciler
from crazytrader_execution.runner import FixtureExecutionRunner
from crazytrader_execution.settlement import FillSettlement
from crazytrader_ledger.store import LedgerStore
from crazytrader_risk.store import StateUnavailable

from tests.execution.fixture_server import sdk_venue

from .test_execution_boundary import prepared_request
from .test_sdk_timeout import transport

pytestmark = pytest.mark.skipif(
    not os.getenv("CT_TEST_S3") or not os.getenv("CT_TEST_OPA_URL"),
    reason="actual stores/SDK required",
)


def fill(request, now, raw_id=1, quantity="0.04", fee="0.01", fee_asset="USDT"):
    delta = now - datetime(1970, 1, 1, tzinfo=UTC)
    milliseconds = delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000
    return {
        "symbol": request.symbol,
        "id": raw_id,
        "orderId": 101,
        "orderListId": -1,
        "price": "100",
        "qty": quantity,
        "quoteQty": format(Decimal(quantity) * 100, "f"),
        "commission": fee,
        "commissionAsset": fee_asset,
        "time": milliseconds,
        "isBuyer": False,
        "isMaker": False,
        "isBestMatch": True,
    }


def set_truth(store, request, rows, status):
    with store.connection() as conn:
        order = json.loads(
            conn.execute(
                "SELECT body FROM ct_test_wire_orders WHERE tenant=%s AND client_id=%s",
                (request.tenant_id, request.client_order_id),
            ).fetchone()["body"]
        )
        order.update(
            status=status,
            executedQty=format(sum((Decimal(row["qty"]) for row in rows), Decimal(0)), "f"),
        )
        conn.execute(
            "UPDATE ct_test_wire_orders SET body=%s WHERE tenant=%s AND client_id=%s",
            (json.dumps(order), request.tenant_id, request.client_order_id),
        )
        for row in rows:
            conn.execute(
                "INSERT INTO ct_test_wire_fills(tenant,trade_id,body) VALUES(%s,%s,%s) "
                "ON CONFLICT(tenant,trade_id) DO UPDATE SET body=excluded.body",
                (request.tenant_id, row["id"], json.dumps(row)),
            )


def ready(backbone, endpoint):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    FixtureExecutionRunner(execution, transport(endpoint), lambda: now).submit_once(
        request.execution_request_id
    )
    reconciler = FixtureReconciler(execution, transport(endpoint), lambda: now)
    assert reconciler.recover(request.execution_request_id).state == OrderState.ACKNOWLEDGED
    return execution, request, reconciler


def test_partial_fill_replay_then_terminal_cancel_releases_only_proven_remainder(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        rows = [fill(request, now)]
        set_truth(risk.store, request, rows, "PARTIALLY_FILLED")
        state = reconciler.reconcile(request.execution_request_id)
        assert state.state == OrderState.PARTIALLY_FILLED
        assert state.filled_quantity == Decimal("0.04")
        ledger = LedgerStore(risk.store)
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC") == Decimal(
            "0.06"
        )
        assert ledger.balance(
            intent.tenant_id, intent.portfolio_id, "AVAILABLE", "USDT"
        ) == Decimal("3.99")
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "FEES", "USDT") == Decimal(
            "0.01"
        )
        assert reconciler.reconcile(request.execution_request_id) == state
        set_truth(risk.store, request, rows, "CANCELED")
        cancelled = reconciler.reconcile(request.execution_request_id)
        assert cancelled.state == OrderState.CANCELLED
        assert cancelled.filled_quantity == Decimal("0.04")
        with risk.store.connection() as conn:
            sources = conn.execute(
                "SELECT body FROM ct_execution_fill_sources WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchall()
            assert any(
                json.loads(row["body"])["order_observation"]["status"] == "CANCELED"
                for row in sources
            )
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC") == 0
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "AVAILABLE", "BTC") == Decimal(
            "0.96"
        )
        assert reconciler.reconcile(request.execution_request_id) == cancelled
        with risk.store.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_execution_fills WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["n"]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_reconciliation_incidents WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["n"]
                == 0
            )


def test_two_fills_full_settlement_and_replay_are_exact(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        rows = [fill(request, now), fill(request, now, raw_id=2, quantity="0.06", fee="0.02")]
        set_truth(risk.store, request, rows, "FILLED")
        state = reconciler.reconcile(request.execution_request_id)
        assert state.state == OrderState.FILLED
        assert state.filled_quantity == Decimal("0.1")
        ledger = LedgerStore(risk.store)
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC") == 0
        assert ledger.balance(
            intent.tenant_id, intent.portfolio_id, "AVAILABLE", "USDT"
        ) == Decimal("9.97")
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "FEES", "USDT") == Decimal(
            "0.03"
        )
        assert reconciler.reconcile(request.execution_request_id) == state


def test_known_fill_with_unowned_fee_is_preserved_in_suspense_and_blocks_healthy_assertion(
    backbone,
):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        set_truth(risk.store, request, [fill(request, now, fee_asset="BNB")], "PARTIALLY_FILLED")
        state = reconciler.reconcile(request.execution_request_id)
        assert (
            state.state == OrderState.ACKNOWLEDGED
        )  # known truth recorded; no partial financial commit
        ledger = LedgerStore(risk.store)
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC") == Decimal(
            "0.1"
        )
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "AVAILABLE", "USDT") == 0
        with risk.store.connection() as conn:
            row = conn.execute(
                "SELECT s.body FROM ct_execution_fill_sources s "
                "JOIN ct_execution_suspense p ON p.source_digest=s.digest "
                "WHERE s.execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()
            assert "BNB" in row["body"]
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_reconciliation_incidents WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["n"]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_execution_fills WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["n"]
                == 0
            )
        with pytest.raises(StateUnavailable, match="healthy accounting"):
            risk.validate_backbone(context, objects, now)
        critical = [
            e
            for e in risk.store.pending(limit=1000)
            if e.tenant_id == intent.tenant_id
            and e.event_type == "ReconciliationCriticalMismatch.v1"
        ]
        assert len(critical) == 1
        assert risk.store.consume_audit(critical[0])
        assert critical[0].event_id in risk.store.notifications()


def test_changed_fill_body_cannot_rewrite_the_journal(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        rows = [fill(request, now)]
        set_truth(risk.store, request, rows, "PARTIALLY_FILLED")
        original = reconciler.reconcile(request.execution_request_id)
        changed = rows[0] | {"commission": "0.02"}
        set_truth(risk.store, request, [changed], "PARTIALLY_FILLED")
        assert reconciler.reconcile(request.execution_request_id) == original
        assert LedgerStore(risk.store).balance(
            intent.tenant_id, intent.portfolio_id, "FEES", "USDT"
        ) == Decimal("0.01")
        with risk.store.connection() as conn:
            assert (
                conn.execute(
                    "SELECT reason_code FROM ct_reconciliation_incidents WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["reason_code"]
                == "FILL_ID_CONFLICT"
            )


def test_duplicate_unposted_fault_is_one_incident_across_observation_clocks(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        set_truth(risk.store, request, [fill(request, now, fee_asset="BNB")], "PARTIALLY_FILLED")
        first = reconciler.reconcile(request.execution_request_id)
        from datetime import timedelta

        later = FixtureReconciler(
            execution, transport(endpoint), lambda: now + timedelta(milliseconds=1)
        )
        assert later.reconcile(request.execution_request_id) == first
        with risk.store.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_reconciliation_incidents WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["n"]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_execution_fill_sources "
                    "WHERE execution_request_id=%s",
                    (request.execution_request_id,),
                ).fetchone()["n"]
                == 2
            )


def test_order_status_proof_cannot_be_swapped_and_terminal_fee_conflict_is_preserved(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        rows = [fill(request, now)]
        set_truth(risk.store, request, rows, "CANCELED")
        adapter = transport(endpoint)
        observation = adapter.query(request, now)
        batch = adapter.fills(request, observation, now)
        altered = list(batch.fills)
        altered[0] = altered[0].model_copy(
            update={"fill": altered[0].fill.model_copy(update={"fee_amount": Decimal("0.02")})}
        )
        with pytest.raises(ValueError, match="preserved source"):
            type(batch).model_validate(batch.model_dump() | {"fills": tuple(altered)})
        with pytest.raises(StateUnavailable, match="source proof mismatch"):
            FillSettlement(execution).apply(
                observation.model_copy(update={"status": "PARTIALLY_FILLED"}), batch
            )
        assert LedgerStore(risk.store).balance(
            intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC"
        ) == Decimal("0.1")
        closed = FillSettlement(execution).apply(observation, batch)
        assert closed.state == OrderState.CANCELLED
        set_truth(risk.store, request, [rows[0] | {"commission": "0.02"}], "CANCELED")
        observation = adapter.query(request, now)
        batch = adapter.fills(request, observation, now)
        assert FillSettlement(execution).apply(observation, batch) == closed
        with risk.store.connection() as conn:
            assert (
                conn.execute(
                    "SELECT reason_code FROM ct_reconciliation_incidents WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["reason_code"]
                == "FILL_ID_CONFLICT"
            )


def test_signed_sdk_actual_rounded_quote_does_not_infer_extra_cash(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        row = fill(request, now) | {"price": "100.00000001", "quoteQty": "4.00000000"}
        set_truth(risk.store, request, [row], "PARTIALLY_FILLED")
        state = reconciler.reconcile(request.execution_request_id)
        assert state.state == OrderState.PARTIALLY_FILLED
        assert LedgerStore(risk.store).balance(
            intent.tenant_id, intent.portfolio_id, "AVAILABLE", "USDT"
        ) == Decimal("3.99")
        assert reconciler.reconcile(request.execution_request_id) == state
        with risk.store.connection() as conn:
            body = conn.execute(
                "SELECT body FROM ct_ledger_transactions WHERE tenant_id=%s "
                "AND transaction_type='FILL'",
                (intent.tenant_id,),
            ).fetchone()["body"]
            assert json.loads(body)["quote_evidence"]["quote_quantity"] == "4.00000000"


def test_v1_posted_fill_upgrade_to_actual_quote_path_cannot_double_post(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        set_truth(risk.store, request, [fill(request, now)], "PARTIALLY_FILLED")
        adapter = transport(endpoint)
        observation = adapter.query(request, now)
        legacy = adapter.fills(request, observation, now)
        original = FillSettlement(execution).apply(observation, legacy)
        assert original.state == OrderState.PARTIALLY_FILLED
        assert reconciler.reconcile(request.execution_request_id) == original
        with risk.store.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_ledger_transactions WHERE tenant_id=%s "
                    "AND transaction_type='FILL'",
                    (intent.tenant_id,),
                ).fetchone()["n"]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT 1 FROM ct_reconciliation_incidents WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()
                is None
            )


def test_inconsistent_actual_quote_remains_unposted_source_and_reservation(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        row = fill(request, now) | {"quoteQty": "3.9"}
        set_truth(risk.store, request, [row], "PARTIALLY_FILLED")
        assert reconciler.reconcile(request.execution_request_id).state == OrderState.ACKNOWLEDGED
        ledger = LedgerStore(risk.store)
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC") == Decimal(
            "0.1"
        )
        assert ledger.balance(intent.tenant_id, intent.portfolio_id, "AVAILABLE", "USDT") == 0
        with risk.store.connection() as conn:
            assert (
                conn.execute(
                    "SELECT reason_code FROM ct_reconciliation_incidents WHERE tenant_id=%s",
                    (intent.tenant_id,),
                ).fetchone()["reason_code"]
                == "UNPROVEN_FILL_BATCH"
            )
