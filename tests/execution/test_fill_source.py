"""Preserved venue truth cannot confer different typed financial authority."""

import json
from datetime import UTC, datetime

import pytest
from crazytrader_contracts.codec import digest
from crazytrader_contracts.execution import VenueFillBatch


def source_batch():
    identity = digest(json.dumps(["tenant", "account", "BTCUSDT", 7], separators=(",", ":")))
    observed = "2026-10-03T00:00:00Z"
    raw = {
        "symbol": "BTCUSDT",
        "id": 7,
        "orderId": 101,
        "qty": "0.04",
        "price": "100",
        "quoteQty": "4",
        "commission": "0.01",
        "commissionAsset": "USDT",
        "time": 1790985600000,
        "isBuyer": False,
    }
    scope = {
        "tenant_id": "tenant",
        "venue_account_ref": "account",
        "execution_request_id": "execution",
        "client_order_id": "ct_owned",
        "venue_order_id": "101",
        "symbol": "BTCUSDT",
        "side": "SELL",
    }
    return {
        **scope,
        "request_sha256": "a" * 64,
        "observed_at": observed,
        "order_observation": {
            **scope,
            "request_sha256": "a" * 64,
            "observed_at": observed,
            "action": "QUERY",
            "requested_quantity": "0.1",
            "filled_quantity": "0.04",
            "status": "PARTIALLY_FILLED",
        },
        "available": True,
        "complete": True,
        "raw_json": json.dumps([raw]),
        "fills": [
            {
                **scope,
                "raw_trade_id": 7,
                "fill": {
                    "fill_id": "fill:" + identity,
                    "venue_fill_id": "vfill:" + identity,
                    "order_id": "order",
                    "quantity": "0.04",
                    "price": "100",
                    "fee_amount": "0.01",
                    "fee_asset": "USDT",
                    "timestamp": observed,
                },
            }
        ],
    }


def test_exact_source_and_typed_financial_values_are_bound():
    batch = VenueFillBatch.model_validate(source_batch())
    assert batch.fills[0].fill.timestamp == datetime(2026, 10, 3, tzinfo=UTC)
    changed = source_batch()
    changed["fills"][0]["fill"]["fee_amount"] = "0.02"
    with pytest.raises(ValueError, match="preserved source"):
        VenueFillBatch.model_validate(changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("qty", 0.04),
        ("id", True),
        ("isBuyer", True),
        ("commissionAsset", "BNB"),
        ("quoteQty", "3.99"),
        ("time", 1790985600001),
        ("orderId", 102),
    ],
)
def test_raw_financial_coercion_or_identity_changes_fail(field, value):
    changed = source_batch()
    rows = json.loads(changed["raw_json"])
    rows[0][field] = value
    changed["raw_json"] = json.dumps(rows)
    with pytest.raises(ValueError):
        VenueFillBatch.model_validate(changed)
