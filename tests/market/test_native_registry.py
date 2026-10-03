"""Actual SQL/source-native request fencing and recovery; financial adapter pending."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.simulation import SimulationCostProfile
from crazytrader_execution.native_registry import NativeSimulationRegistry, NativeSimulationRunner
from crazytrader_execution.native_transport import NativeSimulationTransport
from crazytrader_execution.reconciliation import FixtureReconciler
from crazytrader_ledger.store import LedgerStore
from crazytrader_risk.store import StateUnavailable

from tests.execution.fixture_server import sdk_venue

from .test_execution_boundary import prepared_request
from .test_fill_settlement import ready
from .test_sdk_timeout import transport as sdk_transport

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not os.getenv("CT_TEST_S3") or not os.getenv("CT_TEST_OPA_URL"),
    reason="actual services required",
)


def runner(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    registry = NativeSimulationRegistry(execution)
    native = NativeSimulationTransport(
        ROOT / "infra/spikes/python/.venv/bin/python",
        ROOT / "services/execution/nautilus_simulation_worker.py",
        ROOT / "packages/contracts/src",
        tmp_path,
    )
    costs = SimulationCostProfile(
        profile_id="owned-native-model",
        taker_fee_bps="10",
        maximum_slippage_bps="0",
        fee_asset="USDT",
    )
    return NativeSimulationRunner(registry, native, lambda: now), costs, request


def test_native_account_single_claim_duplicate_delivery_and_owned_result_audit(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, costs, request = runner(backbone, tmp_path)
    service.registry.admit(request.execution_request_id, costs, now)
    assert service.execution.claim_submission(request.execution_request_id, now) is None
    with ThreadPoolExecutor(max_workers=2) as workers:
        result = list(
            workers.map(
                lambda _: service.submit_once(request.execution_request_id, costs), range(2)
            )
        )
    assert sum(item is not None for item in result) == 1
    recorded = next(item for item in result if item is not None)
    assert recorded.receipt.available, recorded.receipt.raw_json
    assert service.execution.load(request.execution_request_id).state == OrderState.UNKNOWN
    assert (
        LedgerStore(risk.store).balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )
    recovered = service.recover_source(request.execution_request_id)
    assert recovered == recorded
    with pytest.raises(StateUnavailable, match="healthy accounting"):
        risk.publish_context(context, objects, now)
    for event in risk.store.pending(limit=1000):
        if event.tenant_id == intent.tenant_id and event.event_type.startswith("NativeSimulation"):
            assert risk.store.consume_audit(event)
            assert not risk.store.consume_audit(event)
    assert len(list(tmp_path.glob("*.claimed"))) == 1


def test_parent_receipt_write_interruption_recovers_fsynced_native_result_without_rerun(
    backbone, tmp_path, monkeypatch
):
    service, costs, request = runner(backbone, tmp_path)
    original = service.registry.record

    def interrupted(*args):
        raise StateUnavailable("receipt persistence interrupted")

    monkeypatch.setattr(service.registry, "record", interrupted)
    with pytest.raises(StateUnavailable, match="interrupted"):
        service.submit_once(request.execution_request_id, costs, interrupt_after_result=True)
    assert service.execution.load(request.execution_request_id).state == OrderState.SUBMITTING
    monkeypatch.setattr(service.registry, "record", original)
    recovered = service.recover_source(request.execution_request_id)
    assert recovered.receipt.available
    assert service.execution.load(request.execution_request_id).state == OrderState.UNKNOWN
    assert service.submit_once(request.execution_request_id, costs) is None
    assert len(list(tmp_path.glob("*.claimed"))) == 1


def test_started_sdk_account_cannot_be_adopted_as_native_simulation(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution, request, reconciler = ready(backbone, endpoint)
        costs = SimulationCostProfile(
            profile_id="owned-native-model",
            taker_fee_bps="10",
            maximum_slippage_bps="0",
            fee_asset="USDT",
        )
        with pytest.raises(StateUnavailable, match="unsent authorized"):
            NativeSimulationRegistry(execution).admit(request.execution_request_id, costs, now)


def test_sdk_recovery_never_queries_native_owned_account(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, costs, request = runner(backbone, tmp_path)
    service.registry.admit(request.execution_request_id, costs, now)
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        reconciler = FixtureReconciler(service.execution, sdk_transport(endpoint), lambda: now)
        with pytest.raises(StateUnavailable, match="native simulated account"):
            reconciler.recover(request.execution_request_id)
    assert service.execution.load(request.execution_request_id).state == OrderState.AUTHORIZED
    assert not list(tmp_path.glob("*.claimed"))


def test_native_database_guard_rejects_missing_original_request_body(backbone):
    import psycopg
    from crazytrader_contracts.codec import digest

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    with risk.store.connection() as conn:
        with pytest.raises(psycopg.Error, match="original authorized"):
            conn.execute(
                "INSERT INTO ct_native_simulation_jobs(execution_request_id,tenant_id,"
                "venue_account_ref,digest,job_digest,body) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    request.execution_request_id,
                    request.tenant_id,
                    request.venue_account_ref,
                    digest("{}"),
                    "a" * 64,
                    "{}",
                ),
            )
