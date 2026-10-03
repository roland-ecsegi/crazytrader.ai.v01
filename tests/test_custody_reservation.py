"""Deterministic original-source allocation and replay-safe release accounting."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from crazytrader_ledger.commands import release_custody, reserve_custody

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def reservation(inventory="0.06", available="0.04"):
    return reserve_custody(
        "tx",
        "tenant",
        "source",
        "owner",
        "proof",
        NOW,
        "portfolio",
        "BTC",
        Decimal("0.1"),
        "order",
        Decimal(inventory),
        Decimal(available),
    )


@pytest.mark.parametrize(
    "remaining,inventory,available",
    [("0.1", "0.06", "0.04"), ("0.06", "0.02", "0.04"), ("0.02", "0", "0.02")],
)
def test_proven_remainder_returns_to_original_custody(remaining, inventory, available):
    original = reservation()
    assert len(original.postings) == 3
    release = release_custody(
        original, Decimal(remaining), "release", "r-source", "owner", "query", NOW
    )
    amounts = {p.account: p.amount for p in release.postings}
    assert amounts.get("INVENTORY", 0) == Decimal(inventory)
    assert amounts.get("AVAILABLE", 0) == Decimal(available)
    assert amounts["RESERVED"] == -Decimal(remaining)


def test_insufficient_combined_custody_and_excess_release_are_rejected():
    with pytest.raises(ValueError, match="insufficient"):
        reservation("0.06", "0.03")
    with pytest.raises(ValueError, match="exceeds"):
        release_custody(
            reservation(), Decimal("0.11"), "release", "r-source", "owner", "query", NOW
        )


def test_balanced_but_cross_portfolio_reservation_cannot_authorize_release():
    original = reservation()
    altered = original.model_dump()
    altered["postings"] = [p.model_dump() for p in original.postings]
    altered["postings"][1]["portfolio_id"] = "other-portfolio"
    from crazytrader_contracts.ledger import LedgerTransaction

    with pytest.raises(ValueError, match="single owned"):
        release_custody(
            LedgerTransaction.model_validate(altered),
            Decimal("0.06"),
            "release",
            "source",
            "owner",
            "query",
            NOW,
        )
