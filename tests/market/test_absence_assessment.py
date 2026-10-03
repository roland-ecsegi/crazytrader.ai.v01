"""Actual signed lookup + full bounded account proof, never granting retry/release."""

import os

import pytest
from crazytrader_execution.absence import FixtureAbsenceAssessor
from crazytrader_execution.runner import FixtureExecutionRunner
from crazytrader_ledger.store import LedgerStore
from crazytrader_risk.store import StateUnavailable

from tests.execution.fixture_server import sdk_venue

from .test_execution_boundary import prepared_request
from .test_sdk_timeout import transport

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual services required")


def ambiguous(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    execution.claim_submission(request.execution_request_id, now)
    execution.recover_interrupted_submission(request.execution_request_id, now)
    return execution, request


def test_complete_stable_signed_fixture_absence_is_proven_without_release_or_health_grant(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        assessment = FixtureAbsenceAssessor(execution, transport(endpoint)).assess(
            request.execution_request_id,
            request.actor_id,
        )
    assert assessment.verdict == "PROVEN", assessment.findings
    assert assessment.financial_effect == "NONE"
    assert (
        LedgerStore(risk.store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )
    with pytest.raises(StateUnavailable, match="healthy accounting"):
        risk.publish_context(context, objects, now)
    assert execution.claim_submission(request.execution_request_id, now) is None
    event = next(
        e
        for e in risk.store.pending(limit=1000)
        if e.tenant_id == request.tenant_id and e.event_type == "FixtureAbsenceAssessed.v1"
    )
    assert risk.store.consume_audit(event)
    assert not risk.store.consume_audit(event)


@pytest.mark.parametrize(
    "authoritative,history_unavailable,reason",
    [
        (False, False, "LOOKUP_UNPROVEN"),
        (True, True, "ACCOUNT_UNAVAILABLE"),
    ],
)
def test_not_found_or_partial_account_source_alone_cannot_prove_absence(
    backbone,
    authoritative,
    history_unavailable,
    reason,
):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    with sdk_venue(
        risk.store,
        intent.tenant_id,
        authoritative_not_found=authoritative,
        account_history_unavailable=history_unavailable,
    ) as endpoint:
        assessment = FixtureAbsenceAssessor(execution, transport(endpoint)).assess(
            request.execution_request_id,
            request.actor_id,
        )
    assert assessment.verdict == "DENIED"
    assert reason in assessment.findings
    assert (
        LedgerStore(risk.store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )


def test_accepted_timeout_order_in_history_cannot_be_proven_absent(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        FixtureExecutionRunner(execution, transport(endpoint), lambda: now).submit_once(
            request.execution_request_id
        )
        assessment = FixtureAbsenceAssessor(execution, transport(endpoint)).assess(
            request.execution_request_id,
            request.actor_id,
        )
    assert assessment.verdict == "DENIED"
    assert "LOOKUP_UNPROVEN" in assessment.findings
    assert "UNOWNED_ORDER" in assessment.findings


def test_assessment_audit_failure_preserves_raw_sources_without_assessment_or_financial_effect(
    backbone,
    monkeypatch,
):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    original = risk.store.append_in_transaction

    def interrupted(conn, event, payload):
        if event.event_type == "FixtureAbsenceAssessed.v1":
            raise RuntimeError("fixture absence audit interruption")
        return original(conn, event, payload)

    monkeypatch.setattr(risk.store, "append_in_transaction", interrupted)
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        with pytest.raises(RuntimeError, match="audit interruption"):
            FixtureAbsenceAssessor(execution, transport(endpoint)).assess(
                request.execution_request_id,
                request.actor_id,
            )
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_fixture_order_lookups WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_fixture_absence_assessments "
                "WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()["n"]
            == 0
        )
    assert (
        LedgerStore(risk.store).balance(request.tenant_id, request.portfolio_id, "RESERVED", "BTC")
        == request.quantity
    )


def test_concurrent_custody_change_during_source_read_prevents_absence(backbone, monkeypatch):
    from crazytrader_ledger.commands import move

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        adapter = transport(endpoint)
        original = adapter.account

        def changed(*args):
            source = original(*args)
            LedgerStore(risk.store).append(
                move(
                    "absence-concurrent:" + request.execution_request_id,
                    request.tenant_id,
                    "absence-concurrent-source:" + request.execution_request_id,
                    request.actor_id,
                    "fixture-concurrent-deposit",
                    now,
                    request.portfolio_id,
                    "BTC",
                    "0.01",
                    "FUNDING",
                )
            )
            return source

        monkeypatch.setattr(adapter, "account", changed)
        assessment = FixtureAbsenceAssessor(execution, adapter).assess(
            request.execution_request_id, request.actor_id
        )
    assert assessment.verdict == "DENIED"
    assert "CONCURRENT_STATE" in assessment.findings
    assert "BALANCE_MISMATCH" in assessment.findings


def test_database_rejects_correctly_hashed_unbound_absence_assessment(backbone):
    import psycopg
    from crazytrader_contracts.codec import canonical, digest

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = ambiguous(backbone)
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        assessment = FixtureAbsenceAssessor(execution, transport(endpoint)).assess(
            request.execution_request_id, request.actor_id
        )
    with risk.store.connection() as conn:
        with pytest.raises(psycopg.Error, match="original source mismatch"):
            conn.execute(
                "INSERT INTO ct_fixture_absence_assessments(digest,execution_request_id,"
                "lookup_digest,account_digest,body,verdict) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    digest("{}"),
                    request.execution_request_id,
                    digest(canonical(assessment.lookup)),
                    digest(canonical(assessment.account)),
                    "{}",
                    "PROVEN",
                ),
            )
