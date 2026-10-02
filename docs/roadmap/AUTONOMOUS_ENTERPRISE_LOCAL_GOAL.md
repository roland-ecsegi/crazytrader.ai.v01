# Autonomous Enterprise Local Master Goal

## Goal

Take CrazyTrader.ai from the current repository state to a complete Enterprise Local product with all planned local/private functionality implemented, tested, documented, and operationally ready.

The work should proceed autonomously in Codex Cloud with minimal owner involvement.

The owner should only be contacted when a true external blocker prevents safe continuation.

## End state

The target end state is Enterprise Local, not Enterprise SaaS.

Enterprise Local includes:

- single owner / single tenant;
- local/private deployment;
- complete Math Mode;
- complete Strategy Mode;
- Low / Medium / High risk profiles;
- permanent agents with stable identity, real skills, governed memory, permissions, and audit history;
- Claude CLI adapter;
- Claude API adapter capability;
- AI Gateway;
- autonomous research;
- controlled learning;
- strategy/model lifecycle;
- Capital Growth Engine;
- Binance Spot integration;
- deterministic Hard Risk Engine;
- OPA policy layer;
- execution engine;
- reconciliation;
- append-only ledger;
- OpenBao-based secret architecture;
- NATS JetStream;
- PostgreSQL;
- ClickHouse;
- object storage;
- MLflow;
- observability;
- backups/recovery;
- Command Center UI;
- backtest;
- simulation;
- paper trading;
- shadow mode;
- canary capability;
- live-certification workflow;
- Enterprise Local operational runbooks.

Enterprise SaaS is explicitly out of scope for this Master Goal.

## Autonomous operating contract

Codex should work continuously toward the end state.

Do not stop for:

- routine implementation choices;
- ordinary dependency choices covered by repository rules;
- passing phase transitions;
- non-critical refactors;
- status updates;
- permission to continue after tests pass;
- permission to create the next ExecPlan.

For each phase:

1. inspect repository and current program status;
2. read the relevant architecture/specs;
3. create or update the phase ExecPlan;
4. implement;
5. test;
6. self-review;
7. run security/failure tests appropriate to the phase;
8. fix defects;
9. update docs;
10. record evidence;
11. commit and push durable progress;
12. advance to the next phase.

## Durable program memory

Maintain:

- docs/program/STATUS.md
- docs/program/DECISIONS.md
- docs/program/KNOWN_ISSUES.md
- docs/program/VALIDATION_LOG.md

These files are the durable continuation state if a Codex Cloud task is resumed or restarted.

STATUS.md must always contain:

- current phase;
- completed phases;
- next action;
- current blockers;
- latest verification commands/results;
- relevant commit SHA;
- certification level.

## Git strategy

Use a long-running branch for the autonomous program unless the environment imposes another safe workflow.

Preferred branch:

    codex/enterprise-local-autonomous

Commit at meaningful milestones and at every phase gate.

Push progress often enough that a lost cloud workspace does not lose significant work.

Do not rewrite published history unless required for recovery.

## Quality policy

Never advance because implementation merely appears complete.

Every phase must have objective evidence.

If tests reveal architectural weakness, repair the implementation before advancing.

If a contract must change, update specifications and migration paths.

## Self-audit policy

At each major gate, perform an adversarial self-review.

Specifically inspect:

- architecture drift;
- security bypasses;
- accidental direct exchange access;
- secret leakage;
- duplicate-order risk;
- idempotency;
- unknown-state recovery;
- ledger integrity;
- event replay behavior;
- stale market data;
- risk bypasses;
- policy bypasses;
- certification bypasses;
- agent privilege creep;
- unvalidated model/strategy promotion;
- dependency licensing.

## Research behavior

Codex may research current public technical documentation when needed to implement dependencies correctly.

Prefer official upstream documentation and repositories.

Record material dependency decisions in docs/program/DECISIONS.md.

## Blocker policy

A true blocker requires owner input or external action.

Valid examples:

- Codex Cloud environment lacks required permission;
- GitHub access fails;
- an external account must be authenticated;
- a secret must be entered into a secure environment by the owner;
- an exchange API key must be created/configured;
- owner-defined capital or live-trading activation is required;
- a legal/commercial license choice cannot be safely inferred;
- a required product choice has multiple materially different interpretations not resolved by architecture.

When a blocker occurs:

1. continue every independent task possible;
2. persist progress to Git;
3. update STATUS.md;
4. create/update BLOCKER.md;
5. ask only for the minimal owner action needed;
6. provide exact resume instructions.

## Real-money boundary

Codex may build and validate everything necessary for real-money operation.

Codex must not invent or expose live credentials.

When L5/L6 validation genuinely requires external owner-controlled Binance credentials or explicit live activation, treat that as an external blocker.

After the owner performs the required secure action, resume the existing Master Goal and continue validation.

## Completion condition

The Master Goal is complete when:

1. all Enterprise Local implementation phases are complete;
2. all required automated tests pass;
3. paper/shadow/canary readiness is implemented;
4. certification evidence is recorded;
5. no unresolved critical security, execution, reconciliation, ledger, or risk defects remain;
6. operational runbooks exist;
7. the repository can be deployed as the Enterprise Local product;
8. any remaining action requiring the owner's live Binance credentials or explicit real-money activation is clearly isolated and documented;
9. Enterprise SaaS work has not been mixed into this scope.

If owner-controlled live credentials and activation are supplied during the Goal, continue through the live certification workflow according to the repository safety rules.
