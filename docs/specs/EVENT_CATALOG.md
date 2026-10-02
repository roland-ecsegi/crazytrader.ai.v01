# Event Catalog V1

## Event standard

Every event must carry:

- event_id
- event_type
- schema_version
- occurred_at
- tenant_id
- source_service
- trace_id
- correlation_id
- causation_id when applicable
- actor_id when applicable
- payload

Events are immutable.

Breaking schema changes require a new schema version.

## Market events

- MarketTickReceived.v1
- MarketTradeReceived.v1
- MarketBookUpdated.v1
- MarketCandleClosed.v1
- MarketDataStale.v1
- MarketDataRecovered.v1
- MarketSequenceGapDetected.v1

## Signal events

- MathSignalProduced.v1
- StrategySignalProduced.v1
- MarketRegimeChanged.v1

## TradeIntent events

- TradeIntentCreated.v1
- TradeIntentExpired.v1
- TradeIntentRiskApproved.v1
- TradeIntentRiskDenied.v1
- TradeIntentPolicyApproved.v1
- TradeIntentPolicyDenied.v1
- TradeIntentExecutionRequested.v1

## Order events

- OrderSubmissionStarted.v1
- OrderSubmitted.v1
- OrderAcknowledged.v1
- OrderPartiallyFilled.v1
- OrderFilled.v1
- OrderCancelRequested.v1
- OrderCancelled.v1
- OrderRejected.v1
- OrderExpired.v1
- OrderStateUnknown.v1
- OrderRecoveryStarted.v1
- OrderRecovered.v1

## Portfolio and ledger events

- CapitalAllocationProposed.v1
- CapitalAllocated.v1
- CapitalAllocationReduced.v1
- PositionOpened.v1
- PositionIncreased.v1
- PositionReduced.v1
- PositionClosed.v1
- LedgerEntryAppended.v1

## Risk events

- RiskWarningRaised.v1
- RiskDecisionDenied.v1
- DailyLossLimitReached.v1
- DrawdownLimitReached.v1
- ExposureLimitReached.v1
- TradingBlocked.v1
- TradingUnblocked.v1
- GlobalKillActivated.v1
- GlobalKillCleared.v1

## Reconciliation events

- ReconciliationStarted.v1
- ReconciliationCompleted.v1
- ReconciliationMismatchDetected.v1
- ReconciliationCriticalMismatch.v1
- ReconciliationRecovered.v1

## Agent events

- AgentTaskCreated.v1
- AgentTaskStarted.v1
- AgentTaskCompleted.v1
- AgentTaskFailed.v1
- AgentAvailabilityChanged.v1
- AgentPermissionChanged.v1
- AgentMemoryUpdated.v1
- ExperienceRecordCreated.v1
- AIProviderAvailabilityChanged.v1
- AIProviderUsageLimited.v1

## Research events

- HypothesisCreated.v1
- ExperimentStarted.v1
- ExperimentCompleted.v1
- StrategyCandidateCreated.v1
- StrategyPromoted.v1
- StrategyDegraded.v1
- StrategySuspended.v1
- StrategyRetired.v1
- ModelRegistered.v1
- ModelPromoted.v1
- ModelRolledBack.v1
- StrategyPromotionDenied.v1
- ModelPromotionDenied.v1

## Platform events

- SystemIncidentOpened.v1
- SystemIncidentResolved.v1
- CertificationLevelChanged.v1
- SecretRotationRequired.v1
- ServiceHealthChanged.v1

## Delivery semantics

Consumers must assume at-least-once delivery unless a stronger guarantee is explicitly implemented.

Handlers that mutate financial state must therefore be idempotent.
