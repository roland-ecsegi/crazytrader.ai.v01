"""Actual native engine + PostgreSQL atomic financial/source/recovery acceptance."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import psycopg
import pytest
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.native_fills import NativeSimulationFill, sourced_fill
from crazytrader_execution.native_settlement import NativeSimulationSettlement
from crazytrader_ledger.commands import account_native_fill
from crazytrader_ledger.store import InsufficientFunds, LedgerStore
from crazytrader_risk.store import StateUnavailable

from .test_native_registry import runner

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual services required")


def submitted(backbone, tmp_path):
    service, costs, request = runner(backbone, tmp_path)
    record = service.submit_once(request.execution_request_id, costs)
    assert record.receipt.available
    return service, request, record, NativeSimulationSettlement(service.registry)


def native_tx(record):
    fill, gross = sourced_fill(record.receipt)
    evidence = NativeSimulationFill(receipt=record.receipt, fill=fill, quote_quantity=gross)
    request = record.admission.request
    symbol = record.receipt.job.venue_rules.rules.symbol_record()
    return account_native_fill(
        "native-tx:" + digest(canonical(evidence)),
        request.tenant_id,
        "native-financial-source:" + digest(canonical(record)),
        request.actor_id,
        "native-result:" + digest(canonical(record)),
        fill.timestamp,
        request.portfolio_id,
        request.side,
        symbol["baseAsset"],
        symbol["quoteAsset"],
        evidence,
        "native-result:" + digest(canonical(record)),
    )


@pytest.mark.parametrize("backbone", [None, "mixed-custody"], indirect=True)
def test_native_full_fill_cash_fee_state_one_journal_under_concurrent_replay(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, request, record, settlement = submitted(backbone, tmp_path)
    ledger = LedgerStore(risk.store)
    initial_base = ledger.balance(request.tenant_id, request.portfolio_id, "AVAILABLE", "BTC")
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(
            workers.map(lambda _: settlement.apply(record, record.receipt.observed_at), range(2))
        )
    assert all(result.state == OrderState.FILLED for result in results)
    assert service.recover_source(request.execution_request_id) == record
    assert settlement.apply(record, record.receipt.observed_at).state == OrderState.FILLED
    assert ledger.balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC") == 0
    assert (
        ledger.balance(request.tenant_id, request.portfolio_id, "AVAILABLE", "BTC") == initial_base
    )
    fill, gross = sourced_fill(record.receipt)
    assert (
        ledger.balance(request.tenant_id, request.portfolio_id, "AVAILABLE", "USDT")
        == gross - fill.fee_amount
    )
    assert (
        ledger.balance(request.tenant_id, request.portfolio_id, "FEES", "USDT") == fill.fee_amount
    )
    assert sum(tx.transaction_type == "FILL" for tx in ledger.history(request.tenant_id)) == 1
    events = [
        e
        for e in risk.store.pending(limit=1000)
        if e.tenant_id == request.tenant_id and e.event_type == "LedgerNativeFillAppended.v1"
    ]
    assert len(events) == 1
    assert risk.store.consume_audit(events[0])
    assert not risk.store.consume_audit(events[0])
    assert len(list(tmp_path.glob("*.claimed"))) == 1


def test_native_financial_journal_cannot_commit_without_completion_proof(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, request, record, settlement = submitted(backbone, tmp_path)
    with pytest.raises(psycopg.Error, match="atomic financial proof"):
        LedgerStore(risk.store).append(native_tx(record))
    assert service.execution.load(request.execution_request_id).state == OrderState.UNKNOWN
    assert all(
        tx.transaction_type != "FILL" for tx in LedgerStore(risk.store).history(request.tenant_id)
    )
    assert settlement.apply(record, record.receipt.observed_at).state == OrderState.FILLED


def test_financial_attribution_failure_preserves_source_custody_one_incident_alert(
    backbone, tmp_path, monkeypatch
):
    risk, objects, intent, context, config, policy, now = backbone
    service, request, record, settlement = submitted(backbone, tmp_path)
    original = LedgerStore.append_in_transaction

    def unavailable(self, conn, transaction):
        if transaction.transaction_type == "FILL":
            raise InsufficientFunds("fixture financial attribution failure")
        return original(self, conn, transaction)

    monkeypatch.setattr(LedgerStore, "append_in_transaction", unavailable)
    assert settlement.apply(record, record.receipt.observed_at).state == OrderState.UNKNOWN
    assert settlement.apply(record, record.receipt.observed_at).state == OrderState.UNKNOWN
    assert (
        LedgerStore(risk.store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_native_simulation_receipts "
                "WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_native_simulation_incidents "
                "WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 1
        )
    alerts = [
        e
        for e in risk.store.pending(limit=1000)
        if e.tenant_id == request.tenant_id
        and e.event_type == "NativeSimulationCriticalMismatch.v1"
    ]
    assert len(alerts) == 1
    assert risk.store.consume_audit(alerts[0])
    assert alerts[0].event_id in risk.store.notifications()
    monkeypatch.setattr(LedgerStore, "append_in_transaction", original)
    assert settlement.apply(record, record.receipt.observed_at).state == OrderState.FILLED
    with pytest.raises(StateUnavailable, match="healthy accounting"):
        risk.publish_context(context, objects, now)


def test_financial_audit_interruption_rolls_back_money_then_recovers_same_native_result(
    backbone, tmp_path, monkeypatch
):
    risk, objects, intent, context, config, policy, now = backbone
    service, request, record, settlement = submitted(backbone, tmp_path)
    original = risk.store.append_in_transaction

    def interrupted(conn, event, payload):
        if event.event_type == "LedgerNativeFillAppended.v1":
            raise RuntimeError("fixture audit interruption")
        return original(conn, event, payload)

    monkeypatch.setattr(risk.store, "append_in_transaction", interrupted)
    with pytest.raises(RuntimeError, match="audit interruption"):
        settlement.apply(record, record.receipt.observed_at)
    assert service.execution.load(request.execution_request_id).state == OrderState.UNKNOWN
    ledger = LedgerStore(risk.store)
    assert (
        ledger.balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )
    assert ledger.balance(request.tenant_id, request.portfolio_id, "AVAILABLE", "USDT") == Decimal(
        0
    )
    monkeypatch.setattr(risk.store, "append_in_transaction", original)
    recovered = service.recover_source(request.execution_request_id)
    assert recovered == record
    assert settlement.apply(recovered, record.receipt.observed_at).state == OrderState.FILLED
    assert service.submit_once(request.execution_request_id, record.receipt.job.costs) is None
    assert len(list(tmp_path.glob("*.claimed"))) == 1


def test_missing_native_result_never_retries_or_releases_and_emits_one_incident(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, costs, request = runner(backbone, tmp_path)
    admission = service.registry.admit(request.execution_request_id, costs, now)
    assert service.execution.claim_submission(request.execution_request_id, now, native=True)
    key = digest(canonical(admission.job))
    (tmp_path / (key + ".claimed")).write_text(canonical(admission.job))
    receipt = service.transport.simulate(admission.job)
    assert not receipt.available
    record = service.registry.record(receipt)
    settlement = NativeSimulationSettlement(service.registry)
    assert settlement.apply(record, receipt.observed_at).state == OrderState.UNKNOWN
    assert settlement.apply(record, receipt.observed_at).state == OrderState.UNKNOWN
    later = receipt.model_copy(update={"observed_at": receipt.observed_at + timedelta(seconds=1)})
    restated = service.registry.record(later)
    assert settlement.apply(restated, later.observed_at).state == OrderState.UNKNOWN
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_native_simulation_incidents "
                "WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 1
        )
    assert service.recover_source(request.execution_request_id) is None
    assert not list(tmp_path.glob("*.json"))
    assert (
        LedgerStore(risk.store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )


def test_existing_reservation_cannot_be_forged_as_native_financial_completion(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, request, record, settlement = submitted(backbone, tmp_path)
    with pytest.raises(psycopg.Error, match="financial/source ownership mismatch"):
        with risk.store.connection() as conn:
            proof = conn.execute(
                "SELECT reservation_tx_id FROM ct_execution_reservations "
                "WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()
            conn.execute(
                "INSERT INTO ct_native_simulation_postings(execution_request_id,"
                "receipt_digest,ledger_tx_id) VALUES(%s,%s,%s)",
                (
                    request.execution_request_id,
                    digest(canonical(record)),
                    proof["reservation_tx_id"],
                ),
            )
    assert service.execution.load(request.execution_request_id).state == OrderState.UNKNOWN
    assert settlement.apply(record, record.receipt.observed_at).state == OrderState.FILLED


def test_native_database_receipt_rejects_hash_valid_but_unbound_body(backbone, tmp_path):
    risk, objects, intent, context, config, policy, now = backbone
    service, request, record, settlement = submitted(backbone, tmp_path)
    with risk.store.connection() as conn:
        with pytest.raises(psycopg.Error, match="original owned claimed source"):
            conn.execute(
                "INSERT INTO ct_native_simulation_receipts(digest,execution_request_id,"
                "job_digest,body,available,observed_at) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    digest("{}"),
                    request.execution_request_id,
                    record.receipt.job_sha256,
                    "{}",
                    True,
                    record.receipt.observed_at,
                ),
            )
