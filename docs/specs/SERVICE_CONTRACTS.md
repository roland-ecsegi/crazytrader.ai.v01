# Service Contracts V1

## Purpose

This document defines service responsibilities and prohibited cross-boundary behavior.

## control-api

Owns:

- owner commands;
- configuration API;
- system health presentation;
- agent controls;
- trading-mode controls;
- certification status;
- emergency commands.

Must not:

- store Binance secrets;
- submit exchange orders directly;
- calculate authoritative risk decisions.

## agent-runtime

Owns:

- permanent agent identity;
- task lifecycle;
- skill invocation;
- tool permission checks;
- memory access;
- agent health and state.

Publishes:

- AgentTaskStarted
- AgentTaskCompleted
- AgentTaskFailed
- AgentAvailabilityChanged

Must not:

- directly access Binance live credentials;
- bypass TradeIntent;
- self-modify hard risk or OPA policy.

## ai-gateway

Owns:

- Claude CLI adapter;
- Claude API adapter;
- future provider adapters;
- per-agent provider/model selection;
- fallback policy;
- AI usage telemetry;
- normalized AI response envelope.

Must not:

- become a required dependency for protective open-position logic.

## market-data

Owns:

- Binance market streams;
- REST fallback;
- freshness checks;
- sequence/gap detection;
- normalized market events.

Must publish stale/gap status.

## math-engine

Owns:

- quantitative features;
- validated quantitative models;
- expected value;
- transaction-cost-aware edge;
- Math Mode proposal generation.

Must produce structured evidence with every TradeIntent.

## strategy-engine

Owns:

- strategy registry;
- immutable strategy versions;
- regime eligibility;
- strategy scoring;
- Low/Medium/High profile mapping;
- Strategy Mode proposal generation.

## portfolio-engine

Owns:

- capital allocation;
- exposure summary;
- strategy budgets;
- Math vs Strategy budget;
- cash reserve;
- capital growth proposals.

It may propose higher allocation but may not exceed owner hard limits.

## risk-engine

Owns deterministic risk evaluation.

Inputs:

- TradeIntent;
- portfolio state;
- market state;
- exchange health;
- reconciliation health;
- risk profile;
- risk_effect (increasing/reducing/neutral);
- hard owner limits.

Output:

- RiskDecision with allow/deny, reason codes, calculated exposure, risk direction, degraded-mode permissions, and rule evidence.

Critical rule: unhealthy/unknown state denies new/increased risk by default but must not unintentionally block an authorized cancellation or exposure-reduction path.

## policy-engine

Implementation target: OPA.

Inputs:

- actor;
- action;
- resource;
- environment;
- certification level;
- risk decision;
- system state.

Output:

- allow or deny;
- policy reason codes.

## execution

Owns:

- approved execution planning;
- client order identifiers;
- order submission;
- order state machine;
- idempotency;
- partial fills;
- cancellation;
- exchange error normalization.

Must accept only fully authorized execution requests.

For live credentials, execution obtains a secret reference only from the owner-controlled local secret manager. Codex Cloud and agent/LLM contexts never receive raw live credentials.

## reconciliation

Owns comparison between:

- internal orders;
- internal fills;
- Binance orders;
- Binance fills;
- balances;
- reservations.

Critical mismatch must block new/increased risk while preserving safe cancellation/risk reduction where policy and venue state allow.

## ledger

Owns append-only internal financial journal.

No service may rewrite historical ledger entries in place.

Corrections are compensating entries with explicit reason.

## research

Owns:

- experiments;
- backtests;
- feature research;
- model training;
- strategy candidates;
- validation workflows.

Must remain isolated from live execution authority.

## audit

Owns durable audit events for:

- owner actions;
- agent actions;
- policy decisions;
- risk decisions;
- promotions;
- execution;
- security changes;
- incidents.

## notification

Owns delivery of alerts.

Alert delivery failure must itself be observable.
