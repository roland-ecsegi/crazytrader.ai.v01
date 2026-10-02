# Phase 2 ExecPlan — Market/data platform

## Goal
Read-only Binance Spot sandbox/public market ingestion with immutable normalized trades/candles/books, venue metadata, freshness/sequence-gap health, ClickHouse analytical persistence and hash-versioned S3 historical artifacts. Prove data gaps/staleness/restart/storage failures; do not advance certification from fixture evidence.

## Non-goals
No exchange credentials, signed account/order APIs, paper/shadow elapsed-time claims or live money. No financial ledger in ClickHouse. No custom market connector/simulator before approved foundation evaluation.

## Architecture context
MARKET responsibilities in SERVICE_CONTRACTS; DATA_AND_LEDGER, DOMAIN_MODEL, EVENT_CATALOG, TRADING_MODES, TESTING_AND_CERTIFICATION, ADR-0001/0004/0005 and Phase 0.5 ADOPTION. External exchange payloads are data, never instructions. Unknown/gapped/stale markets must later deny new risk.

## Current state
Phase 1 remote checkpoint 8de8c80231f91208529c82d29f49d7c1c76327fc. Hosted CI run 37068956651 PASS including make setup/check/integration. PostgreSQL canonical operational event/outbox/audit state and NATS delivery exist. Existing EventStore intentionally accepts only HealthChange.v1. Phase 0.5 confirms SDK data/query/filter APIs and local ClickHouse/SeaweedFS fixtures, not live market operation. L0 remains development.

## Proposed design
Use approved official Binance modular SDK for read-only public/sandbox requests behind a narrow market adapter; no key/secret constructor arguments. Reuse Nautilus Spot instrument precision/model reference instead of custom exchange semantics. Market adapter has explicit sandbox base URL, timeout and read-only endpoint allowlist.

Add versioned immutable Trade/Candle/BookDelta/InstrumentMetadata payload contracts. Exchange timestamps originate as integer milliseconds and normalize to explicit UTC; financial values remain decimal strings. Quantity/price conversions respect versioned tick/step/min-notional metadata.

A deterministic monitor tracks per-symbol stream sequence and exchange time, receipt time, warmup, last good observation and gap state. Duplicate ID with different bytes is rejected; exact duplicates never refresh market freshness. Stale/future-skewed data cannot restore healthy state. Gaps require recorded contiguous backfill or explicit verified resynchronization evidence, not an unconditional healthy flag. Book deltas require snapshot sequence alignment.

Historical ingestion writes raw/versioned source artifact plus content hash/config metadata to S3 through a mature client; analytical records go to ClickHouse through its approved client/API. Watermarks and manifest metadata live in PostgreSQL. Delivery is idempotent by venue/symbol/record ID and version; failures retain retryable checkpoints and degraded health. ClickHouse merge semantics alone do not establish financial uniqueness; these records confer no execution authority. EventStore expansion uses an explicit producer payload registry, validated provenance/content hash and immutable database event identity; no arbitrary dict payloads.

## Files and ownership
packages/contracts: market payloads/schema exports. services/market-data and shared Python market package: read-only adapters/monitor. infra/migrations: manifest/watermark state. infra/data config: ClickHouse and S3 integrations. tests/market-data: fixtures, negative data cases, actual ClickHouse/S3/PostgreSQL/NATS persistence/restart tests. docs/evidence/program: observed results and limits.

## Dependencies and licensing
Official binance-sdk-spot 3.0.0 and binance-common 3.2.0 already inspected in isolated spike (MIT); integrate into a dedicated market worker or verify root dependency compatibility before merging. NautilusTrader 1.221.0 LGPL unmodified dynamic model/simulation dependency, not approved native live submission. Mature ClickHouse client and S3 client exact pins/license metadata/lock required before use. Server digests/licenses from Phase 0.5; no assumed CVE clearance. Dataset redistribution/venue rate terms must be respected; no credential/account data in artifacts.

## Failure modes
HTTP/WS outage, stale/future timestamps, sequence gaps, duplicate/conflicting records, invalid venue filters, unknown symbol, DB/broker/ClickHouse/S3 outage and restart. Preserve source/watermark evidence; degrade health; never manufacture new market observations. Risk reduction availability remains deterministic execution work, not a reason to falsely mark data healthy. Historical ingestion is bounded with explicit rate/time limits.

## Security and financial-risk impact
Read-only capability above financial boundary; never shares execution credentials. External payloads parsed into typed records; arbitrary prompt-like text cannot become policy. No anonymous S3/trust DB production deployment; disposable fixtures stay isolated. Source/tenant provenance required. SDK raw signed methods never exposed as agent tools. No fixture establishes venue certification.

## Data/event migrations
Additive V1 normalized schema and initial manifest/watermarks. Existing HealthChange payload compatible. Explicit event registry extensions and schema hashes; breaking formats new version. Replays idempotent; preserve raw source artifacts and stable parser version. Rollback reader version with old schema support; never erase source history.

## Implementation steps
- [x] Read specifications/adoption evidence and define phase boundaries.
- [ ] Lock read-only SDK/data clients and prove dependency/license compatibility.
- [ ] Implement typed normalized payloads and deterministic freshness/gap monitor.
- [ ] Implement narrow public/sandbox reads and metadata/stream alignment.
- [ ] Add historical manifests, ClickHouse analytical writes and S3 source artifacts.
- [ ] Test real local persistence/restart/outage and malformed/stale/gapped fixtures.
- [ ] Adversarial self-review, repair, record evidence, publish and proceed Phase 3.

## Test plan
make check; new market unit/contract cases for float/nonfinite/precision rejection, IDs/UTC, stale/future times, conflicting duplicates, warmup and gap/backfill/snapshot alignment. Extend make integration with exact-digest ClickHouse/SeaweedFS alongside PostgreSQL/NATS; verify real fixture PUT/GET/hash, analytical queries, replay, watermark restart and storage failures. A supported public/sandbox read, if reachable, is recorded separately from local fixtures; never fabricate continuous elapsed-market evidence. No signed endpoint calls.

## Acceptance criteria
Typed normalized reads and historical ingestion run through real local data-store integrations; monitoring fails closed on stale/gapped/unknown data; idempotent restart and source lineage evidence pass. SDK/client adoption documented; no live credential/order path. CI equivalent checks PASS. L0 remains until actual certification phase evidence.

## Rollback/recovery
Stop ingestion, preserve source artifacts and manifests, revert parser/writer version. Replay from committed watermarks with immutable source history and dedup keys. Do not delete historical data to conceal gaps or failed tests. Test fixtures are disposable only.

## Resume checkpoint
Branch codex/enterprise-local-autonomous. Last durable implementation commit 8de8c80231f91208529c82d29f49d7c1c76327fc. Current step: plan/adoption design complete, implementation not started. Next exact action: integrate the narrow SDK dependency/client contract, then implement market payloads and freshness/gap tests before changing EventStore registry. Uncommitted: this plan and CI/status evidence. Blockers: none. Usage state: active; no allowance-reset claim. Verification: Phase 1 local static/unit/integration/build/runtime smoke PASS and hosted CI PASS.

## Progress log
2026-10-02: Phase 1 published/CI verified; Phase 2 design and dependency boundaries established. No market observation claimed.

## Decisions
Real-time readiness requires observed freshness and verified sequence alignment, not successful parsing or store reachability. Keep SDK credentials unavailable to market worker. Preserve immutable raw source lineage so parser changes remain reproducible.

## Completion summary
Pending implementation; do not mark Phase 2 delivered based on this plan.
