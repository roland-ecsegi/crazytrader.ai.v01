"""Actual full source-first rule receipts: tenant isolation/replay/conflict/tamper."""

import os
from datetime import timedelta

import pytest
from crazytrader_market.rules import TradingRuleArchive, capture_rules
from crazytrader_platform.storage import ConflictError

from tests.test_venue_rules import exchange_info

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual source stores required")


def test_full_rule_source_receipts_are_tenant_bound_and_read_back_verified(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    tenant = intent.tenant_id + ":raw-test"
    archive = TradingRuleArchive(risk.store, objects)
    rules = capture_rules(exchange_info(), "BTCUSDT", "SANDBOX", now)
    first = archive.persist(tenant, rules)
    assert archive.persist(tenant, rules) == first
    second = archive.persist(tenant + ":other", rules)
    assert second != first
    assert archive.latest(tenant, "SANDBOX", "BTCUSDT", now).rules == rules
    assert archive.latest(tenant + ":other", "SANDBOX", "BTCUSDT", now).rules == rules
    with pytest.raises(ValueError, match="stale"):
        archive.latest(tenant, "SANDBOX", "BTCUSDT", now + timedelta(seconds=6))
    changed = exchange_info()
    changed["symbols"][0]["filters"][0]["maxQty"] = "0.05"
    with pytest.raises(ConflictError, match="identity conflict"):
        archive.persist(tenant, capture_rules(changed, "BTCUSDT", "SANDBOX", now))
    objects.client.put_object(
        Bucket=objects.bucket,
        Key="market/rules/source/" + rules.source_sha256 + ".json",
        Body=b'{"tampered":true}',
    )
    with pytest.raises(ConflictError, match="raw source integrity"):
        archive.latest(tenant, "SANDBOX", "BTCUSDT", now)


def test_raw_source_tamper_after_reservation_cannot_claim_sdk_send(backbone):
    from decimal import Decimal

    from crazytrader_ledger.store import LedgerStore
    from crazytrader_risk.store import StateUnavailable

    from .test_execution_boundary import prepared_request

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    execution.prepare(request, objects, now)
    rules = (
        TradingRuleArchive(risk.store, objects)
        .latest(intent.tenant_id, "SANDBOX", "BTCUSDT", now)
        .rules
    )
    objects.client.put_object(
        Bucket=objects.bucket,
        Key="market/rules/source/" + rules.source_sha256 + ".json",
        Body=b'{"changed":true}',
    )
    with pytest.raises(StateUnavailable, match="full venue rules"):
        execution.claim_submission(request.execution_request_id, now)
    assert LedgerStore(risk.store).balance(
        intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC"
    ) == Decimal("0.1")


def test_changed_full_filters_before_prepare_cannot_reserve_old_approval(backbone):
    from decimal import Decimal

    from crazytrader_ledger.store import LedgerStore
    from crazytrader_risk.store import StateUnavailable

    from .test_execution_boundary import prepared_request

    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    archive = TradingRuleArchive(risk.store, objects)
    raw = archive.latest(intent.tenant_id, "SANDBOX", "BTCUSDT", now).rules.source()
    raw["symbols"][0]["filters"][1]["maxQty"] = "0.05"
    later = now + timedelta(milliseconds=1)
    archive.persist(intent.tenant_id, capture_rules(raw, "BTCUSDT", "SANDBOX", later))
    with pytest.raises(StateUnavailable, match="full venue rules"):
        execution.prepare(request, objects, later)
    assert LedgerStore(risk.store).balance(
        intent.tenant_id, intent.portfolio_id, "RESERVED", "BTC"
    ) == Decimal(0)
