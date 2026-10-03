"""Actual isolated unmodified engine/result durability, not execution permission."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.simulation import (
    NativeSimulationJob,
    NativeSimulationReceipt,
    SimulationCostProfile,
)
from crazytrader_contracts.venue_rules import VenueRuleReceipt
from crazytrader_execution.native_transport import NativeSimulationTransport
from crazytrader_market.rules import capture_rules

from tests.test_venue_rules import exchange_info

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "infra/spikes/python/.venv/bin/python"
pytestmark = pytest.mark.skipif(
    not PYTHON.exists(), reason="pinned optional native simulation environment required"
)


def job(quantity="0.1"):
    now = datetime.now(UTC)
    raw = exchange_info()
    raw["symbols"][0]["filters"].append(
        {"filterType": "PRICE_FILTER", "minPrice": "0", "maxPrice": "0", "tickSize": "0.01"}
    )
    receipt = VenueRuleReceipt(
        tenant_id="tenant", rules=capture_rules(raw, "BTCUSDT", "SANDBOX", now)
    )
    costs = SimulationCostProfile(
        profile_id="native-fixture", taker_fee_bps="10", maximum_slippage_bps="0", fee_asset="USDT"
    )
    return NativeSimulationJob(
        execution_request_id="request",
        order_id="order",
        request_sha256="a" * 64,
        tenant_id="tenant",
        portfolio_id="portfolio",
        venue_account_ref="fixture",
        client_order_id="ct_native_owned",
        symbol="BTCUSDT",
        quantity=quantity,
        reference_price="100",
        reference_risk_record_sha256="b" * 64,
        ledger_head_sha256="c" * 64,
        venue_rules=receipt,
        costs=costs,
        starting_base="1",
        starting_quote="0",
        event_at=now,
    )


def transport(tmp_path):
    return NativeSimulationTransport(
        PYTHON,
        ROOT / "services/execution/nautilus_simulation_worker.py",
        ROOT / "packages/contracts/src",
        tmp_path,
    )


def test_native_receipt_survives_worker_response_interruption_and_never_runs_twice(tmp_path):
    expected = job()
    adapter = transport(tmp_path)
    receipt = adapter.simulate(expected, interrupt_after_result=True)
    assert receipt.available, receipt.raw_json
    raw = json.loads(receipt.raw_json)
    assert Decimal(raw["after"]["BTC"]) == Decimal("0.9")
    assert Decimal(raw["after"]["USDT"]) == Decimal("9.99")
    assert raw["fills"][0]["commission"] == "0.01000000 USDT"
    restarted = transport(tmp_path)
    assert restarted.recover_result(expected) == receipt
    assert restarted.simulate(expected) == receipt
    assert len(list(tmp_path.glob("*.claimed"))) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_existing_claim_without_result_is_unresolved_not_a_native_retry(tmp_path):
    expected = job()
    (tmp_path / (digest(canonical(expected)) + ".claimed")).write_text(canonical(expected))
    receipt = transport(tmp_path).simulate(expected)
    assert not receipt.available
    assert receipt.raw_json is None
    assert not list(tmp_path.glob("*.json"))


def test_native_rounding_loss_stays_unavailable_and_preserves_claim(tmp_path):
    expected = job("0.100000000000000001")
    receipt = transport(tmp_path).simulate(expected)
    assert not receipt.available
    assert transport(tmp_path).simulate(expected) == receipt


def test_changed_cash_cannot_validate_as_same_native_fill_proof(tmp_path):
    receipt = transport(tmp_path).simulate(job())
    assert receipt.available
    altered = receipt.model_dump()
    raw = json.loads(altered["raw_json"])
    raw["after"]["USDT"] = "10"
    altered["raw_json"] = json.dumps(raw)
    with pytest.raises(ValueError, match="native actual cash"):
        NativeSimulationReceipt.model_validate(altered)


@pytest.mark.parametrize(
    "mutation", ["boolean-order-count", "changed-native-time", "wrong-quote-currency"]
)
def test_native_source_identity_and_clock_are_not_coercible(tmp_path, mutation):
    receipt = transport(tmp_path).simulate(job())
    assert receipt.available
    altered = receipt.model_dump()
    raw = json.loads(altered["raw_json"])
    if mutation == "boolean-order-count":
        raw["orders"] = True
    elif mutation == "changed-native-time":
        raw["fills"][0]["ts_event"] += 1000
    else:
        raw["fills"][0]["currency"] = "BTC"
    altered["raw_json"] = json.dumps(raw)
    with pytest.raises(ValueError):
        NativeSimulationReceipt.model_validate(altered)


def test_compensating_subquantum_cash_and_fee_cannot_fake_native_precision(tmp_path):
    receipt = transport(tmp_path).simulate(job())
    assert receipt.available
    altered = receipt.model_dump()
    raw = json.loads(altered["raw_json"])
    raw["fills"][0]["commission"] = "0.010000005 USDT"
    raw["after"]["USDT"] = "9.989999995"
    altered["raw_json"] = json.dumps(raw)
    with pytest.raises(ValueError, match="native actual cash"):
        NativeSimulationReceipt.model_validate(altered)


def test_native_financial_fill_uses_cash_source_and_rejects_amount_or_side_tamper(tmp_path):
    from crazytrader_contracts.native_fills import NativeSimulationFill, sourced_fill
    from crazytrader_ledger.commands import account_native_fill

    receipt = transport(tmp_path).simulate(job())
    fill, gross = sourced_fill(receipt)
    assert gross == Decimal("10")
    with pytest.raises(ValueError, match="raw cash/event"):
        NativeSimulationFill(receipt=receipt, fill=fill, quote_quantity="9.99")
    evidence = NativeSimulationFill(receipt=receipt, fill=fill, quote_quantity=gross)
    with pytest.raises(ValueError, match="evidence mismatch"):
        account_native_fill(
            "tx",
            "tenant",
            "source",
            "actor",
            "native",
            fill.timestamp,
            "portfolio",
            "BUY",
            "BTC",
            "USDT",
            evidence,
            "native",
        )
    tx = account_native_fill(
        "tx",
        "tenant",
        "source",
        "actor",
        "native",
        fill.timestamp,
        "portfolio",
        "SELL",
        "BTC",
        "USDT",
        evidence,
        "native",
    )
    assert sum(
        p.amount for p in tx.postings if p.asset == "USDT" and p.account == "AVAILABLE"
    ) == Decimal("9.99")
