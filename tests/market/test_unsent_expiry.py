"""Actual financial expiry/replay/race checks without venue dispatch."""

import os
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from crazytrader_contracts.events import EventEnvelope
from crazytrader_contracts.ledger import LedgerTransaction
from crazytrader_contracts.models import OrderState
from crazytrader_execution.expiry import UnsentExpiryService
from crazytrader_ledger.commands import release_custody
from crazytrader_ledger.store import LedgerStore
from crazytrader_risk.store import StateUnavailable

from .test_execution_boundary import prepared_request
from .test_native_registry import runner

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual services required")


def prepared(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    before = LedgerStore(risk.store).snapshot(request.tenant_id, request.portfolio_id, now)
    execution.prepare(request, objects, now)
    return execution, request, UnsentExpiryService(execution), before


@pytest.mark.parametrize("backbone", [None, "mixed-custody"], indirect=True)
def test_expired_unsent_request_restores_exact_original_custody_under_duplicate_delivery(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request, expiry, before = prepared(backbone)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(
            workers.map(
                lambda _: expiry.expire(
                    request.execution_request_id, request.actor_id, request.expires_at
                ),
                range(2),
            )
        )
    assert results[0] == results[1]
    assert execution.load(request.execution_request_id).state == OrderState.EXPIRED
    assert execution.claim_submission(request.execution_request_id, now) is None
    after = LedgerStore(risk.store).snapshot(request.tenant_id, request.portfolio_id, now)
    assert after == before
    with risk.store.connection() as conn:
        rows = conn.execute(
            "SELECT envelope FROM ct_events WHERE tenant_id=%s "
            "AND event_type='UnsentExecutionExpired.v1'",
            (request.tenant_id,),
        ).fetchall()
    events = [EventEnvelope.model_validate_json(str(row["envelope"])) for row in rows]
    assert len(events) == 1
    assert risk.store.consume_audit(events[0])
    assert not risk.store.consume_audit(events[0])


def test_unexpired_or_unauthorized_cannot_release_and_unknown_always_retains_funds(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request, expiry, before = prepared(backbone)
    with pytest.raises(StateUnavailable, match="authority denied"):
        expiry.expire(request.execution_request_id, "untrusted-actor", request.expires_at)
    assert expiry.expire(request.execution_request_id, request.actor_id, now) is None
    assert execution.claim_submission(request.execution_request_id, now)
    assert expiry.expire(request.execution_request_id, request.actor_id, request.expires_at) is None
    execution.recover_interrupted_submission(request.execution_request_id, request.expires_at)
    assert expiry.expire(request.execution_request_id, request.actor_id, request.expires_at) is None
    assert (
        LedgerStore(risk.store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )


def test_native_admission_without_dispatch_can_expire_without_engine_execution(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, costs, request = runner(backbone, tmp_path)
    service.registry.admit(request.execution_request_id, costs, now)
    expired = UnsentExpiryService(service.execution).expire(
        request.execution_request_id,
        request.actor_id,
        request.expires_at,
    )
    assert expired is not None
    assert service.submit_once(request.execution_request_id, costs) is None
    assert not list(tmp_path.iterdir())


def test_claim_expiry_race_cannot_dispatch_after_custody_release(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request, expiry, before = prepared(backbone)
    with ThreadPoolExecutor(max_workers=2) as workers:
        claimed = workers.submit(execution.claim_submission, request.execution_request_id, now)
        expired = workers.submit(
            expiry.expire, request.execution_request_id, request.actor_id, request.expires_at
        )
        claim_result, expiry_result = claimed.result(), expired.result()
    assert (claim_result is None) != (expiry_result is None)
    state = execution.load(request.execution_request_id).state
    balance = LedgerStore(risk.store).balance(
        request.tenant_id, request.portfolio_id, "RESERVED", "BTC"
    )
    assert (state, balance) in {(OrderState.SUBMITTING, request.quantity), (OrderState.EXPIRED, 0)}


def test_expiry_audit_failure_rolls_back_release_and_state_then_replays_once(backbone, monkeypatch):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request, expiry, before = prepared(backbone)
    original = risk.store.append_in_transaction

    def interrupted(conn, event, payload):
        if event.event_type == "UnsentExecutionExpired.v1":
            raise RuntimeError("fixture expiry audit interruption")
        return original(conn, event, payload)

    monkeypatch.setattr(risk.store, "append_in_transaction", interrupted)
    with pytest.raises(RuntimeError, match="audit interruption"):
        expiry.expire(request.execution_request_id, request.actor_id, request.expires_at)
    assert execution.load(request.execution_request_id).state == OrderState.AUTHORIZED
    assert (
        LedgerStore(risk.store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )
    monkeypatch.setattr(risk.store, "append_in_transaction", original)
    assert expiry.expire(request.execution_request_id, request.actor_id, request.expires_at)
    assert LedgerStore(risk.store).snapshot(request.tenant_id, request.portfolio_id, now) == before


def test_standalone_expiry_release_cannot_commit_without_expired_unsent_proof(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request, expiry, before = prepared(backbone)
    with risk.store.connection() as conn:
        row = conn.execute(
            "SELECT t.body FROM ct_execution_reservations r JOIN ct_ledger_transactions t "
            "ON t.transaction_id=r.reservation_tx_id WHERE r.execution_request_id=%s",
            (request.execution_request_id,),
        ).fetchone()
    original = LedgerTransaction.model_validate_json(row["body"])
    release = release_custody(
        original,
        request.quantity,
        "standalone-expiry",
        "standalone-source",
        request.actor_id,
        "unsent-expiry:" + request.execution_request_id,
        request.expires_at,
    )
    with pytest.raises(psycopg.Error, match="original undispatched"):
        LedgerStore(risk.store).append(release)
    assert execution.load(request.execution_request_id).state == OrderState.AUTHORIZED
