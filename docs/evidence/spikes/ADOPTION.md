# Initial foundation adoption decisions

These are compatibility decisions at L0, not production certification. Exact Python hashes are in `infra/spikes/python/uv.lock`; image digests are in the platform probe. Raw observations and exact-tag license hashes are adjacent JSON files.

| Foundation | Pin | License observed | Decision / boundary |
| --- | --- | --- | --- |
| NautilusTrader | 1.221.0 | LGPL-3.0-or-later (packaged) | Adopt unmodified dynamic dependency for simulation/instrument models. Defer its live Binance submission client until UNKNOWN fault tests; failed submission currently may emit REJECTED. Do not trust its state as our accounting authority. |
| Binance official modular SDK | binance-sdk-spot 3.0.0 / binance-common 3.2.0 | MIT metadata; Spot license packaged | Adopt venue-native API/reference behind execution/reconciliation adapters. Disable retry on submission; timeout ambiguity reconciles by stable client ID. No agent gets SDK capability. |
| PostgreSQL | 17.6-bookworm + digest | PostgreSQL License | Operational state and durable append-only journals; NUMERIC(38,18), unique delivery keys, transactional outbox. Our later migrations/roles must enforce immutability and tenancy. |
| NATS | 2.11.8-alpine + digest | Apache-2.0 | JetStream durable streams/explicit acknowledgments; bounded retries and database inbox idempotency. No exactly-once claim. |
| OPA | 1.8.0 + digest | Apache-2.0 | Rego v1 with fail-closed authorization wrapper and dedicated reduction/cancel policies. Never substitute a custom policy evaluator. |
| OpenBao | 2.3.2 + digest | MPL-2.0 | Local secret API isolated service. Spike stays uninitialized/sealed. Production TLS/init/unseal and local owner secrets are owner-controlled; no dev-root token pattern. |
| ClickHouse | 25.8.3.66 + digest | Apache-2.0 | Market/analytical storage only. Never financial journal or authorization authority. |
| MLflow | 3.4.0 + digest | Apache-2.0 | Research registry/tracking. Our promotion authority validates immutable evidence independently. Spike file backend does not establish PostgreSQL/S3 production support. |
| SeaweedFS | 3.97 + digest | Apache-2.0 | S3-compatible object store candidate with content hashes/versioned keys. Selected over embedding AGPL MinIO without review. Anonymous disposable probe settings must never become production settings. |

## License and security boundaries

Packaged/upstream license files were inspected and hashed, not inferred solely from product names. Nautilus LGPL remains replaceable via normal Python loading; preserve license/source notices and allow dependency replacement, including debugging modifications. Do not vendor, statically link or modify it into proprietary core. Before binary redistribution, verify combined-work source/installation requirements and transitive notices. Current public application source and isolated wheel dependency keep a safe development default; no legal completion claim.

OpenBao MPL obligations attach to covered files; run the unmodified server as a separate process/image. Apache/MIT/PostgreSQL notices remain with deployed distributions. Transitive Python dependencies are hash-locked; packaged versions can differ from core (Pydantic 2.13.5 in the isolated spike vs 2.12.3 core), so do not silently merge environments. SBOM, CVE scan and runtime least privilege remain mandatory Phase 14 work. None of these dated pins establishes ongoing vulnerability clearance.

## Compatibility limits and next tests

Offline fixture/import checks establish Python 3.12 compatibility and API presence, not real venue behavior. No exchange call occurred. Nautilus native submission is not presently cleared for live adoption. Phase 5 must inject accepted-then-timeout, no order found, duplicate deliveries, partial fills, restart and filter drift before selecting a live wrapper. A possible resolution is official SDK submission behind our deterministic request/UNKNOWN state machine, while retaining Nautilus simulation; do not rebuild a simulator.

Platform probes establish local APIs and a PostgreSQL exact-decimal restart. NATS durable consumer replay, production database migration/recovery, authenticated S3, production MLflow backend, TLS and OpenBao operational initialization are later phase gates. Probe resources are disposable and cleaned automatically.
