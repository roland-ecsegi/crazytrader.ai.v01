# Validation Log

## 2026-10-02 — Documentation / architecture audit

Scope:
- complete product discussion requirements;
- every repository file on main;
- merged PR #1 and PR #3;
- Master Goal issue #4;
- official Codex Goal/usage behavior;
- current Claude subscription/CLI/Agent-SDK operating model at a high level.

Result: PASS AFTER HARDENING CHANGES.

Corrections:
- removed Phase 0 autonomous-stop contradiction;
- clarified autonomous gate reviews;
- made actual L6 evidence the completion condition;
- added risk-reduction path invariant;
- isolated live secrets from Codex Cloud;
- strengthened Math/Strategy semantics;
- added lifecycle/capital/open-source/resume specs;
- strengthened agent memory/prompt-injection governance;
- moved recovery/runbooks before final live certification;
- documented Codex budget auto-resume limitation truthfully.

Implementation tests: not applicable yet (L0).

## 2026-10-02 — Phase 0 bootstrap gate

PASS. `UV_CACHE_DIR=/tmp/crazytrader-uv-cache make check`: 43 tests; Ruff lint/format; strict mypy (3 modules); 22 validation/serialization schema drift checks; baseline source secret scan. `uv build --out-dir /tmp/crazytrader-build`: wheel/sdist PASS. All eleven required typed foundations included. No network/venue submission code. Adversarial self-review found and repaired decimal notation mismatches, numeric timestamp coercion, zero horizon and event registry construction. Full scanner/SBOM integration remains Phase 14; event producer payload resolution/integrity is not implemented. CI defines equivalent checks; remote execution not yet observed. L0 retained.

## 2026-10-02 — Phase 0.5 compatibility/license gate

PASS with explicit boundaries. `infra/spikes/python/.venv/bin/python infra/spikes/python/compatibility.py`: pinned Nautilus 1.221.0/official Binance Spot SDK 3.0.0 + common 3.2.0 offline precision/ID/API checks PASS (no venue calls). Source inspection found submit-failure REJECTED semantics: live Nautilus adapter adoption deferred until Phase 5 UNKNOWN/fault proof. `python infra/spikes/platform_probe.py`: PostgreSQL exact decimal after restart; NATS JetStream; OPA false eval; OpenBao sealed/uninitialized; ClickHouse decimal query; MLflow fixture run/parameter; SeaweedFS S3 PUT/GET PASS, resources cleaned. `python infra/spikes/license_probe.py`: exact-tag upstream licenses hashed PASS. Probe failures were script/module naming, entrypoint and inherited proxy routing; repaired using narrow internal exclusions, no disabled TLS. Production auth/TLS, consumer replay, MLflow PostgreSQL/S3 and secret initialization remain later gates. L0 retained.

## 2026-10-02 — Phase 1 backbone gate

PASS. `make check`: 44 unit/contract tests, 8 real-dependency tests intentionally skipped in this command; lint/format, strict mypy (10 modules), 24 schema drift checks and baseline source scan pass. `make integration`: 9 tests pass (API test plus 8 real PostgreSQL/NATS tests); exact-digest loopback fixtures removed. Covers changed-content ID denial, atomic outbox, audit inbox, UPDATE/DELETE/TRUNCATE protection, broker failure retention, ACK-before-marker crash, unacked durable consumer restart, bounded notification failure/recovery and fresh/stale worker readiness. `docker build` with ephemeral CA: actual hash-locked non-root image PASS. `python scripts/platform_smoke.py`: actual Compose migration, UID10001, auth, all worker readiness, audit stop ->503 and restart ->200 PASS; random platform credentials never recorded; fixtures/volumes removed. `uv build`: wheel/sdist PASS. Self-review repaired stalled-worker blindness, copied source permissions and internal-network ingress isolation. Production restricted SQL/NATS roles/TLS, external alert adapters, operational replay/backup/trace exporters remain later gates. L0, no orders/secret endpoints. Remote CI pending observation.

## 2026-10-02 — Hosted CI checkpoint verification

Phase 1 commit 8de8c80231f91208529c82d29f49d7c1c76327fc, run 37068956651/job 111043565024: PASS for setup/check and real dependency integration. Phase 0 commit b610027 hosted CI also PASS. Phase 0.5 run 37066810615 failed solely Ruff formatting in platform_probe.py after a late local proxy fix; this formatting was repaired in Phase 1 and current hosted checks include the corrected file. No runtime/license/contract failure hidden. Phase 2 plan created; market implementation/observation still pending.

## 2026-10-03 — Phase 2 market/data local gate

PASS. `make check integration`: 63 unit/contract tests, 10 dependency tests skipped
only in unit command; separate actual platform integration 9 PASS and market
integration 2 PASS. Ruff/static mypy18 modules, 36 schema artifacts, source scan
and isolated official SDK offline roundtrip/unsigned GET signatures PASS.
`uv build`: wheel/sdist PASS. Actual public three-operation metadata/trade/depth
read normalization evidence recorded in phase-2-public-read.json. Real fixtures
verify S3 PUT/GET/hash lineage, ClickHouse logical dedup/restart, PostgreSQL
immutable old-ID conflicts, source manifests, failed projection retry/no cursor
advance, missing watermark range denial, worker checkpoint restart, typed market
event audit idempotency. Self-review repairs: full Decimal context; SDK generated
union to_dict; post-storage freshness check; old duplicate conflicts; complete
history recovery; symbol writer serialization. Fixture-only anonymous S3 and
loopback trust DB are not production auth/TLS evidence. Bounded REST fallback,
no websocket/elapsed paper/live claim. L0 retained. Continue Phase 3.

