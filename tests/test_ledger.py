from datetime import UTC, datetime
from decimal import Decimal

import pytest
from crazytrader_contracts.ledger import LedgerPosting, LedgerTransaction
from crazytrader_ledger.commands import compensate, move
from pydantic import ValidationError

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def funding(amount="100"):
    return move(
        "fund",
        "owner",
        "source",
        "owner",
        "bank-fixture",
        NOW,
        "reserve",
        "USDT",
        amount,
        "FUNDING",
    )


def test_balanced_and_full_precision_compensation():
    value = "99999999999999999999.999999999999999999"
    tx = funding(value)
    assert tx.postings[1].amount == Decimal(value)
    reversal = compensate(tx, "reverse", "reverse-source", "owner", "FIXTURE_ERROR", "proof", NOW)
    assert reversal.postings[0].amount == Decimal(value)
    assert reversal.correction_of_id == "fund"
    assert LedgerTransaction.model_validate_json(tx.model_dump_json()) == tx


def test_cross_asset_does_not_balance():
    tx = funding()
    data = tx.model_dump()
    data["postings"][1]["asset"] = "BTC"
    with pytest.raises(ValidationError, match="every asset"):
        LedgerTransaction.model_validate(data)


@pytest.mark.parametrize("value", [0, "0", "-1", 1.5, "NaN", "1e3"])
def test_invalid_funding(value):
    with pytest.raises((ValueError, ValidationError)):
        funding(value)


def test_posting_ownership_and_order_attribution():
    with pytest.raises(ValidationError):
        LedgerPosting(
            posting_id="x", portfolio_id=None, account="AVAILABLE", asset="USDT", amount="1"
        )
    with pytest.raises(ValidationError, match="order"):
        move(
            "reserve", "owner", "source", "owner", "proof", NOW, "math", "USDT", "1", "RESERVATION"
        )
    tx = funding()
    with pytest.raises(ValidationError, match="duplicate"):
        LedgerTransaction.model_validate(
            tx.model_dump() | {"postings": (tx.postings[0], tx.postings[0])}
        )


def test_exact_fill_cost_attribution_and_unknown_external_fee():
    from crazytrader_contracts.models import Fill
    from crazytrader_ledger.attribution import positions
    from crazytrader_ledger.commands import account_fill

    buy = Fill(
        fill_id="buy",
        order_id="buy-order",
        venue_fill_id="buy-venue",
        quantity="0.1",
        price="100",
        fee_amount="0.01",
        fee_asset="USDT",
        timestamp=NOW,
    )
    sell = Fill(
        fill_id="sell",
        order_id="sell-order",
        venue_fill_id="sell-venue",
        quantity="0.05",
        price="110",
        fee_amount="0.01",
        fee_asset="USDT",
        timestamp=NOW,
    )
    bought = account_fill(
        "buy-tx",
        "owner",
        "buy-source",
        "execution",
        "venue",
        NOW,
        "math",
        "BUY",
        "BTC",
        "USDT",
        buy,
        "venue-price.v1",
    )
    sold = account_fill(
        "sell-tx",
        "owner",
        "sell-source",
        "execution",
        "venue",
        NOW,
        "math",
        "SELL",
        "BTC",
        "USDT",
        sell,
        "venue-price.v1",
    )
    result = positions((bought, sold), "owner", "math", NOW)[0]
    assert result.quantity == Decimal("0.05")
    assert result.cost_basis == Decimal("5.005")
    assert result.realized_pnl == Decimal("0.485")
    assert not result.fee_valuation_pending
    compensated = compensate(
        sold, "sell-reverse", "sell-correction", "owner", "CORRECT", "proof", NOW
    )
    restored = positions((bought, sold, compensated), "owner", "math", NOW)[0]
    assert restored.quantity == Decimal("0.1")
    assert restored.cost_basis == Decimal("10.01")
    with pytest.raises(ValueError, match="provenance"):
        positions((sold,), "owner", "math", NOW)


def test_unchecked_model_copy_cannot_enter_financial_store():
    from crazytrader_ledger.store import LedgerStore
    from crazytrader_platform.storage import EventStore

    tx = funding()
    corrupted = tx.model_copy(
        update={"postings": (tx.postings[0], tx.postings[1].model_copy(update={"amount": 1.0}))}
    )
    with pytest.raises(ValidationError):
        LedgerStore(EventStore("not-a-database-dsn")).append(corrupted)
