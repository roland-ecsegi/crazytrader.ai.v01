"""Real OPA+journal/source proof and atomic execution reservation/claim milestone."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.execution import ExecutionRequest, ExecutionTransition
from crazytrader_contracts.models import OrderState
from crazytrader_execution.state import client_order_id
from crazytrader_execution.store import ExecutionStore
from crazytrader_ledger.store import LedgerStore
from crazytrader_platform.storage import ConflictError, EventStore
from crazytrader_risk.policy import OPAClient
from crazytrader_risk.service import RiskService
from crazytrader_risk.store import StateUnavailable

pytestmark = pytest.mark.skipif(
    not os.getenv("CT_TEST_OPA_URL") or not os.getenv("CT_TEST_S3"),
    reason="actual OPA and stores required",
)


def prepared_request(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    risk.publish_context(context, objects, now)
    actual_policy = OPAClient(
        os.environ["CT_TEST_OPA_URL"], Path("infra/policy/authorization.rego")
    )
    record = RiskService(risk, objects, actual_policy, lambda: now).evaluate(intent, "owner")
    assert record.policy.decision.decision == "ALLOW"
    request_id = intent.tenant_id + ":execution"
    request = ExecutionRequest(
        execution_request_id=request_id,
        order_id=intent.tenant_id + ":order",
        tenant_id=intent.tenant_id,
        portfolio_id=intent.portfolio_id,
        actor_id="owner",
        intent_id=intent.intent_id,
        intent_sha256=digest(canonical(intent)),
        risk_record_sha256=digest(canonical(record)),
        owner_config_id=config.config_id,
        policy_bundle_sha256=actual_policy.policy_hash,
        client_order_id=client_order_id(request_id, intent.tenant_id, "fixture"),
        venue_account_ref="fixture",
        symbol=intent.symbol,
        side=intent.side,
        order_type="MARKET",
        quantity=record.authorization.quantity,
        limit_price=None,
        metadata_version=context.metadata.metadata_version,
        execution_mode="SIMULATION",
        environment="SANDBOX",
        created_at=now,
        expires_at=min(record.authorization.expires_at, record.policy.expires_at),
    )
    return ExecutionStore(risk.store), request


def test_atomic_reservation_duplicate_claim_and_restart_unknown(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    with ThreadPoolExecutor(max_workers=2) as workers:
        states = list(workers.map(lambda _: execution.prepare(request, objects, now), range(2)))
    assert all(state.state == OrderState.AUTHORIZED for state in states)
    ledger = LedgerStore(risk.store)
    assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC") == Decimal(
        "0.1"
    )
    assert ledger.balance(intent.tenant_id, intent.portfolio_id, "AVAILABLE", "BTC") == Decimal(
        "0.9"
    )
    with ThreadPoolExecutor(max_workers=2) as workers:
        claims = list(
            workers.map(
                lambda _: execution.claim_submission(request.execution_request_id, now), range(2)
            )
        )
    assert sum(claim is not None for claim in claims) == 1
    restarted = ExecutionStore(EventStore(os.environ["CT_TEST_DSN"]))
    unknown = restarted.recover_interrupted_submission(request.execution_request_id, now)
    assert unknown.state == OrderState.UNKNOWN
    assert restarted.claim_submission(request.execution_request_id, now) is None
    assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC") == Decimal(
        "0.1"
    )
    events = [
        e
        for e in risk.store.pending()
        if e.tenant_id == intent.tenant_id and e.source_service == "execution"
    ]
    assert len(events) == 5
    for event in events:
        assert risk.store.consume_audit(event)
        assert not risk.store.consume_audit(event)
    with risk.store.connection() as conn:
        with pytest.raises(psycopg.Error, match="append-only"):
            conn.execute(
                "DELETE FROM ct_execution_transitions WHERE execution_request_id=%s",
                (request.execution_request_id,),
            )


def test_changed_expired_or_denied_authority_cannot_prepare(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    with pytest.raises(StateUnavailable, match="expired"):
        execution.prepare(request, objects, request.expires_at)
    with pytest.raises(StateUnavailable, match="differs"):
        execution.prepare(request.model_copy(update={"quantity": Decimal("0.2")}), objects, now)
    with pytest.raises(StateUnavailable, match="venue account"):
        changed = request.model_copy(
            update={
                "venue_account_ref": "other",
                "client_order_id": client_order_id(
                    request.execution_request_id, intent.tenant_id, "other"
                ),
            }
        )
        execution.prepare(changed, objects, now)
    assert (
        LedgerStore(risk.store).balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC")
        == 0
    )
    execution.prepare(request, objects, now)
    with pytest.raises(ConflictError):
        execution.prepare(request.model_copy(update={"order_id": "changed"}), objects, now)


def test_reservation_and_audit_failure_roll_back_together(backbone, monkeypatch):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    original = risk.store.append_in_transaction

    def fail_after_reservation(conn, event, payload):
        if (
            isinstance(payload, ExecutionTransition)
            and payload.resulting_state.state == OrderState.AUTHORIZED
        ):
            raise RuntimeError("injected audit failure")
        return original(conn, event, payload)

    monkeypatch.setattr(risk.store, "append_in_transaction", fail_after_reservation)
    with pytest.raises(RuntimeError, match="injected"):
        execution.prepare(request, objects, now)
    assert (
        LedgerStore(risk.store).balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC")
        == 0
    )
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_execution_requests WHERE tenant_id=%s",
                (intent.tenant_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_execution_transitions t "
                "JOIN ct_execution_requests r USING(execution_request_id) WHERE r.tenant_id=%s",
                (intent.tenant_id,),
            ).fetchone()["n"]
            == 0
        )


def test_new_owner_configuration_and_expiry_invalidate_claim(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    with pytest.raises(ValueError, match="expired"):
        execution.claim_submission(request.execution_request_id, request.expires_at)
    risk.install_owner_configuration(
        config.model_copy(update={"config_id": config.config_id + ":2"})
    )
    with pytest.raises(StateUnavailable, match="configuration"):
        execution.claim_submission(request.execution_request_id, now + timedelta(microseconds=1))
    assert execution.load(request.execution_request_id).state == OrderState.AUTHORIZED
