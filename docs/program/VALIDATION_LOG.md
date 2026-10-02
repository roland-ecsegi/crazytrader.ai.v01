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
