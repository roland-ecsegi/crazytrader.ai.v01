from datetime import UTC, datetime, timedelta

import pytest
from crazytrader_contracts.market import BookDelta, BookLevel, BookSnapshot, MarketTrade
from crazytrader_market.book import BookMonitor
from crazytrader_market.monitor import TradeCheckpoint, TradeMonitor
from pydantic import ValidationError

NOW = datetime(2026, 10, 3, tzinfo=UTC)
IDENTITY = dict(environment="SANDBOX", symbol="BTCUSDT", metadata_version="a" * 64)


def trade(number=1, at=NOW, price="100"):
    return MarketTrade(
        **IDENTITY, trade_id=number, price=price, quantity="0.001", taker_side="BUY", exchange_at=at
    )


def monitor():
    return TradeMonitor(TradeCheckpoint(**IDENTITY))


def test_warmup_duplicate_stale_restart():
    m = monitor()
    assert m.health(NOW) == "UNKNOWN"
    assert m.observe(trade(), NOW)
    assert m.health(NOW) == "DEGRADED"
    assert m.observe(trade(2), NOW)
    assert m.health(NOW) == "HEALTHY"
    assert not m.observe(trade(2), NOW + timedelta(seconds=4))
    assert m.health(NOW + timedelta(seconds=6)) == "DEGRADED"
    restored = TradeMonitor(TradeCheckpoint.model_validate_json(m.checkpoint.model_dump_json()))
    assert restored.health(NOW) == "DEGRADED"
    m.disconnect()
    assert m.health(NOW) == "DEGRADED"


def test_conflicting_duplicate_latches():
    m = monitor()
    m.observe(trade(), NOW)
    with pytest.raises(ValueError, match="conflicting"):
        m.observe(trade(price="101"), NOW)
    assert not m.observe(trade(2), NOW)
    assert m.health(NOW) == "DEGRADED"


def test_gap_requires_contiguous_backfill_and_live_warmup():
    m = monitor()
    m.observe(trade(), NOW)
    assert not m.observe(trade(4), NOW)
    with pytest.raises(ValueError):
        m.recover((trade(2), trade(4)), NOW)
    with pytest.raises(ValueError):
        m.recover((trade(2), trade(3)), NOW)
    with pytest.raises(ValueError, match="backwards"):
        m.recover((trade(2), trade(3), trade(4)), NOW - timedelta(seconds=1))
    m.recover((trade(2), trade(3), trade(4)), NOW)
    assert m.health(NOW) == "DEGRADED"
    m.observe(trade(5), NOW)
    m.observe(trade(6), NOW)
    assert m.health(NOW) == "HEALTHY"


@pytest.mark.parametrize("offset", [-6, 1])
def test_bad_time_never_advances(offset):
    m = monitor()
    assert not m.observe(trade(at=NOW + timedelta(seconds=offset)), NOW)
    assert m.checkpoint.last_id is None
    assert m.health(NOW) != "HEALTHY"


@pytest.mark.parametrize("price", [1.0, "NaN", "Infinity", "1e-3", " 1", "0", "-1"])
def test_decimal_rejection(price):
    with pytest.raises(ValidationError):
        trade(price=price)


def snapshot():
    return BookSnapshot(
        **IDENTITY,
        last_sequence=10,
        observed_at=NOW,
        bids=(BookLevel(price="99", quantity="1"),),
        asks=(BookLevel(price="101", quantity="1"),),
    )


def delta(first=10, last=12, **kwargs):
    return BookDelta(
        **IDENTITY,
        first_sequence=first,
        last_sequence=last,
        exchange_at=NOW,
        bids=(),
        asks=(),
        **kwargs,
    )


def test_depth_bridge_gap_and_resnapshot():
    m = BookMonitor()
    assert not m.observe(delta(), NOW)
    m.resync(snapshot(), NOW)
    assert not m.healthy(NOW)
    assert m.observe(delta(), NOW)
    assert m.healthy(NOW)
    assert not m.observe(delta(), NOW + timedelta(seconds=4))
    assert not m.healthy(NOW + timedelta(seconds=6))
    assert not m.observe(delta(14, 14), NOW)
    assert not m.observe(delta(13, 13), NOW)
    m.resync(snapshot(), NOW)
    assert m.observe(delta(), NOW)
    m.disconnect()
    assert not m.healthy(NOW)


def test_book_deletion_and_cross_fail_closed():
    m = BookMonitor()
    m.resync(snapshot(), NOW)
    assert m.observe(delta(), NOW)
    update = delta(13, 13).model_copy(update={"bids": (BookLevel(price="102", quantity="1"),)})
    assert not m.observe(update, NOW)
    assert not m.healthy(NOW)
    assert max(m.bids) == 99  # failed update did not mutate verified book