## 2026-10-03 — Phase 3 accounting local gate

PASS. `make check integration`: 73 unit tests (subsequent unchecked-copy regression
adds1, standalone ledger unit11 PASS), 18 dependency skips only in unit command;
actual platform/ledger17 PASS (8 ledger +8 platform +API), market2 PASS. Ruff,
strict mypy23 modules, 46 schema artifacts, source scan and SDK offline PASS.
Wheel/sdist PASS. Real SQL tests cover tenant/mode ownership, high-precision history,
concurrent80+80 reservations against100 (one denied), partial/over/wrong-order release,
changed transaction/source/fill IDs, exact base/quote/BNB fees, SELL inventory reservation,
SQL UPDATE/DELETE/TRUNCATE denial, no-posting/unbalanced/negative direct SQL,
late posting rejection, one full compensation and audit idempotency. Rational cost
view reconstructs costs/P&L; unknown BNB quote fee value yields null P&L. Shared
producer and ledger handler revalidate unchecked model-copy input. SQL journal,
artifact, event and outbox commit atomically. Live venue ingestion/mismatch handling,
production roles and trading authorization remain later gates. L0 retained.
Mandatory pre-T012 architecture/security pass recorded; continue Phase4.

Phase2 hosted run37109997716 PASS, implementation866efded6d3d5e4778d2f17a1b2f0bc446bb7a5d.

## 2026-10-03 — Phase4 evaluator/OPA milestone (not phase gate)

29 deterministic cases PASS; actual OPA HTTP and image-derived SHA-pinned local
OPA36 tests PASS. Permission/symbol/expiry denies, strict malformed-reply denial,
forged ALLOW rejection, explicit degraded reduction, no offline increasing risk,
owner-disabled local fallback and HTTP outage verified. Owner/system cap minima,
unknown exposure/P&L, stale/future state, unavailable price, no-short pending SELL,
L0/L5 LIVE denial and conservative step conversion tested. Cancellation/state-loader/
audit persistence remain next tasks. No order capability or elapsed certification.
Phase3 hosted CI37111641894 PASS atca085cd33135bd337b5b79de27d1bbf5aa11f17a.


## 2026-10-03 — Phase4 gate and Phase5 coordination milestone
Phase4 gate PASS:109 units, actual OPA38, actual platform/ledger17 and actual
market/risk13, mypy31,76 schemas, source scan and wheel/sdist. Published722a914;
hosted CI37116292477 PASS. Review/source expiry/accounting/config activation/
terminal replay repairs in evidence. L0 remains, no external blocker.
Phase5 milestone PASS (not phase gate):114 units, mypy35,82 schemas, SDK offline,
source scan, wheel/sdist; actual OPA+market/risk/execution17 (4 execution), actual
platform/ledger17. Concurrent replay/claim gives one reservation and one claim;
restart SUBMITTING -> UNKNOWN, no resend; atomic audit-failure rollback; expired/
changed account/config/evidence denied. No transport or reconciliation yet.


## 2026-10-03 — Phase5 official SDK UNKNOWN recovery milestone
115 units, mypy38,84 schemas, scan/offline SDK and build PASS. Actual combined
market/risk/execution/SDK22 PASS: signed dummy-auth POST commits fixture order before
timeout -> UNKNOWN; zero retries; restarted SDK query finds stable ID; query-only
recovery -> ACKNOWLEDGED; not-found remains unresolved, funds reserved; crash after
accepted response/before local receipt persistence gives one total submission.
Exact decimal string wire proof PASS despite generated SDK float annotations.
Parent/child reject non-literal-loopback endpoints and real-money modes, strip
credentials, use fixed dummy auth; redirects disabled. No production simulator,
real Binance credentials/orders, L4 observation or complete Phase5 claim.
Coordination7cdc0c6 hosted CI37117415054 PASS. Pre-T016 review recorded.


## 2026-10-03 — Native financial and unsent expiry milestones
Native registry cf91a168 hosted CI37140085947 PASS; native source84c74699 and modeled
funding61a7ebd3 hosted CI37136414359/37134720320 PASS. Native financial3d28318b:69 full
actual cases PASS (234.94s), final13 native PASS (27.88s),17 platform/ledger PASS (7.50s),
164 units/mypy51/128 schemas/scan/offline SDK/wheel-sdist PASS. Source-bound native cash
and fee, atomic journal/FILLED/proof, duplicate/crash recovery, critical incident latch.
Unsent expiry2c820edc:7 actual PASS (6.10s),36 affected cases PASS (98.62s),17 platform/
ledger PASS (6.79s),169 units/mypy53/130 schemas/scan/offline SDK/wheel-sdist PASS. Exact
original custody, owned no-dispatch proof, unknown retention, claim race/audit rollback.
L0/no Phase5 gate.

## 2026-10-03 — Bounded fixture absence source assessment
Full83 passes (285.88s) with one invalid fixture identifier; repaired final8 cases PASS
(34.99s),175 units/mypy55/134 schemas/scan/offline SDK/build PASS,17 platform/ledger
PASS (6.27s). Strict signed HTTP lookup, complete bounded account/history, stable
source/head, SQL source binding, raw-before-audit recovery. No financial effect.
SDK/native pending-state fences unified. Original send/late-acceptance fence required
before release/retry. Native financial CI37141145082 and expiry CI37142039091 PASS.
L0/no Phase5 gate.
