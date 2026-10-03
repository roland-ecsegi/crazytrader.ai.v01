"""Actual SDK prepared-request deadline fence and captured loopback server clock."""

import os
import time
from datetime import UTC, datetime

import pytest
from crazytrader_contracts.models import OrderState

from tests.execution.fixture_server import sdk_venue

from .test_execution_boundary import prepared_request
from .test_sdk_timeout import transport

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual services required")


def test_paused_original_sender_cannot_dispatch_after_request_deadline(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    assert execution.claim_submission(request.execution_request_id, now)
    remaining = max(0, (request.expires_at - datetime.now(UTC)).total_seconds())
    assert remaining <= 5  # actual bounded fixture authorization; no rewritten request
    time.sleep(remaining + 0.02)
    assert datetime.now(UTC) >= request.expires_at
    with sdk_venue(
        risk.store, intent.tenant_id, timeout_after_accept=False, authoritative_not_found=True
    ) as endpoint:
        observed = transport(endpoint).submit(request, datetime.now(UTC))
        assert observed.status == "UNKNOWN"
        assert execution.record_submission(observed).state == OrderState.UNKNOWN
        timed = transport(endpoint).timed_lookup(request)
        assert timed.lookup.explicitly_not_found
        assert timed.server_date is not None
        assert timed.maximum_signature_window_ms == 5000
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_test_wire_posts WHERE tenant=%s", (request.tenant_id,)
            ).fetchone()["n"]
            == 0
        )


def test_current_signed_dispatch_and_lookup_use_exact_bounded_window_and_server_clock(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        observed = transport(endpoint).submit(request, now)
        assert observed.status == "NEW"
        timed = transport(endpoint).timed_lookup(request)
        assert timed.lookup.available
        assert timed.lookup.http_status == 200
        assert not timed.lookup.explicitly_not_found
        assert timed.server_date is not None
        assert timed.raw_server_date


def test_owned_dispatch_protocol_is_atomic_audited_and_duplicate_submit_cannot_repeat(backbone):
    from concurrent.futures import ThreadPoolExecutor

    from crazytrader_execution.runner import FixtureExecutionRunner

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        service = FixtureExecutionRunner(execution, transport(endpoint), lambda: now)
        with ThreadPoolExecutor(max_workers=2) as workers:
            list(workers.map(lambda _: service.submit_once(request.execution_request_id), range(2)))
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_fixture_dispatch_bounds WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_test_wire_posts WHERE tenant=%s", (request.tenant_id,)
            ).fetchone()["n"]
            == 1
        )
    assert execution.load(request.execution_request_id).state == OrderState.SUBMITTED


def test_guard_protocol_audit_failure_cannot_claim_or_send(backbone, monkeypatch):
    from crazytrader_execution.runner import FixtureExecutionRunner

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    original = risk.store.append_in_transaction

    def interrupted(conn, event, payload):
        if event.event_type == "FixtureDispatchBound.v1":
            raise RuntimeError("fixture protocol audit interruption")
        return original(conn, event, payload)

    monkeypatch.setattr(risk.store, "append_in_transaction", interrupted)
    with sdk_venue(risk.store, intent.tenant_id) as endpoint:
        with pytest.raises(RuntimeError, match="audit interruption"):
            FixtureExecutionRunner(execution, transport(endpoint), lambda: now).submit_once(
                request.execution_request_id
            )
    assert execution.load(request.execution_request_id).state == OrderState.AUTHORIZED
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_fixture_dispatch_bounds WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_test_wire_posts WHERE tenant=%s", (request.tenant_id,)
            ).fetchone()["n"]
            == 0
        )


def test_guarded_claim_cannot_bypass_binding_and_sdk_choice_cannot_switch_to_native(backbone):
    import psycopg
    from crazytrader_contracts.simulation import SimulationCostProfile
    from crazytrader_execution.native_registry import NativeSimulationRegistry
    from crazytrader_execution.state import transition
    from crazytrader_risk.store import StateUnavailable

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    with sdk_venue(risk.store, intent.tenant_id) as endpoint:
        bound = transport(endpoint).dispatch_bound(request)
        execution.bind_fixture_dispatch(bound)
        assert execution.claim_submission(request.execution_request_id, now) is None
        current = execution.load(request.execution_request_id)
        with pytest.raises(psycopg.Error, match="bound protocol evidence"):
            with risk.store.connection() as conn:
                forged = transition(
                    current,
                    OrderState.SUBMITTING,
                    now,
                    "SINGLE_DURABLE_SUBMISSION_CLAIM",
                    "legacy-reservation-proof",
                )
                execution._write(conn, forged)
        costs = SimulationCostProfile(
            profile_id="native", taker_fee_bps="10", maximum_slippage_bps="0", fee_asset="USDT"
        )
        with pytest.raises(StateUnavailable, match="SDK fixture backend"):
            NativeSimulationRegistry(execution).admit(request.execution_request_id, costs, now)
        assert execution.claim_submission(request.execution_request_id, now, dispatch_bound=bound)
