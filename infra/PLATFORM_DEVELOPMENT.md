# Development backbone deployment

This is L0 development, not a live trading deployment. No exchange/Claude/OpenBao bootstrap secrets are needed.

Build `crazytrader-platform:phase1` using `infra/Dockerfile.platform` and a BuildKit `proxy_ca` secret containing the trusted system CA bundle. In a managed environment:

```sh
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -f infra/Dockerfile.platform -t crazytrader-platform:phase1 .
```

Preserve configured Docker registry/proxy settings. This build uses pinned Python base digest, uv 0.12.19 and hash-locked runtime dependencies. The CA secret is not copied into image layers. The app runs as UID 10001 with a read-only filesystem under Compose.

On your local machine, configure `CT_POSTGRES_PASSWORD`, `CT_DATABASE_DSN` (PostgreSQL user/database `crazytrader`, host `postgres` on the Compose network) and `CT_OWNER_TOKEN` (at least 32 random characters). Keep them in an untracked environment/secret-manager workflow. URI-encode passwords in the DSN. These are development platform credentials; never put Binance live keys, Claude auth or OpenBao bootstrap material in this environment.

```sh
docker compose -f infra/compose.platform.yml up -d postgres nats
docker compose -f infra/compose.platform.yml run --rm migrate
docker compose -f infra/compose.platform.yml up -d outbox audit notification control-api
```

Only the control API publishes a port, bound to loopback. All platform stores are on an internal network; only the control API also attaches to a separate ingress network. API worker binding to `0.0.0.0` is container-local; authenticated requests use `http://127.0.0.1:8080`. Do not expose this development stack to WAN or enable live capital. NATS service authentication/TLS and least-privilege SQL roles are still Phase 14 work.

`/ready` becomes healthy after all three workers heartbeat. Stop any worker to verify degraded readiness after five seconds. `/certification` always reports L0/development/live disabled. Alerts currently deliver to local notification process logs with stable event identifiers. Protect log access. Failures/exhausted delivery remain visible in readiness and `ct_notifications`.

Stopping processes retains Compose named volumes. Do not use `down -v` on durable state. Replay/correction operations need an audited operations workflow before production. Upgrades must run explicit migrations and preserve append-only history. No backup/restore or live recovery readiness is claimed by this phase.
