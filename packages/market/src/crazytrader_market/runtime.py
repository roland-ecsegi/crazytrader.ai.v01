"""Owner-configured read-only market cycle; no signed venue capability."""

from datetime import UTC, datetime
from pathlib import Path

from crazytrader_platform.runtime import required
from crazytrader_platform.storage import EventStore

from .adapter import PublicMarketClient, normalize_metadata
from .archive import AnalyticalTrades, HistoricalIngestor, S3Artifacts
from .worker import MarketWorker


def main() -> None:
    try:
        environment = required("CT_MARKET_ENVIRONMENT")
        if environment not in {"PUBLIC", "SANDBOX"}:
            raise ValueError("invalid market environment")
        client = PublicMarketClient(
            Path(required("CT_MARKET_SDK_PYTHON")),
            Path(required("CT_MARKET_SDK_SCRIPT")),
            environment,  # type: ignore[arg-type]
        )
        symbol = required("CT_MARKET_SYMBOL")
        raw = client.read("exchange_info", symbol)
        if not isinstance(raw, dict) or not isinstance(raw.get("symbols"), list):
            raise ValueError("invalid instrument response")
        symbols = raw["symbols"]
        if len(symbols) != 1 or symbols[0].get("symbol") != symbol:
            raise ValueError("instrument identity mismatch")
        metadata = normalize_metadata(symbols[0], client.environment, datetime.now(UTC))
        store = EventStore(required("CT_DATABASE_DSN"))
        objects = S3Artifacts(
            required("CT_S3_ENDPOINT"),
            required("CT_S3_BUCKET"),
            required("CT_S3_ACCESS_KEY"),
            required("CT_S3_SECRET_KEY"),
        )
        analytics = AnalyticalTrades(
            required("CT_CLICKHOUSE_HOST"),
            int(required("CT_CLICKHOUSE_PORT")),
            required("CT_CLICKHOUSE_USER"),
            required("CT_CLICKHOUSE_PASSWORD"),
        )
        worker = MarketWorker(
            required("CT_TENANT_ID"),
            metadata,
            client,
            HistoricalIngestor(store, objects, analytics),
            store,
        )
        worker.poll()
    except Exception:
        raise SystemExit("market cycle failed; owner-local health inspection required") from None
    print("read-only market cycle persisted; no certification advancement")


if __name__ == "__main__":
    main()
