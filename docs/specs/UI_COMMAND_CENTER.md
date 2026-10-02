# Custom Command Center UI V1

The user-facing product is custom; do not expose Grafana/Hummingbot/Freqtrade as the primary UI.

## Dashboard

Show:
- total portfolio;
- per-mode capital/P&L/drawdown;
- Math Mode status and Auto Trading ON/OFF;
- Strategy Mode status, Low/Medium/High selection and Auto Trading ON/OFF;
- open orders/positions;
- system/exchange/data/reconciliation health;
- current certification level;
- active incidents;
- Global Kill.

## Agent pages

For each permanent agent:
- stable identity/role;
- status/current task;
- provider/model selection;
- skills;
- permission summary;
- memory/experience metadata;
- performance/audit history;
- provider usage/error state.

Do not expose raw secrets or unrestricted shell/tool controls.

## Research pages

Experiments, candidates, lifecycle stage, validation metrics/evidence, promotions/suspensions and model/strategy lineage.

## Risk/operations

Owner-configurable hard caps through audited workflow, kill-switch hierarchy, incidents, reconciliation status, backup/restore health and runbook links.

## Safety UX

- destructive/emergency actions require clear confirmation where latency permits;
- Global Kill remains quickly accessible;
- live activation visibly displays certification and capital cap;
- UI cannot bypass backend risk/policy.
