# Program Decisions

## 2026-10-02 — Full architecture audit

- Enterprise Local completion means **L6 LIVE CERTIFIED**, not merely code-complete.
- Codex Cloud never receives live Binance credentials or owner-local Claude authentication material.
- Math Mode authoritative live decisions remain quantitative/statistical.
- Risk controls distinguish risk-increasing from risk-reducing actions.
- No fixed monthly return/minimum trade count is a system success requirement.
- Autonomous phase gates use mandatory adversarial review but do not require routine human approval.
- An early open-source compatibility/license spike is mandatory before rebuilding mature infrastructure.
- Current Codex Goals auto-continue only while active/within budget; budget-limit auto-resume cannot be guaranteed by repository code, so the project uses durable checkpoint/resume protocol.
- Final live canary runs on the owner-controlled local deployment, not Codex Cloud.

## 2026-10-02 — Phase 0 tooling/contracts

Python 3.12 with uv 0.12.19 and hash-locked dependencies; Pydantic frozen/extra-forbidden V1 contracts. Financial strings reject binary floats/nonfinite/excess precision and ambiguous sizing. Evidence-backed event payload references prevent mutable opaque financial payloads; producer schemas/resolution follow in service phases. UI TypeScript tooling deferred to Phase 13; directories are explicit ownership reservations. Validation is not financial authority or certification evidence verification.

## 2026-10-02 — Open-source adoption gate

See docs/evidence/spikes/ADOPTION.md and exact version/license hashes. Use Nautilus unmodified dynamic dependency for simulation; defer native live submission until UNKNOWN recovery fault proof. Official Binance modular SDK remains venue reference behind deterministic boundary. SeaweedFS Apache-2.0 S3 candidate avoids embedding AGPL object-store core. No secret/bootstrap material used. GitHub connector can publish atomic trees/commits and fast-forward branch when shell Git lacks write credentials.

## 2026-10-02 — Platform durability/readiness

PostgreSQL is canonical immutable event/audit state with transactional outbox and inbox. NATS file JetStream is at-least-once transport, not an exactly-once ledger. Notification failures persist bounded attempts; only local console delivery exists so far. Readiness requires fresh audit/outbox/notification heartbeats, not only reachable stores. Explicit admin migration separated from ordinary worker startup. App UID10001/read-only Compose with API-only ingress and loopback binding; data network internal. Development role/auth settings are not production security certification.
