"""Strict account financial strings and bounded complete pagination."""

import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from crazytrader_contracts.account import VenueAccountRead, history_rows

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def source():
    account = {
        "canTrade": True,
        "canWithdraw": False,
        "balances": [{"asset": "BTC", "free": "1", "locked": "0"}],
    }
    return dict(
        tenant_id="tenant",
        venue_account_ref="account",
        anchor_request_id="request",
        anchor_request_sha256="a" * 64,
        symbols=("BTCUSDT",),
        started_at=NOW,
        finished_at=NOW,
        available=True,
        raw_json=json.dumps(
            {
                "before": account,
                "after": deepcopy(account),
                "open": [],
                "history": {"BTCUSDT": {"orders": [[]], "fills": [[]]}},
            }
        ),
    )


def test_float_balance_and_duplicate_asset_are_not_available_account_proof():
    for value in (1.0, "-1"):
        data = source()
        raw = json.loads(data["raw_json"])
        raw["after"]["balances"][0]["free"] = value
        data["raw_json"] = json.dumps(raw)
        with pytest.raises(ValueError):
            VenueAccountRead.model_validate(data)
    data = source()
    raw = json.loads(data["raw_json"])
    raw["after"]["balances"] *= 2
    data["raw_json"] = json.dumps(raw)
    with pytest.raises(ValueError, match="unique account asset"):
        VenueAccountRead.model_validate(data)


def test_short_final_page_and_strict_ascending_ids_are_required():
    rows = [{"id": i, "symbol": "BTCUSDT"} for i in range(1000)]
    assert len(history_rows([rows, []], "id", "BTCUSDT")) == 1000
    for pages in ([rows], [[], rows], [rows, [rows[0]]]):
        with pytest.raises(ValueError):
            history_rows(pages, "id", "BTCUSDT")


def test_unavailable_raw_source_cannot_claim_completed_account_proof():
    data = source()
    data.update(available=False, raw_json=None)
    assert VenueAccountRead.model_validate(data).available is False
    data["available"] = True
    with pytest.raises(ValueError):
        VenueAccountRead.model_validate(data)
