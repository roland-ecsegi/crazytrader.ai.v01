# ExecPlan Standard

## Purpose

ExecPlans are mandatory for substantial Codex work in CrazyTrader.ai.

An ExecPlan is a living implementation document that allows another agent or engineer to understand what is being changed, why, how it will be tested, and what remains incomplete.

## When an ExecPlan is required

Create an ExecPlan for:

- a new service;
- a new agent;
- a new financial state machine;
- a change to TradeIntent;
- database schema changes;
- NATS event schema changes;
- risk changes;
- OPA policy changes;
- execution changes;
- Binance integration;
- security architecture changes;
- cross-service refactoring;
- roadmap work expected to require multiple commits.

## ExecPlan location

Store plans under:

    docs/plans/

Use:

    YYYY-MM-DD-short-title.md

## Required structure

# Title

## Goal

State the concrete outcome.

## Non-goals

List what is explicitly excluded.

## Architecture context

Reference the architecture/specification sections that constrain the work.

## Current state

Describe what exists before the task.

## Proposed design

Describe components, boundaries, public contracts, and data flow.

## Files and ownership

List directories/files expected to change.

## Dependencies

List blocking tasks, external dependencies, and required infrastructure.

## Failure modes

Describe failures and required safe behavior.

## Security and financial-risk impact

Explicitly state whether the task is above or below the financial trust boundary.

If below it, include negative-path tests and recovery tests.

## Data migrations

Describe any schema/event migrations and backward compatibility.

## Implementation steps

Use a checkbox list with small, verifiable steps.

## Test plan

Specify exact tests, not only broad categories.

## Acceptance criteria

List objective pass/fail conditions.

## Rollback

Describe how to revert the change safely.

## Progress log

Append dated progress updates during execution.

## Decisions

Record decisions that would otherwise be rediscovered later.

## Completion summary

When complete, record what shipped, what remains, and any follow-up work.

## Rule

An ExecPlan may evolve during implementation, but safety constraints and acceptance criteria may not be weakened merely to make tests pass.
