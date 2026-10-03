import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from botocore.exceptions import EndpointConnectionError
from crazytrader_contracts.market import InstrumentMetadata
from crazytrader_market.archive import AnalyticalTrades, HistoricalIngestor, S3Artifacts
from crazytrader_platform.storage import ConflictError, EventStore

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="real market stores required")


def test_real_source_projection_restart_and_failures():
    store = EventStore(os.environ["CT_TEST_DSN"])
    for path in sorted(Path("infra/migrations").glob("*.sql")):
        store.migrate(path)
    objects = S3Artifacts(os.environ["CT_TEST_S3"], "market-fixture", "fixture", "fixture")
    objects.client.create_bucket(Bucket=objects.bucket)
    analytics = AnalyticalTrades(
        "127.0.0.1", int(os.environ["CT_TEST_CH_PORT"]), "fixture", "fixture"
    )
    analytics.migrate()
    metadata = InstrumentMetadata(
        environment="SANDBOX",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        status="TRADING",
        tick_size="0.01",
        quantity_step="0.001",
        min_quantity="0.001",
        max_quantity="100",
        min_notional="5",
        metadata_version="a" * 64,
        observed_at=datetime(2026, 10, 3, tzinfo=UTC),
    )
    raw = [{"a": i, "p": "100.01", "q": "0.100", "T": 1790985600000, "m": False} for i in (1, 2)]
    ingestor = HistoricalIngestor(store, objects, analytics)
    source = ingestor.ingest("fixture", metadata, raw)
    assert ingestor.ingest("fixture", metadata, raw) == source
    result = analytics.client.query("SELECT count(DISTINCT record_key) FROM ct_market_trades")
    assert result.first_row[0] == 2
    with store.connection() as conn:
        assert (
            conn.execute("SELECT last_trade_id FROM ct_market_watermarks").fetchone()[
                "last_trade_id"
            ]
            == 2
        )
        assert conn.execute("SELECT count(*) AS n FROM ct_market_records").fetchone()["n"] == 2
    # New process-like objects use durable database state, not in-memory cursor.
    restarted = HistoricalIngestor(EventStore(os.environ["CT_TEST_DSN"]), objects, analytics)
    with pytest.raises(ConflictError):
        restarted.ingest("fixture", metadata, [raw[0] | {"p": "101"}])
    with pytest.raises(ValueError, match="watermark gap"):
        restarted.ingest("fixture", metadata, [raw[0] | {"a": 4}])
    # An actual unreachable store must not advance the committed cursor.
    docker_command = ["docker", "--host=unix:///var/run/docker.sock"]
    subprocess.run(
        docker_command + ["stop", os.environ["CT_TEST_CH_CONTAINER"]],
        check=True,
        capture_output=True,
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        HistoricalIngestor(store, objects, analytics).ingest(
            "fixture", metadata, [raw[0] | {"a": 3}]
        )
    with store.connection() as conn:
        assert (
            conn.execute("SELECT last_trade_id FROM ct_market_watermarks").fetchone()[
                "last_trade_id"
            ]
            == 2
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM ct_market_batches WHERE status='FAILED'"
            ).fetchone()["n"]
            == 1
        )
    subprocess.run(
        docker_command + ["start", os.environ["CT_TEST_CH_CONTAINER"]],
        check=True,
        capture_output=True,
    )
    new_port = (
        subprocess.run(
            docker_command + ["port", os.environ["CT_TEST_CH_CONTAINER"], "8123/tcp"],
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .rsplit(":", 1)[1]
    )
    for _ in range(60):
        import time

        try:
            analytics = AnalyticalTrades("127.0.0.1", int(new_port), "fixture", "fixture")
            analytics.client.query("SELECT 1")
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise AssertionError("ClickHouse restart failed")
    restarted = HistoricalIngestor(store, objects, analytics)
    assert (
        analytics.client.query("SELECT count(DISTINCT record_key) FROM ct_market_trades").first_row[
            0
        ]
        >= 2
    )
    restarted.ingest("fixture", metadata, [raw[0] | {"a": 3}])
    with store.connection() as conn:
        assert (
            conn.execute("SELECT last_trade_id FROM ct_market_watermarks").fetchone()[
                "last_trade_id"
            ]
            == 3
        )
    unavailable = S3Artifacts("http://127.0.0.1:1", "market-fixture", "fixture", "fixture")
    with pytest.raises(EndpointConnectionError):
        HistoricalIngestor(store, unavailable, analytics).ingest(
            "fixture", metadata, [raw[0] | {"a": 4}]
        )
    with store.connection() as conn:
        assert (
            conn.execute("SELECT last_trade_id FROM ct_market_watermarks").fetchone()[
                "last_trade_id"
            ]
            == 3
        )


def test_worker_checkpoint_event_provenance_and_old_conflict():
    from crazytrader_market.adapter import PublicMarketClient
    from crazytrader_market.worker import MarketWorker

    store = EventStore(os.environ["CT_TEST_DSN"])
    objects = S3Artifacts(os.environ["CT_TEST_S3"], "market-fixture", "fixture", "fixture")
    # Reuse the bounded disposable collection; source hashes include tenant provenance.
    # Re-discover port because the preceding test restarts the container.
    command = [
        "docker",
        "--host=unix:///var/run/docker.sock",
        "port",
        os.environ["CT_TEST_CH_CONTAINER"],
        "8123/tcp",
    ]
    port = (
        subprocess.run(command, check=True, capture_output=True, text=True)
        .stdout.strip()
        .rsplit(":", 1)[1]
    )
    analytics = AnalyticalTrades("127.0.0.1", int(port), "fixture", "fixture")
    now = datetime(2026, 10, 3, tzinfo=UTC)
    metadata = InstrumentMetadata(
        environment="SANDBOX",
        symbol="ETHUSDT",
        base_asset="ETH",
        quote_asset="USDT",
        status="TRADING",
        tick_size="0.01",
        quantity_step="0.001",
        min_quantity="0.001",
        max_quantity="100",
        min_notional="5",
        metadata_version="b" * 64,
        observed_at=now,
    )

    class FixtureReads(PublicMarketClient):
        def __init__(self):
            self.environment = "SANDBOX"
            self.records = [
                {"a": i, "p": "100.01", "q": "0.100", "T": 1790985600000, "m": False}
                for i in (10, 11)
            ]

        def read(self, *args, **kwargs):
            return self.records

    client = FixtureReads()
    archive = HistoricalIngestor(store, objects, analytics)
    worker = MarketWorker("worker-fixture", metadata, client, archive, store)
    assert worker.poll(now) == 2
    assert worker.monitor.health(now) == "HEALTHY"
    events = [
        e
        for e in store.pending()
        if e.tenant_id == "worker-fixture" and e.event_type == "MarketTradeReceived.v1"
    ]
    assert len(events) == 2
    for event in events:
        assert store.consume_audit(event)
        assert not store.consume_audit(event)
    restarted = MarketWorker("worker-fixture", metadata, client, archive, store)
    assert restarted.monitor.health(now) == "DEGRADED"
    assert restarted.poll(now) == 0
    # An older ID conflict must latch readiness, not just the latest duplicate.
    client.records = [client.records[0] | {"p": "101"}]
    with pytest.raises(ConflictError):
        restarted.poll(now)
    assert restarted.monitor.checkpoint.conflict
    assert restarted.monitor.health(now) == "DEGRADED"
