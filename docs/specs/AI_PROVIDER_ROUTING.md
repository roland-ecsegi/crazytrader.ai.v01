# AI Provider Routing V1

## Goal

The AI provider must be replaceable without changing permanent agent identity or financial-control logic.

## Provider architecture

    Permanent Agent
          |
          v
       AI Gateway
          |
          +--> Claude CLI Adapter
          |
          +--> Claude API Adapter
          |
          +--> Future Provider Adapter

## Agent identity rule

Agent identity is independent from:

- provider;
- model;
- reasoning mode;
- transport;
- subscription or API path.

Changing the model must not create a new agent or discard its governed memory/history.

## Enterprise Local

Enterprise Local may use Claude CLI through the owner's authenticated local Claude Code environment.

The adapter must:

- call the CLI through a controlled process boundary;
- enforce timeout;
- capture normalized output;
- capture normalized failure state;
- avoid placing secrets in prompts;
- record provider/model metadata;
- support cancellation;
- prevent shell capability from becoming exchange authority.

## Claude API

The API adapter is optional in early Enterprise Local and becomes important for future SaaS.

It must support:

- configured model selection;
- usage tracking;
- retry policy;
- timeout policy;
- error normalization;
- fallback policy;
- tenant attribution in future SaaS.

## Provider fallback

Fallback must be explicit and auditable.

A provider timeout may allow another provider to complete a research/advisory task.

A provider fallback must never duplicate a financial action.

TradeIntent identity and execution idempotency remain outside the AI provider layer.

## Required normalized response envelope

- request_id
- agent_id
- provider
- model
- started_at
- completed_at
- status
- structured_output when requested
- usage metadata when available
- tool_calls
- error_class
- trace_id

## Safety

Claude or another AI provider must not be required for:

- hard risk;
- OPA policy decisions;
- kill switch;
- reconciliation;
- duplicate-order prevention;
- emergency open-position handling;
- internal ledger integrity.

## Model configuration

A per-agent configuration may specify:

- primary provider;
- primary model;
- reasoning level;
- maximum response budget;
- timeout;
- fallback sequence;
- tool allowlist;
- task categories.

## Future SaaS

Commercial operation should move toward centrally governed API routing with:

- per-tenant quotas;
- cost attribution;
- provider policies;
- rate limiting;
- audit;
- billing integration.

CLI support can remain a private/local execution option where appropriate.
