# ADR-0002 — Agent Identity Is Independent of AI Model

Status: Accepted

## Context

Permanent agents must accumulate governed experience and maintain stable responsibilities over time.

AI providers and models will change.

## Decision

A permanent agent is a platform entity with stable identity, permissions, memory, skills, performance history, and audit history.

Claude Opus, Claude Sonnet, Claude CLI, Claude API, or another future provider are execution resources used by the agent.

Changing provider or model does not create a new agent.

## Consequences

- memory and experience remain attached to the agent;
- provider choice can be changed per task;
- model upgrades do not erase agent history;
- SaaS can later enforce per-tenant provider policies;
- AI Gateway becomes an important abstraction boundary.
