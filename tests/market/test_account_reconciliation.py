"""Actual official-SDK account reads and source-first immutable reconciliation."""

import json
import os

import psycopg
import pytest
from crazytrader_contracts.codec import digest
from crazytrader_execution.account_reconciliation import FixtureAccountReconciler
from crazytrader_risk.store import StateUnavailable

from tests.execution.fixture_server import sdk_venue

from .test_fill_settlement import fill, ready, set_truth
from .test_sdk_timeout import transport

pytestmark = pytest.mark.skipif(
    not os.getenv("CT_TEST_S3") or not os.getenv("CT_TEST_OPA_URL"),
    reason="actual services required",
)


def test_complete_fixture_account_read_matches_registered_open_order_and_balances(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        report = FixtureAccountReconciler(execution, transport(endpoint)).run(
            request.execution_request_id
        )
        assert report.status == "MATCHED", report.findings
        assert report.certification_effect == "NONE"
        with risk.store.connection() as conn:
            source = conn.execute(
                "SELECT body FROM ct_account_read_sources WHERE digest=%s", (report.source_sha256,)
            ).fetchone()
            assert digest(str(source["body"])) == report.source_sha256
            assert (
                conn.execute(
                    "SELECT count(*) n FROM ct_test_wire_posts WHERE tenant=%s", (intent.tenant_id,)
                ).fetchone()["n"]
                == 1
            )
        event = next(
            e
            for e in risk.store.pending(limit=1000)
            if e.tenant_id == intent.tenant_id and e.event_type == "AccountReconciliationMatched.v1"
        )
        assert risk.store.consume_audit(event)
        assert not risk.store.consume_audit(event)
        with risk.store.connection() as conn:
            with pytest.raises(psycopg.Error, match="append-only"):
                conn.execute(
                    "DELETE FROM ct_account_read_sources WHERE digest=%s", (report.source_sha256,)
                )


def test_unowned_order_latches_new_risk_without_authorizing_cancel_release(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        with risk.store.connection() as conn:
            row = conn.execute(
                "SELECT body FROM ct_test_wire_orders WHERE tenant=%s", (intent.tenant_id,)
            ).fetchone()
            body = json.loads(row["body"])
            body.update(orderId=202, clientOrderId="external-owner-order")
            conn.execute(
                "INSERT INTO ct_test_wire_orders(tenant,client_id,body) VALUES(%s,%s,%s)",
                (intent.tenant_id, "external-owner-order", json.dumps(body)),
            )
        report = FixtureAccountReconciler(execution, transport(endpoint)).run(
            request.execution_request_id
        )
        assert "UNOWNED_ORDER" in report.findings
        with pytest.raises(StateUnavailable, match="incident"):
            execution.prepare(request, objects, now)
        with pytest.raises(StateUnavailable, match="healthy accounting"):
            risk.publish_context(context, objects, now)
        event = next(
            e
            for e in risk.store.pending(limit=1000)
            if e.tenant_id == intent.tenant_id
            and e.event_type == "AccountReconciliationMismatch.v1"
        )
        assert risk.store.consume_audit(event)
        assert event.event_id in risk.store.notifications()


def test_account_source_is_durable_when_comparison_raises(backbone, monkeypatch):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        reconciler = FixtureAccountReconciler(execution, transport(endpoint))

        def fail(*args):
            raise StateUnavailable("comparison interrupted")

        monkeypatch.setattr(reconciler, "_compare", fail)
        report = reconciler.run(request.execution_request_id)
        assert report.status == "UNAVAILABLE"
        assert "COMPARISON_FAILED" in report.findings
        with pytest.raises(StateUnavailable, match="incident"):
            execution.prepare(request, objects, now)
        with risk.store.connection() as conn:
            count = conn.execute(
                "SELECT count(*) n FROM ct_account_read_sources WHERE tenant_id=%s",
                (intent.tenant_id,),
            ).fetchone()["n"]
        assert count == 1


def test_balance_and_withdrawal_permission_mismatch_are_explicit(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        sdk = transport(endpoint)
        source = sdk.account(request, (request.symbol,))
        assert source.available
        account = source.raw()["after"]
        account.update(canWithdraw=True)
        account["balances"][0]["free"] = "0.9"
        with risk.store.connection() as conn:
            conn.execute(
                "INSERT INTO ct_test_wire_accounts(tenant,body) VALUES(%s,%s)",
                (intent.tenant_id, json.dumps(account)),
            )
        report = FixtureAccountReconciler(execution, sdk).run(request.execution_request_id)
        assert {"BALANCE_MISMATCH", "PERMISSION_MISMATCH"} <= set(report.findings)


def test_cumulative_quote_and_missing_cost_provenance_prevent_false_account_health(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        rows = [fill(request, now)]
        set_truth(risk.store, request, rows, "PARTIALLY_FILLED")
        order_reconciler.reconcile(request.execution_request_id)
        sdk = transport(endpoint)
        account = sdk.account(request, (request.symbol,)).raw()["after"]
        account["balances"] = [
            {"asset": "BTC", "free": "0.96", "locked": "0"},
            {"asset": "USDT", "free": "3.99", "locked": "0"},
        ]
        with risk.store.connection() as conn:
            conn.execute(
                "INSERT INTO ct_test_wire_accounts(tenant,body) VALUES(%s,%s)",
                (intent.tenant_id, json.dumps(account)),
            )
            row = conn.execute(
                "SELECT body FROM ct_test_wire_orders WHERE tenant=%s", (intent.tenant_id,)
            ).fetchone()
            body = json.loads(row["body"])
            body["cummulativeQuoteQty"] = "3.99"
            conn.execute(
                "UPDATE ct_test_wire_orders SET body=%s WHERE tenant=%s",
                (json.dumps(body), intent.tenant_id),
            )
        report = FixtureAccountReconciler(execution, sdk).run(request.execution_request_id)
        assert "BALANCE_MISMATCH" not in report.findings
        assert "QUOTE_MISMATCH" in report.findings
        assert "ATTRIBUTION_MISMATCH" in report.findings


def test_unavailable_account_read_latches_risk_and_preserves_reservation(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
    report = FixtureAccountReconciler(execution, transport(endpoint)).run(
        request.execution_request_id
    )
    assert report.status == "UNAVAILABLE"
    assert "SOURCE_UNAVAILABLE" in report.findings
    from crazytrader_ledger.store import LedgerStore

    assert (
        LedgerStore(risk.store).balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )


def test_official_sdk_history_pagination_advances_past_full_page(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        with risk.store.connection() as conn:
            template = json.loads(
                conn.execute(
                    "SELECT body FROM ct_test_wire_orders WHERE tenant=%s", (intent.tenant_id,)
                ).fetchone()["body"]
            )
            for order_id in range(102, 1102):
                body = template | {
                    "orderId": order_id,
                    "clientOrderId": f"external-{order_id}",
                    "status": "CANCELED",
                }
                conn.execute(
                    "INSERT INTO ct_test_wire_orders(tenant,client_id,body) VALUES(%s,%s,%s)",
                    (intent.tenant_id, body["clientOrderId"], json.dumps(body)),
                )
        source = transport(endpoint).account(request, (request.symbol,))
        assert source.available
        pages = source.raw()["history"][request.symbol]["orders"]
        assert [len(page) for page in pages] == [1000, 1]
        assert pages[1][0]["orderId"] == 1101


def test_missing_order_reservation_is_detected_even_when_total_balances_match(backbone):
    from crazytrader_ledger.commands import move
    from crazytrader_ledger.store import LedgerStore

    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        LedgerStore(risk.store).append(
            move(
                intent.tenant_id + ":fault-release",
                intent.tenant_id,
                intent.tenant_id + ":fault-source",
                "owner",
                "fixture-fault",
                now,
                intent.portfolio_id,
                "BTC",
                "0.01",
                "RELEASE",
                request.order_id,
            )
        )
        report = FixtureAccountReconciler(execution, transport(endpoint)).run(
            request.execution_request_id
        )
        assert "BALANCE_MISMATCH" not in report.findings
        assert "RESERVATION_MISMATCH" in report.findings


def test_internal_change_during_sdk_read_is_not_a_matched_snapshot(backbone, monkeypatch):
    from crazytrader_ledger.commands import move
    from crazytrader_ledger.store import LedgerStore

    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        sdk = transport(endpoint)
        original = sdk.account

        def concurrent(*args):
            source = original(*args)
            LedgerStore(risk.store).append(
                move(
                    intent.tenant_id + ":concurrent",
                    intent.tenant_id,
                    intent.tenant_id + ":concurrent-source",
                    "owner",
                    "fixture-fault",
                    now,
                    intent.portfolio_id,
                    "USDT",
                    "1",
                    "FUNDING",
                )
            )
            return source

        monkeypatch.setattr(sdk, "account", concurrent)
        report = FixtureAccountReconciler(execution, sdk).run(request.execution_request_id)
        assert "CONCURRENT_STATE" in report.findings


def test_partial_sdk_account_truth_is_retained_when_later_history_read_fails(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(
        risk.store, intent.tenant_id, timeout_after_accept=False, account_history_unavailable=True
    ) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
        report = FixtureAccountReconciler(execution, transport(endpoint)).run(
            request.execution_request_id
        )
        assert report.status == "UNAVAILABLE"
        with risk.store.connection() as conn:
            row = conn.execute(
                "SELECT body FROM ct_account_read_sources WHERE digest=%s", (report.source_sha256,)
            ).fetchone()
        from crazytrader_contracts.account import VenueAccountRead

        source = VenueAccountRead.model_validate_json(row["body"])
        assert not source.available
        assert source.raw()["before"]["balances"]
        assert source.raw()["open"][0]["orderId"] == 101


def test_identical_fault_keeps_every_receipt_but_emits_one_critical_notification(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, order_reconciler = ready(backbone, endpoint)
    reconciler = FixtureAccountReconciler(execution, transport(endpoint))
    first = reconciler.run(request.execution_request_id)
    second = reconciler.run(request.execution_request_id)
    assert first.findings == second.findings == ("SOURCE_UNAVAILABLE",)
    events = [e for e in risk.store.pending(limit=1000) if e.tenant_id == intent.tenant_id]
    critical = [e for e in events if e.event_type == "AccountReconciliationMismatch.v1"]
    checked = [e for e in events if e.event_type == "AccountReconciliationChecked.v1"]
    assert len(critical) == 1
    assert len(checked) == 2
    for event in critical + checked:
        assert risk.store.consume_audit(event)
    assert [e.event_id for e in critical] == [
        n for n in risk.store.notifications() if n in {e.event_id for e in events}
    ]
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_account_read_sources WHERE tenant_id=%s",
                (intent.tenant_id,),
            ).fetchone()["n"]
            == 2
        )
