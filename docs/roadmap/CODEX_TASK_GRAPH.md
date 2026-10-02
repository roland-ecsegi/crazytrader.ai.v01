# Codex Task Graph V1

Respect gates; parallelize only independent work with stable contracts.

    T000 audited docs/contracts
      -> T001 monorepo/toolchain
      -> T002 domain + T003 CI
      -> T004 contracts/events
      -> T004A open-source/license compatibility spikes
      -> T005 NATS + T006 PostgreSQL + T007 audit + T007B notification
      -> T008 control API
      -> T009 market data
      -> T010 ClickHouse/object data
      -> T011 ledger/portfolio
      -> T012 hard risk
      -> T013 OPA
      -> T014 execution state machine/integration
      -> T015 exchange test adapter
      -> T016 reconciliation
      -> T017 Math + T018 Strategy
      -> T019 agent runtime
      -> T020 skill/memory/experience
      -> T021 AI Gateway/Claude
      -> T022 research + T023 UI base
      -> T024 MLflow/lifecycle
      -> T025 learning
      -> T026 Capital Growth
      -> T027 security/OpenBao/supply-chain
      -> T028 observability/backup/recovery/runbooks
      -> T029 L1
      -> T030 L2
      -> T031 L3
      -> T032 L4
      -> T033 L5 local canary
      -> T034 L6 Enterprise Local acceptance

Before T012, T014, T016, T033 and T034 perform a mandatory adversarial architecture/security review. In Autonomous Program Mode this is an autonomous independent review pass/subagent with recorded evidence. Human approval is required only for true external blockers and explicit L5/L6 owner actions.

Avoid concurrent edits to TradeIntent, ledger semantics, order/risk state machines, OPA inputs, core event schemas or overlapping migrations.
