# Codex Task Graph V1

## Rule

Codex must respect dependency gates.

Parallelism is encouraged only when contracts are stable and tasks do not share unsafe ownership.

## Dependency graph

    T000 Documentation/contract baseline
       |
       v
    T001 Monorepo/toolchain
       |
       +----------------------+
       |                      |
       v                      v
    T002 Domain           T003 CI/quality
       |
       v
    T004 Contracts/events
       |
       +-------------+----------------+
       |             |                |
       v             v                v
    T005 NATS     T006 PostgreSQL   T007 Audit
       |             |
       +------+------+
              |
              v
         T008 Control API
              |
              v
         T009 Market data
              |
              v
         T010 ClickHouse/data
              |
              v
         T011 Ledger/portfolio
              |
              v
         T012 Hard Risk
              |
              v
         T013 OPA policies
              |
              v
         T014 Execution state machine
              |
              v
         T015 Exchange test adapter
              |
              v
         T016 Reconciliation
              |
       +------+------+
       |             |
       v             v
    T017 Math     T018 Strategy
       |             |
       +------+------+
              |
              v
         T019 Agent runtime
              |
              v
         T020 Skill registry
              |
              v
         T021 AI Gateway
              |
       +------+------+
       |             |
       v             v
    T022 Research  T023 UI base
       |
       v
    T024 MLflow/model lifecycle
       |
       v
    T025 Learning/experience
       |
       v
    T026 Capital Growth Engine
       |
       v
    T027 Security/OpenBao
       |
       v
    T028 Observability/recovery
       |
       v
    T029 L1 Backtest certification
       |
       v
    T030 L2 Simulation certification
       |
       v
    T031 L3 Paper certification
       |
       v
    T032 L4 Shadow certification
       |
       v
    T033 L5 Canary certification
       |
       v
    T034 L6 Live certification

## Parallel-safe examples

After contracts stabilize:

- CI work may run in parallel with domain implementation.
- UI shell may run in parallel with research internals if API contracts are fixed.
- documentation and non-financial observability can run in parallel with service work.
- independent agent skill implementations can run in parallel after skill contracts are versioned.

## Do not parallelize blindly

Avoid parallel changes to:

- TradeIntent schema;
- financial ledger semantics;
- order state machine;
- risk semantics;
- OPA authorization inputs;
- event names and schema versions;
- database migrations touching the same tables.

## Review gates

Mandatory architectural review before:

- T012 Hard Risk;
- T014 Execution;
- T016 Reconciliation;
- T033 Canary;
- T034 Live certification.
