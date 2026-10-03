"""Source-first historical archive with retryable commits and immutable record identity.

ClickHouse is an analytical projection. PostgreSQL identity manifests are canonical;
query projection with GROUP BY record_key (ReplacingMergeTree is asynchronous).
"""

import json
from typing import Any

import boto3  # type: ignore[import-untyped]
import clickhouse_connect
from botocore.config import Config  # type: ignore[import-untyped]
from crazytrader_contracts.market import InstrumentMetadata, MarketTrade
from crazytrader_platform.storage import ConflictError, EventStore, canonical, digest

from .adapter import normalize_trade


class S3Artifacts:
    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                connect_timeout=3,
                read_timeout=5,
                retries={"max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )

    def write(self, key: str, body: bytes) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=body, ContentType="application/json"
        )
        observed = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        if observed != body:
            raise ConflictError("source object read-back integrity failure")


class AnalyticalTrades:
    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=username,
            password=password,
            connect_timeout=3,
            send_receive_timeout=5,
        )

    def migrate(self) -> None:
        self.client.command("""CREATE TABLE IF NOT EXISTS ct_market_trades (
            record_key String, tenant_id String, environment LowCardinality(String),
            symbol LowCardinality(String), trade_id UInt64, record_digest String,
            source_digest String, body String
        ) ENGINE=ReplacingMergeTree ORDER BY record_key""")

    def write(self, tenant: str, trades: tuple[MarketTrade, ...], source: str) -> None:
        rows: list[list[Any]] = []
        for trade in trades:
            key = digest(json.dumps([tenant, trade.environment, trade.symbol, trade.trade_id]))
            body = canonical(trade)
            rows.append(
                [
                    key,
                    tenant,
                    trade.environment,
                    trade.symbol,
                    trade.trade_id,
                    digest(body),
                    source,
                    body,
                ]
            )
        self.client.insert(
            "ct_market_trades",
            rows,
            column_names=[
                "record_key",
                "tenant_id",
                "environment",
                "symbol",
                "trade_id",
                "record_digest",
                "source_digest",
                "body",
            ],
        )


class HistoricalIngestor:
    def __init__(
        self, store: EventStore, objects: S3Artifacts, analytics: AnalyticalTrades
    ) -> None:
        self.store, self.objects, self.analytics = store, objects, analytics

    def ingest(
        self, tenant: str, metadata: InstrumentMetadata, raw: list[dict[str, object]]
    ) -> str:
        if not raw or len(raw) > 1000:
            raise ValueError("bounded nonempty batch required")
        trades = tuple(normalize_trade(item, metadata) for item in raw)
        if any(
            b.trade_id != a.trade_id + 1 or b.exchange_at < a.exchange_at
            for a, b in zip(trades, trades[1:], strict=False)
        ):
            raise ValueError("noncontiguous historical batch")
        source_body = json.dumps(
            {
                "tenant_id": tenant,
                "metadata": metadata.model_dump(mode="json"),
                "parser_version": "binance-agg-trade.v1",
                "records": raw,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        source = digest(source_body)
        key = "market/v1/" + source + ".json"
        # Source is persisted and read-back verified before manifest/projection changes.
        self.objects.write(key, source_body.encode())
        identity = (tenant, metadata.environment, metadata.symbol)
        with self.store.connection() as conn:
            # Transaction advisory lock serializes symbol identity across workers.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (json.dumps(identity),)
            )
            existing_source = conn.execute(
                "SELECT tenant_id FROM ct_market_sources WHERE digest=%s", (source,)
            ).fetchone()
            if existing_source is not None and existing_source["tenant_id"] != tenant:
                raise ConflictError("source ownership conflict")
            conn.execute(
                "INSERT INTO ct_market_sources "
                "(digest,tenant_id,environment,symbol,metadata_version,parser_version,object_key) "
                "VALUES(%s,%s,%s,%s,%s,'binance-agg-trade.v1',%s) ON CONFLICT DO NOTHING",
                (source, *identity, metadata.metadata_version, key),
            )
            for trade in trades:
                body = canonical(trade)
                previous = conn.execute(
                    "SELECT digest FROM ct_market_records WHERE "
                    "tenant_id=%s AND environment=%s AND symbol=%s AND trade_id=%s",
                    (*identity, trade.trade_id),
                ).fetchone()
                if previous is not None and previous["digest"] != digest(body):
                    raise ConflictError("trade ID content/metadata conflict")
                conn.execute(
                    "INSERT INTO ct_market_records "
                    "(tenant_id,environment,symbol,trade_id,digest,source_digest,body) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (*identity, trade.trade_id, digest(body), source, body),
                )
            conn.execute(
                "INSERT INTO ct_market_batches(source_digest,status) VALUES(%s,'PENDING') "
                "ON CONFLICT DO NOTHING",
                (source,),
            )
        try:
            # May repeat after lost acknowledgment; logical keys dedup projection reads.
            self.analytics.write(tenant, trades, source)
        except Exception:
            with self.store.connection() as conn:
                conn.execute(
                    "UPDATE ct_market_batches SET status='FAILED',error_category="
                    "'ANALYTICAL_WRITE_FAILED',updated_at=now() WHERE source_digest=%s",
                    (source,),
                )
            raise RuntimeError("historical projection unavailable") from None
        with self.store.connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (json.dumps(identity),)
            )
            row = conn.execute(
                "SELECT last_trade_id FROM ct_market_watermarks WHERE "
                "tenant_id=%s AND environment=%s AND symbol=%s",
                identity,
            ).fetchone()
            # Do not advance a cursor across a missing range. First batch defines baseline.
            if row is not None and trades[0].trade_id > int(str(row["last_trade_id"])) + 1:
                raise ValueError("watermark gap requires earlier backfill")
            conn.execute(
                "UPDATE ct_market_batches SET status='COMMITTED',error_category=NULL,"
                "updated_at=now() WHERE source_digest=%s",
                (source,),
            )
            conn.execute(
                "INSERT INTO ct_market_watermarks "
                "(tenant_id,environment,symbol,last_trade_id,source_digest) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(tenant_id,environment,symbol) DO UPDATE SET "
                "last_trade_id=excluded.last_trade_id,source_digest=excluded.source_digest "
                "WHERE ct_market_watermarks.last_trade_id < excluded.last_trade_id",
                (*identity, trades[-1].trade_id, source),
            )
        return source
