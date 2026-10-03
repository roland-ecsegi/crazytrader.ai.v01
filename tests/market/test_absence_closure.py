"""Actual elapsed signed window, source-first financial proof and failure containment."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import psycopg
import pytest
from crazytrader_contracts.models import OrderState
from crazytrader_execution.absence_closure import FixtureAbsenceCloser
from crazytrader_ledger.store import LedgerStore

from tests.execution.fixture_server import sdk_venue

from .test_absence_assessment import ambiguous
from .test_execution_boundary import prepared_request
from .test_sdk_timeout import transport

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual services required")


def guarded_ambiguous(backbone, adapter):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    bound = adapter.dispatch_bound(request)
    execution.bind_fixture_dispatch(bound)
    assert execution.claim_submission(request.execution_request_id, now, dispatch_bound=bound)
    execution.recover_interrupted_submission(request.execution_request_id, now)
    return execution, request


def elapsed(request):
    remaining = max(0, (request.expires_at - datetime.now(UTC)).total_seconds())
    assert remaining <= 5
    time.sleep(remaining + 7)  # signature window + HTTP Date floor, actual wall clock


def reserved(store, request):
    return LedgerStore(store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")


@pytest.mark.parametrize("backbone", [None, "mixed-custody"], indirect=True)
def test_elapsed_original_absence_releases_once_and_delayed_sender_cannot_send(backbone, request):
    mixed = request.node.callspec.params["backbone"] == "mixed-custody"
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        adapter = transport(endpoint)
        execution, request = guarded_ambiguous(backbone, adapter)
        if mixed:
            # Independent venue fixture truth: the fixture transferred0.9 BTC externally.
            body = adapter.account(request, (request.symbol,)).raw()["before"]
            body["balances"] = [
                {"asset": "BTC", "free": "0.1", "locked": "0"},
                {"asset": "USDT", "free": "0", "locked": "0"},
            ]
            with risk.store.connection() as conn:
                conn.execute(
                    "INSERT INTO ct_test_wire_accounts(tenant,body) VALUES(%s,%s)",
                    (request.tenant_id, json.dumps(body)),
                )
        elapsed(request)
        service = FixtureAbsenceCloser(execution, adapter)
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(
                    lambda _: service.close(request.execution_request_id, request.actor_id),
                    range(2),
                )
            )
        closure = next(value for value in results if value is not None)
        assert all(value is None or value == closure for value in results)
        from crazytrader_contracts.absence_closure import FixtureAbsenceClosure

        for corrupted in (
            {"actor_id": "other-owner"},
            {
                "timed_lookup": closure.timed_lookup.model_dump()
                | {"server_date": None, "raw_server_date": None}
            },
            {"release": closure.release.model_dump() | {"provenance_ref": "unbound-release"}},
        ):
            with pytest.raises(ValueError):
                FixtureAbsenceClosure.model_validate(closure.model_dump() | corrupted)
        assert execution.load(request.execution_request_id).state == OrderState.EXPIRED
        assert reserved(risk.store, request) == 0
        assert service.close(request.execution_request_id, request.actor_id) == closure
        assert adapter.submit(request, datetime.now(UTC)).status == "UNKNOWN"
    assert (
        LedgerStore(risk.store).snapshot(intent.tenant_id, intent.portfolio_id, now)
        == context.portfolio
    )
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_test_wire_posts WHERE tenant=%s", (intent.tenant_id,)
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_fixture_absence_closures WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 1
        )


def test_fresh_negative_before_elapsed_window_cannot_release(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        execution, request = guarded_ambiguous(backbone, transport(endpoint))
        assert (
            FixtureAbsenceCloser(execution, transport(endpoint)).close(
                request.execution_request_id, request.actor_id
            )
            is None
        )
    assert reserved(risk.store, request) == request.quantity


def test_legacy_unbound_unknown_cannot_backfill_release(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        assert (
            FixtureAbsenceCloser(execution, transport(endpoint)).close(
                request.execution_request_id, request.actor_id
            )
            is None
        )
    assert reserved(risk.store, request) == request.quantity


def test_financial_audit_failure_keeps_sources_and_whole_reservation(backbone, monkeypatch):
    risk, objects, intent, context, config, policy, now = backbone
    original = risk.store.append_in_transaction

    def interrupted(conn, event, payload):
        if event.event_type == "FixtureAbsenceClosed.v1":
            raise RuntimeError("absence closure audit fault")
        return original(conn, event, payload)

    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        execution, request = guarded_ambiguous(backbone, transport(endpoint))
        elapsed(request)
        monkeypatch.setattr(risk.store, "append_in_transaction", interrupted)
        with pytest.raises(RuntimeError, match="audit fault"):
            FixtureAbsenceCloser(execution, transport(endpoint)).close(
                request.execution_request_id, request.actor_id
            )
    assert execution.load(request.execution_request_id).state == OrderState.UNKNOWN
    assert reserved(risk.store, request) == request.quantity
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_fixture_timed_lookups WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_fixture_absence_closures WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 0
        )


def test_standalone_absence_release_requires_database_financial_proof(backbone):
    from crazytrader_contracts.ledger import LedgerTransaction
    from crazytrader_ledger.commands import release_custody

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    with risk.store.connection() as conn:
        row = conn.execute(
            "SELECT t.body FROM ct_execution_reservations r "
            "JOIN ct_ledger_transactions t ON t.transaction_id=r.reservation_tx_id "
            "WHERE r.execution_request_id=%s",
            (request.execution_request_id,),
        ).fetchone()
    original = LedgerTransaction.model_validate_json(row["body"])
    release = release_custody(
        original,
        request.quantity,
        "fake-absence:" + request.execution_request_id,
        "fake-source:" + request.execution_request_id,
        request.actor_id,
        "fixture-absent:" + request.execution_request_id,
        now,
    )
    with pytest.raises(psycopg.Error, match="absence closure requires"):
        LedgerStore(risk.store).append(release)
    assert reserved(risk.store, request) == request.quantity


@pytest.mark.parametrize("fault", ["missing-clock", "partial-account"])
def test_elapsed_absence_missing_clock_or_incomplete_history_keeps_custody(
    backbone, monkeypatch, fault
):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(
        risk.store,
        intent.tenant_id,
        authoritative_not_found=True,
        account_history_unavailable=fault == "partial-account",
    ) as endpoint:
        adapter = transport(endpoint)
        execution, request = guarded_ambiguous(backbone, adapter)
        elapsed(request)
        if fault == "missing-clock":
            original = adapter.timed_lookup

            def no_clock(req):
                result = original(req)
                return type(result).model_validate(
                    result.model_dump()
                    | {
                        "server_date": None,
                        "raw_server_date": None,
                    }
                )

            monkeypatch.setattr(adapter, "timed_lookup", no_clock)
        assert (
            FixtureAbsenceCloser(execution, adapter).close(
                request.execution_request_id, request.actor_id
            )
            is None
        )
    assert reserved(risk.store, request) == request.quantity
    assert execution.load(request.execution_request_id).state == OrderState.UNKNOWN


def test_owner_scope_denied_before_any_source_capture(backbone):
    from crazytrader_risk.store import StateUnavailable

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        with pytest.raises(StateUnavailable, match="owner denied"):
            FixtureAbsenceCloser(execution, transport(endpoint)).close(
                request.execution_request_id, "other-owner"
            )
    assert reserved(risk.store, request) == request.quantity


def test_database_snapshot_guard_rolls_back_concurrent_financial_mutation(backbone, monkeypatch):
    from crazytrader_ledger.commands import move

    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        execution, request = guarded_ambiguous(backbone, transport(endpoint))
        elapsed(request)
        original = LedgerStore.append_in_transaction

        def intervening(self, conn, transaction):
            if transaction.provenance_ref == "fixture-absent:" + request.execution_request_id:
                original(
                    self,
                    conn,
                    move(
                        "concurrent-funding:" + request.execution_request_id,
                        request.tenant_id,
                        "concurrent-source:" + request.execution_request_id,
                        request.actor_id,
                        "fixture-concurrent-funding",
                        datetime.now(UTC),
                        request.portfolio_id,
                        "BTC",
                        "0.01",
                        "FUNDING",
                    ),
                )
            return original(self, conn, transaction)

        monkeypatch.setattr(LedgerStore, "append_in_transaction", intervening)
        with pytest.raises(psycopg.Error, match="internal snapshot"):
            FixtureAbsenceCloser(execution, transport(endpoint)).close(
                request.execution_request_id, request.actor_id
            )
    assert reserved(risk.store, request) == request.quantity
    assert execution.load(request.execution_request_id).state == OrderState.UNKNOWN