def test_snapshot_stale_and_duplicates():
    m = BookMonitor()
    with pytest.raises(ValueError):
        m.resync(snapshot(), NOW + timedelta(seconds=6))
    with pytest.raises(ValueError):
        m.resync(snapshot().model_copy(update={"bids": snapshot().bids * 2}), NOW)


def test_typed_event_registry_provenance():
    from crazytrader_contracts.events import EventEnvelope, PayloadReference
    from crazytrader_platform.storage import canonical, digest, validate_payload

    payload = trade()
    fingerprint = digest(canonical(payload))
    event = EventEnvelope(
        event_id="fixture-trade-1",
        event_type="MarketTradeReceived.v1",
        schema_version="1",
        occurred_at=NOW,
        tenant_id="fixture",
        source_service="market-data",
        trace_id="trace",
        correlation_id="correlation",
        payload=PayloadReference(
            artifact_ref=fingerprint, sha256=fingerprint, payload_schema_ref="MarketTrade.v1"
        ),
    )
    validate_payload(event, payload)
    with pytest.raises(ValueError, match="provenance"):
        validate_payload(event.model_copy(update={"source_service": "untrusted"}), payload)
    with pytest.raises(ValueError, match="schema"):
        validate_payload(
            event.model_copy(
                update={
                    "payload": event.payload.model_copy(
                        update={"payload_schema_ref": "HealthChange.v1"}
                    )
                }
            ),
            payload,
        )


def test_sdk_subprocess_strips_credentials(monkeypatch):
    import subprocess
    from pathlib import Path

    from crazytrader_market.adapter import PublicMarketClient

    monkeypatch.setenv("BINANCE_API_SECRET", "fixture-not-a-secret")
    monkeypatch.setenv("CT_OWNER_TOKEN", "fixture-not-a-secret")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:8080")

    def run(command, **kwargs):
        assert "BINANCE_API_SECRET" not in kwargs["env"]
        assert "CT_OWNER_TOKEN" not in kwargs["env"]
        assert kwargs["env"]["HTTPS_PROXY"] == "http://proxy:8080"
        assert kwargs["timeout"] == 15
        return subprocess.CompletedProcess(command, 0, stdout="[]")

    monkeypatch.setattr(subprocess, "run", run)
    client = PublicMarketClient(Path("python"), Path("read_public.py"))
    assert client.read("agg_trades", "BTCUSDT") == []
    with pytest.raises(ValueError):
        client.read("new_order", "BTCUSDT")


def test_venue_alignment_uses_full_contract_precision():
    from decimal import Decimal

    from crazytrader_market.adapter import aligned

    assert aligned(
        Decimal("99999999999999999999.999999999999999999"), Decimal("0.000000000000000001")
    )
    assert not aligned(Decimal("99999999999999999999.999999999999999999"), Decimal("0.01"))


def test_normalized_depth_and_closed_candle():
    from crazytrader_contracts.market import InstrumentMetadata
    from crazytrader_market.adapter import normalize_candle, normalize_delta, normalize_snapshot

    metadata = InstrumentMetadata(
        **IDENTITY,
        base_asset="BTC",
        quote_asset="USDT",
        status="TRADING",
        tick_size="0.01",
        quantity_step="0.001",
        min_quantity="0.001",
        max_quantity="100",
        min_notional="5",
        observed_at=NOW,
    )
    snap = normalize_snapshot(
        {"lastUpdateId": 10, "bids": [["99", "1"]], "asks": [["101", "1"]]}, metadata, NOW
    )
    assert snap.observed_at == NOW
    assert not hasattr(snap, "exchange_at")
    raw_delta = {
        "e": "depthUpdate",
        "s": "BTCUSDT",
        "E": 1790985600000,
        "U": 11,
        "u": 12,
        "b": [["99", "0"]],
        "a": [],
    }
    assert normalize_delta(raw_delta, metadata).last_sequence == 12
    with pytest.raises(ValueError):
        normalize_delta(raw_delta | {"s": "ETHUSDT"}, metadata)
    with pytest.raises(ValueError):
        normalize_snapshot(
            {"lastUpdateId": 10, "bids": [["99.001", "1"]], "asks": []}, metadata, NOW
        )
    raw = {
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "x": True,
            "t": 1790985600000,
            "T": 1790985659999,
            "n": 2,
            "i": "1m",
            "o": "100",
            "h": "102",
            "l": "99",
            "c": "101",
            "v": "1.001",
        },
    }
    assert normalize_candle(raw, metadata).trade_count == 2
    with pytest.raises(ValueError):
        normalize_candle(raw | {"k": raw["k"] | {"x": False}}, metadata)
