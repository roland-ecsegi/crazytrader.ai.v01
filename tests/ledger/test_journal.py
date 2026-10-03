"""Real PostgreSQL accounting integrity, concurrency and reconstructability."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import psycopg
import pytest
from crazytrader_contracts.ledger import LedgerTransaction
from crazytrader_contracts.models import Fill, Mode, Portfolio
from crazytrader_ledger.commands import account_fill, compensate, move
from crazytrader_ledger.store import InsufficientFunds, LedgerStore
from crazytrader_platform.storage import ConflictError, EventStore, canonical

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_DSN"), reason="real PostgreSQL required")
NOW = datetime(2026, 10, 3, tzinfo=UTC)


@pytest.fixture
def ledger():
    store = EventStore(os.environ["CT_TEST_DSN"])
    for path in (
        Path("infra/migrations/001_platform.sql"),
        Path("infra/migrations/003_ledger.sql"),
    ):
        store.migrate(path)
    ledger = LedgerStore(store)
    tenant = "t_" + uuid.uuid4().hex
    portfolios = {}
    for mode in (Mode.RESERVE, Mode.MATH, Mode.STRATEGY):
        portfolio = Portfolio(
            portfolio_id=tenant + ":" + mode,
            tenant_id=tenant,
            name=mode,
            mode=mode,
            risk_profile_version_id="low.v1" if mode == Mode.STRATEGY else None,
            status="ACTIVE",
            base_currency="USDT",
            created_at=NOW,
        )
        assert ledger.register(portfolio)
        assert not ledger.register(portfolio)
        portfolios[mode] = portfolio.portfolio_id
    return ledger, tenant, portfolios


def command(
    tenant,
    portfolio,
    amount,
    operation,
    label,
    order=None,
    destination=None,
    reserve_account="AVAILABLE",
):
    return move(
        tenant + ":" + label,
        tenant,
        tenant + ":source:" + label,
        "owner",
        "fixture.v1",
        NOW,
        portfolio,
        "USDT",
        amount,
        operation,
        order,
        destination,
        reserve_account,
    )


def test_history_replay_transfer_reserve_release_and_compensation(ledger):
    ledger, tenant, p = ledger
    funding = command(tenant, p[Mode.RESERVE], "1000.123456789123456789", "FUNDING", "fund")
    assert ledger.append(funding)
    assert not ledger.append(funding)
    assert ledger.balance(tenant, p[Mode.RESERVE], "AVAILABLE", "USDT") == Decimal(
        "1000.123456789123456789"
    )
    allocation = command(
        tenant, p[Mode.RESERVE], "500", "ALLOCATION", "allocate", destination=p[Mode.MATH]
    )
    ledger.append(allocation)
    reservation = command(tenant, p[Mode.MATH], "100", "RESERVATION", "reserve", "order1")
    ledger.append(reservation)
    assert ledger.balance(tenant, p[Mode.MATH], "AVAILABLE", "USDT") == 400
    assert ledger.balance(tenant, p[Mode.STRATEGY], "AVAILABLE", "USDT") == 0
    ledger.append(command(tenant, p[Mode.MATH], "40", "RELEASE", "release", "order1"))
    assert ledger.balance(tenant, p[Mode.MATH], "RESERVED", "USDT") == 60
    with pytest.raises(InsufficientFunds):
        ledger.append(command(tenant, p[Mode.MATH], "61", "RELEASE", "over-release", "order1"))
    with pytest.raises(InsufficientFunds):
        ledger.append(command(tenant, p[Mode.MATH], "1", "RELEASE", "wrong-order", "order2"))
    correction = compensate(
        allocation,
        tenant + ":correction",
        tenant + ":correction-source",
        "owner",
        "FIXTURE_ERROR",
        "proof.v1",
        NOW,
    )
    with pytest.raises(InsufficientFunds):
        ledger.append(correction)  # cannot reverse already-reserved/spent allocation
    ledger.append(command(tenant, p[Mode.MATH], "60", "RELEASE", "release-rest", "order1"))
    ledger.append(correction)
    restored = LedgerStore(EventStore(os.environ["CT_TEST_DSN"]))
    assert restored.balance(tenant, p[Mode.RESERVE], "AVAILABLE", "USDT") == Decimal(
        "1000.123456789123456789"
    )
    with localcontext() as ctx:
        ctx.prec = 100
        history_balance = sum(
            (
                posting.amount
                for tx in restored.history(tenant)
                for posting in tx.postings
                if posting.portfolio_id == p[Mode.RESERVE] and posting.account == "AVAILABLE"
            ),
            Decimal(0),
        )
    assert history_balance == restored.balance(tenant, p[Mode.RESERVE], "AVAILABLE", "USDT")
    snapshot = restored.snapshot(tenant, p[Mode.RESERVE], NOW)
    assert snapshot.mode == "RESERVE"
    assert snapshot.balances[0].total_held == history_balance
    with pytest.raises(ValueError, match="ownership"):
        restored.snapshot("other-tenant", p[Mode.RESERVE], NOW)
    for event in ledger.store.pending(1000):
        if event.tenant_id == tenant:
            assert ledger.store.consume_audit(event)
            assert not ledger.store.consume_audit(event)


def test_concurrent_reservations_cannot_overspend(ledger):
    ledger, tenant, p = ledger
    ledger.append(command(tenant, p[Mode.MATH], "100", "FUNDING", "fund"))

    def reserve(i):
        try:
            return ledger.append(
                command(tenant, p[Mode.MATH], "80", "RESERVATION", f"reserve{i}", f"order{i}")
            )
        except InsufficientFunds:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reserve, (1, 2)))
    assert sorted(outcomes) == [False, True]
    assert ledger.balance(tenant, p[Mode.MATH], "AVAILABLE", "USDT") == 20
    assert ledger.balance(tenant, p[Mode.MATH], "RESERVED", "USDT") == 80


def test_content_source_tenant_and_fill_collisions(ledger):
    ledger, tenant, p = ledger
    tx = command(tenant, p[Mode.MATH], "100", "FUNDING", "fund")
    ledger.append(tx)
    changed = LedgerTransaction.model_validate(tx.model_dump() | {"reason": "CHANGED"})
    with pytest.raises(ConflictError):
        ledger.append(changed)
    changed_id = LedgerTransaction.model_validate(
        tx.model_dump() | {"transaction_id": tenant + ":changed"}
    )
    with pytest.raises(ConflictError):
        ledger.append(changed_id)
    with pytest.raises(psycopg.Error):
        ledger.append(command("other-tenant", p[Mode.MATH], "1", "FUNDING", "cross-tenant"))
    ledger.append(command(tenant, p[Mode.MATH], "50", "RESERVATION", "reserve", "buy1"))
    fill = Fill(
        fill_id="fill1",
        order_id="buy1",
        venue_fill_id="venue1",
        quantity="0.1",
        price="100",
        fee_amount="0.01",
        fee_asset="USDT",
        timestamp=NOW,
    )
    entry = account_fill(
        tenant + ":fill",
        tenant,
        tenant + ":fill-source",
        "execution",
        "venue-fixture.v1",
        NOW,
        p[Mode.MATH],
        "BUY",
        "BTC",
        "USDT",
        fill,
        "venue-fill-price.v1",
    )
    ledger.append(entry)
    assert not ledger.append(entry)
    assert ledger.balance(tenant, p[Mode.MATH], "INVENTORY", "BTC") == Decimal("0.1")
    assert ledger.balance(tenant, p[Mode.MATH], "RESERVED", "USDT") == 40
    assert ledger.balance(tenant, p[Mode.MATH], "FEES", "USDT") == Decimal("0.01")
    duplicate_fill = LedgerTransaction.model_validate(
        entry.model_dump()
        | {"transaction_id": tenant + ":duplicate-fill", "source_event_id": tenant + ":new-source"}
    )
    with pytest.raises(ConflictError):
        ledger.append(duplicate_fill)


def test_sql_append_only_unbalanced_and_missing_posting_denial(ledger):
    ledger, tenant, p = ledger
    ledger.append(command(tenant, p[Mode.MATH], "100", "FUNDING", "fund"))
    for table in ("ct_portfolios", "ct_ledger_transactions", "ct_ledger_postings"):
        for action in (
            f"DELETE FROM {table} WHERE tenant_id=%s",
            f"UPDATE {table} SET tenant_id=tenant_id WHERE tenant_id=%s",
        ):
            with pytest.raises(psycopg.Error), ledger.store.connection() as conn:
                conn.execute(action, (tenant,))
        with pytest.raises(psycopg.Error), ledger.store.connection() as conn:
            conn.execute(f"TRUNCATE {table} CASCADE")
    with pytest.raises(psycopg.Error, match="postings"), ledger.store.connection() as conn:
        conn.execute(
            "INSERT INTO ct_ledger_transactions "
            "(transaction_id,tenant_id,source_event_id,digest,body,transaction_type) "
            "VALUES(%s,%s,%s,%s,'{}','FUNDING')",
            (tenant + ":empty", tenant, tenant + ":empty-source", "a" * 64),
        )
    with pytest.raises(psycopg.Error, match="unbalanced"), ledger.store.connection() as conn:
        tx = tenant + ":unbalanced"
        conn.execute(
            "INSERT INTO ct_ledger_transactions "
            "(transaction_id,tenant_id,source_event_id,digest,body,transaction_type) "
            "VALUES(%s,%s,%s,%s,'{}','FUNDING')",
            (tx, tenant, tx + ":source", "a" * 64),
        )
        for label, amount in (("a", "1"), ("b", "-2")):
            conn.execute(
                "INSERT INTO ct_ledger_postings "
                "(posting_id,transaction_id,tenant_id,portfolio_id,account,asset,amount) "
                "VALUES(%s,%s,%s,%s,'AVAILABLE','USDT',%s)",
                (tx + label, tx, tenant, p[Mode.MATH], amount),
            )


def test_committed_transaction_cannot_gain_postings(ledger):
    ledger, tenant, p = ledger
    tx = command(tenant, p[Mode.MATH], "100", "FUNDING", "fund")
    ledger.append(tx)
    with pytest.raises(psycopg.Error, match="cannot gain"), ledger.store.connection() as conn:
        conn.execute(
            "INSERT INTO ct_ledger_postings "
            "(posting_id,transaction_id,tenant_id,portfolio_id,account,asset,amount) "
            "VALUES(%s,%s,%s,%s,'AVAILABLE','USDT',1)",
            (tenant + ":late", tx.transaction_id, tenant, p[Mode.MATH]),
        )
    assert ledger.balance(tenant, p[Mode.MATH], "AVAILABLE", "USDT") == 100


def test_full_compensation_cannot_repeat_or_change_attribution(ledger):
    ledger, tenant, p = ledger
    tx = command(tenant, p[Mode.MATH], "100", "FUNDING", "fund")
    ledger.append(tx)
    reversal = compensate(
        tx, tenant + ":reverse", tenant + ":reverse-source", "owner", "CORRECTION", "proof", NOW
    )
    ledger.append(reversal)
    assert not ledger.append(reversal)
    another = LedgerTransaction.model_validate(
        reversal.model_dump()
        | {"transaction_id": tenant + ":reverse2", "source_event_id": tenant + ":reverse-source2"}
    )
    with pytest.raises(ConflictError):
        ledger.append(another)


def test_sql_controlled_balance_cannot_be_negative(ledger):
    ledger, tenant, p = ledger
    tx = command(tenant, p[Mode.MATH], "1", "FUNDING", "negative")
    with (
        pytest.raises(psycopg.Error, match="negative controlled"),
        ledger.store.connection() as conn,
    ):
        conn.execute(
            "INSERT INTO ct_ledger_transactions "
            "(transaction_id,tenant_id,source_event_id,digest,body,transaction_type) "
            "VALUES(%s,%s,%s,%s,%s,'FUNDING')",
            (tx.transaction_id, tenant, tx.source_event_id, "a" * 64, canonical(tx)),
        )
        for posting in tx.postings:
            conn.execute(
                "INSERT INTO ct_ledger_postings "
                "(posting_id,transaction_id,tenant_id,portfolio_id,account,asset,amount) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    posting.posting_id,
                    tx.transaction_id,
                    tenant,
                    posting.portfolio_id,
                    posting.account,
                    posting.asset,
                    posting.amount.copy_negate(),
                ),
            )
    assert ledger.balance(tenant, p[Mode.MATH], "AVAILABLE", "USDT") == 0


def test_sell_reservation_and_third_asset_fee_attribution(ledger):
    ledger, tenant, p = ledger
    portfolio = p[Mode.MATH]
    ledger.append(command(tenant, portfolio, "100", "FUNDING", "fund"))
    ledger.append(command(tenant, portfolio, "50", "RESERVATION", "buy-reserve", "buy1"))
    fee_fund = move(
        tenant + ":bnb-fund",
        tenant,
        tenant + ":bnb-source",
        "owner",
        "fixture",
        NOW,
        portfolio,
        "BNB",
        "0.1",
        "FUNDING",
    )
    ledger.append(fee_fund)
    buy = Fill(
        fill_id="buy-fill",
        order_id="buy1",
        venue_fill_id="buy-venue",
        quantity="0.1",
        price="100",
        fee_amount="0.001",
        fee_asset="BNB",
        timestamp=NOW,
    )
    ledger.append(
        account_fill(
            tenant + ":buy-fill",
            tenant,
            tenant + ":buy-source",
            "execution",
            "venue-fixture",
            NOW,
            portfolio,
            "BUY",
            "BTC",
            "USDT",
            buy,
            "venue-price.v1",
        )
    )
    assert ledger.balance(tenant, portfolio, "AVAILABLE", "BNB") == Decimal("0.099")
    sell_reservation = move(
        tenant + ":sell-reserve",
        tenant,
        tenant + ":sell-reserve-source",
        "execution",
        "approved-intent",
        NOW,
        portfolio,
        "BTC",
        "0.05",
        "RESERVATION",
        "sell1",
        reserve_account="INVENTORY",
    )
    ledger.append(sell_reservation)
    sell = Fill(
        fill_id="sell-fill",
        order_id="sell1",
        venue_fill_id="sell-venue",
        quantity="0.05",
        price="110",
        fee_amount="0.01",
        fee_asset="USDT",
        timestamp=NOW,
    )
    ledger.append(
        account_fill(
            tenant + ":sell-fill",
            tenant,
            tenant + ":sell-source",
            "execution",
            "venue-fixture",
            NOW,
            portfolio,
            "SELL",
            "BTC",
            "USDT",
            sell,
            "venue-price.v1",
        )
    )
    assert ledger.balance(tenant, portfolio, "RESERVED", "BTC") == 0
    assert ledger.balance(tenant, portfolio, "INVENTORY", "BTC") == Decimal("0.05")
    assert ledger.balance(tenant, portfolio, "AVAILABLE", "USDT") == Decimal("55.49")
    from crazytrader_ledger.attribution import positions

    attributed = positions(ledger.history(tenant), tenant, portfolio, NOW)
    assert attributed[0].quantity == Decimal("0.05")
    assert attributed[0].cost_basis == 5
    assert attributed[0].realized_pnl is None
    assert attributed[0].fee_valuation_pending
    snapshot = ledger.snapshot(tenant, portfolio, NOW)
    assert next(b for b in snapshot.balances if b.asset == "BTC").total_held == Decimal("0.05")
