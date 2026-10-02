# Enterprise Local Deployment V1

## Target

Owner-controlled private Linux host or equivalent secure machine.

Initial orchestration: containers with Docker Compose/equivalent. Kubernetes deferred to SaaS unless a local operational requirement justifies it.

## Network zones

At minimum separate:
- UI/control ingress;
- application services;
- data stores;
- secret/policy services;
- exchange egress.

PostgreSQL, ClickHouse, NATS, OpenBao and OPA should not be directly exposed to WAN.

## Secrets

Owner initializes/unseals/configures OpenBao locally. Codex Cloud never receives unseal/bootstrap material.

Binance live secret is entered locally only. Claude subscription login is also local.

## Persistence

Durable volumes/backups for PostgreSQL, required ClickHouse data, object store, MLflow metadata/artifacts, OpenBao state/config where appropriate, audit and configuration.

## Recovery

Document and test:
- clean restart;
- power-loss restart;
- backup restore;
- NATS replay;
- exchange reconciliation;
- unknown-order recovery;
- secret-store unavailable mode;
- upgrade rollback.

## Observability

OpenTelemetry + Prometheus baseline. Internal dashboarding may use Grafana after license review, but the product UI remains custom.

Monitor technical health plus P&L, drawdown, exposure, slippage, order rejects, unknown states, reconciliation mismatches, stale data, model/strategy degradation, agent/provider failures and risk denials.
