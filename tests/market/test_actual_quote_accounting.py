"""Actual PostgreSQL mixed V1/new quote journal, exact fees, replay and metadata binding."""

import os
from decimal import Decimal

import pytest
from crazytrader_contracts.codec import canonical, digest
from crazytrader_ledger.attribution import positions
from crazytrader_ledger.commands import account_actual_quote_fill, move
from crazytrader_ledger.store import LedgerStore
from crazytrader_market.rules import TradingRuleArchive
from crazytrader_platform.storage import ConflictError

from tests.test_actual_quote_ledger import evidence

pytestmark = pytest.mark.skipif(
    not os.getenv("CT_TEST_S3"), reason="actual financial stores required"
)


def quote_transaction(backbone, rule_ref=None):
    risk, objects, intent, context, config, policy, now = backbone
    receipt = TradingRuleArchive(risk.store, objects).latest(
        intent.tenant_id, "SANDBOX", "BTCUSDT", now
    )
    reference = rule_ref or digest(canonical(receipt))
    data = evidence(tenant=intent.tenant_id, rule_ref=reference)
    return account_actual_quote_fill(
        intent.tenant_id + ":actual-fill",
        intent.tenant_id,
        intent.tenant_id + ":actual-fill-source",
        "owner",
        "fixture-actual-quote",
        now,
        intent.portfolio_id,
        "BUY",
        "BTC",
        "USDT",
        data,
        "venue-actual-quote",
    )


def test_actual_quote_fee_reservation_posting_replay_and_history_reconstruction(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    ledger = LedgerStore(risk.store)
    tx = quote_transaction(backbone)
    for transaction_id, amount, kind, order in (
        (intent.tenant_id + ":quote-funding", "20", "FUNDING", None),
        (intent.tenant_id + ":quote-reserve", "13.4", "RESERVATION", "order"),
    ):
        ledger.append(
            move(
                transaction_id,
                intent.tenant_id,
                transaction_id + ":source",
                "owner",
                "fixture",
                now,
                intent.portfolio_id,
                "USDT",
                amount,
                kind,
                order,
            )
        )
    assert ledger.append(tx)
    assert not ledger.append(tx)
    assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "USDT") == Decimal(
        "0.05666667"
    )
    assert ledger.balance(intent.tenant_id, intent.portfolio_id, "FEES", "USDT") == Decimal("0.01")
    history = ledger.history(intent.tenant_id)
    view = positions(history, intent.tenant_id, intent.portfolio_id, now)[0]
    assert view.cost_basis == Decimal("13.34333333")
    assert view.quantity == Decimal("0.100000000000000001")
    events = [
        event
        for event in risk.store.pending(limit=1000)
        if event.tenant_id == intent.tenant_id and event.event_type == "LedgerVenueFillAppended.v1"
    ]
    assert len(events) == 1
    assert risk.store.consume_audit(events[0])
    assert not risk.store.consume_audit(events[0])


def test_quote_precision_receipt_cannot_be_borrowed_from_another_tenant(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    archive = TradingRuleArchive(risk.store, objects)
    receipt = archive.latest(intent.tenant_id, "SANDBOX", "BTCUSDT", now)
    other = archive.persist(intent.tenant_id + ":other", receipt.rules)
    with pytest.raises(ConflictError, match="precision/asset ownership"):
        LedgerStore(risk.store).append(quote_transaction(backbone, other))
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM ct_ledger_transactions WHERE transaction_id=%s",
                (intent.tenant_id + ":actual-fill",),
            ).fetchone()
            is None
        )


def test_modeled_buy_buffers_fund_actual_quote_fee_and_release_unused_cash_without_execution(
    backbone,
):
    from crazytrader_contracts.simulation import SimulationCostProfile
    from crazytrader_execution.funding import plan_simulation_buy_funding
    from crazytrader_ledger.commands import release_custody, reserve_custody

    risk, objects, intent, context, config, policy, now = backbone
    receipt = TradingRuleArchive(risk.store, objects).latest(
        intent.tenant_id, "SANDBOX", "BTCUSDT", now
    )
    costs = SimulationCostProfile(
        profile_id="fixture-sim-costs",
        taker_fee_bps="10",
        maximum_slippage_bps="25",
        fee_asset="USDT",
    )
    plan = plan_simulation_buy_funding(
        intent.tenant_id,
        intent.portfolio_id,
        "order",
        "USDT",
        "USDT",
        Decimal("0.100000000000000001"),
        Decimal("133.33333333"),
        Decimal("14"),
        costs,
        receipt,
    )
    ledger = LedgerStore(risk.store)
    ledger.append(
        move(
            intent.tenant_id + ":plan-fund",
            intent.tenant_id,
            intent.tenant_id + ":plan-fund-source",
            "owner",
            "fixture-simulation-only",
            now,
            intent.portfolio_id,
            "USDT",
            "20",
            "FUNDING",
        )
    )
    reserve = reserve_custody(
        intent.tenant_id + ":plan-reserve",
        intent.tenant_id,
        intent.tenant_id + ":plan-source",
        "owner",
        digest(canonical(plan)),
        now,
        intent.portfolio_id,
        "USDT",
        plan.quote_reservation,
        "order",
        Decimal(0),
        Decimal(20),
    )
    assert ledger.append(reserve)
    assert not ledger.append(reserve)
    assert ledger.append(quote_transaction(backbone))
    remaining = ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "USDT")
    assert remaining == Decimal("0.03670001")
    release = release_custody(
        reserve,
        remaining,
        intent.tenant_id + ":plan-release",
        intent.tenant_id + ":plan-release-source",
        "owner",
        "fixture-proven-complete",
        now,
    )
    assert ledger.append(release)
    assert not ledger.append(release)
    assert ledger.balance(intent.tenant_id, intent.portfolio_id, "RESERVED", "USDT") == 0
    assert ledger.balance(intent.tenant_id, intent.portfolio_id, "AVAILABLE", "USDT") == Decimal(
        "6.65666667"
    )
    assert plan.certification_effect == "NONE"
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_execution_requests WHERE tenant_id=%s",
                (intent.tenant_id,),
            ).fetchone()["n"]
            == 0
        )
