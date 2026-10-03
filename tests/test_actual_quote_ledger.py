"""Actual venue quote amounts, precision and BUY quote-fee reservation without floats."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from crazytrader_contracts.codec import digest
from crazytrader_contracts.models import Fill
from crazytrader_contracts.venue_fills import QuoteFillIdentity, VenueQuoteFill
from crazytrader_ledger.attribution import positions
from crazytrader_ledger.commands import account_actual_quote_fill

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def evidence(
    side="BUY",
    quantity="0.100000000000000001",
    price="133.33333333",
    quote="13.33333333",
    fee="0.01",
    raw_id=7,
    tenant="tenant",
    rule_ref="a" * 64,
):
    scope = digest(json.dumps([tenant, "account", "BTCUSDT", raw_id], separators=(",", ":")))
    fill = Fill(
        fill_id="fill:" + scope,
        venue_fill_id="vfill:" + scope,
        order_id="order",
        quantity=quantity,
        price=price,
        fee_asset="USDT",
        fee_amount=fee,
        timestamp=NOW,
    )
    identity = QuoteFillIdentity(
        tenant_id=tenant,
        venue_account_ref="account",
        execution_request_id="execution",
        client_order_id="ct_owned",
        venue_order_id="101",
        symbol="BTCUSDT",
        side=side,
        raw_trade_id=raw_id,
        fill=fill,
    )
    row = {
        "id": raw_id,
        "orderId": 101,
        "time": 1790985600000,
        "symbol": "BTCUSDT",
        "isBuyer": side == "BUY",
        "qty": quantity,
        "price": price,
        "quoteQty": quote,
        "commission": fee,
        "commissionAsset": "USDT",
    }
    return VenueQuoteFill(
        identity=identity,
        quote_quantity=quote,
        quote_precision=8,
        venue_rule_receipt_sha256=rule_ref,
        raw_trade_json=json.dumps(row),
    )


def transaction(data, transaction_id="fill-transaction"):
    return account_actual_quote_fill(
        transaction_id,
        "tenant",
        transaction_id + ":source",
        "owner",
        "venue",
        NOW,
        "portfolio",
        data.identity.side,
        "BTC",
        "USDT",
        data,
        "actual-quote",
    )


def test_actual_quote_amount_controls_cash_fees_and_cost_basis():
    data = evidence()
    tx = transaction(data)
    reserved = sum(
        (p.amount for p in tx.postings if p.account == "RESERVED" and p.asset == "USDT"), Decimal(0)
    )
    assert reserved == Decimal("-13.34333333")
    assert (
        tx.quote_evidence.quote_quantity != data.identity.fill.quantity * data.identity.fill.price
    )
    view = positions((tx,), "tenant", "portfolio", NOW)[0]
    assert view.cost_basis == Decimal("13.343333330000000000")
    assert view.quantity == Decimal("0.100000000000000001")


def test_zero_quote_truth_has_no_zero_postings_or_fictitious_cash():
    tx = transaction(evidence(quantity="0.000000001", price="0.01", quote="0", fee="0"))
    assert len(tx.postings) == 2
    assert all(p.asset == "BTC" for p in tx.postings)
    assert positions((tx,), "tenant", "portfolio", NOW)[0].cost_basis == 0


@pytest.mark.parametrize("quote", ["13.333333331", "13.33333330", "14"])
def test_wrong_precision_or_quote_delta_cannot_be_journal_authority(quote):
    with pytest.raises(ValueError):
        evidence(quote=quote)


def test_preserved_quote_row_and_typed_values_cannot_be_disconnected():
    data = evidence()
    changed = data.model_dump()
    changed["quote_quantity"] = Decimal("13.33333334")
    with pytest.raises(ValueError, match="preserved source"):
        VenueQuoteFill.model_validate(changed)
    rows = json.loads(changed["raw_trade_json"])
    rows["quoteQty"] = 13.33333333
    changed["raw_trade_json"] = json.dumps(rows)
    with pytest.raises(ValueError, match="financial strings"):
        VenueQuoteFill.model_validate(changed)
