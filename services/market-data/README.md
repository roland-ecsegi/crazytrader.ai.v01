# Read-only market worker

The root locked environment runs `python -m crazytrader_market.runtime` for one
bounded cycle. A supervisor may schedule it; restart requires fresh observations.
This REST poller does not claim websocket or elapsed certification evidence.

Install the official SDK separately with `uv sync --locked --project services/market-data/sdk`.
The worker starts that interpreter with an allowlisted proxy/CA environment and
three fixed unsigned public GET operations. It never receives execution/owner
credentials. SDK `to_dict()` is required: generic `model_dump()` leaks generated
union wrappers into filter payloads.

Required owner-local configuration: `CT_MARKET_ENVIRONMENT` (`PUBLIC` or `SANDBOX`),
`CT_MARKET_SYMBOL`, `CT_MARKET_SDK_PYTHON`, `CT_MARKET_SDK_SCRIPT`, `CT_TENANT_ID`,
`CT_DATABASE_DSN`, `CT_S3_ENDPOINT`, `CT_S3_BUCKET`, `CT_S3_ACCESS_KEY`,
`CT_S3_SECRET_KEY`, `CT_CLICKHOUSE_HOST`, `CT_CLICKHOUSE_PORT`,
`CT_CLICKHOUSE_USER`, `CT_CLICKHOUSE_PASSWORD`. Apply migrations 001/002 and the
analytical schema through a separate administrative identity; precreate the bucket.
TLS, scoped access policy, versioning and deletion protection are required before
production deployment. Anonymous local fixtures confer no production readiness.

Historical batches are contiguous, at most 1,000 records. PostgreSQL immutable
record identities reject changed price/quantity/metadata even for old IDs. S3
source JSON contains metadata and parser version and is verified by read-back.
ClickHouse `ReplacingMergeTree` is an analytical projection: queries deduplicate
by `record_key`/`FINAL`; physical merge timing never authorizes finance.
Projection failure leaves a FAILED retryable manifest and no watermark advancement.
Gap batches cannot advance a committed watermark; replay earlier missing ranges.
Monitor gap recovery needs complete contiguous backfill and fresh live warmup.
Depth needs a fresh REST snapshot plus bridging deltas; reconnect alone never
restores health. No current snapshot has an invented exchange timestamp.

The root/core toolchain remains Ruff 0.14.3; the official SDK's common package
requires Ruff <0.13 and therefore uses its separate lock. Data clients boto3
1.40.53 and clickhouse-connect 0.9.2 are Apache-2.0; upstream SDK is MIT.
