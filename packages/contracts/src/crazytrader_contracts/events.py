"""V1 catalog/envelope. Typed producer payloads are added before service integration."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .models import Contract, Identifier, Timestamp

EVENT_TYPES: frozenset[str] = frozenset(
    {
        "MarketTickReceived.v1",
        "MarketTradeReceived.v1",
        "MarketBookUpdated.v1",
        "MarketCandleClosed.v1",
        "MarketDataStale.v1",
        "MarketDataRecovered.v1",
        "MarketSequenceGapDetected.v1",
        "MathSignalProduced.v1",
        "StrategySignalProduced.v1",
        "MarketRegimeChanged.v1",
        "TradeIntentCreated.v1",
        "TradeIntentExpired.v1",
        "TradeIntentRiskApproved.v1",
        "TradeIntentRiskDenied.v1",
        "TradeIntentPolicyApproved.v1",
        "TradeIntentPolicyDenied.v1",
        "TradeIntentExecutionRequested.v1",
        "ExecutionPreparationChanged.v1",
        "OrderSubmissionStarted.v1",
        "OrderSubmitted.v1",
        "OrderAcknowledged.v1",
        "OrderPartiallyFilled.v1",
        "OrderFilled.v1",
        "OrderCancelRequested.v1",
        "OrderCancellationAuthorized.v1",
        "OrderCancellationDenied.v1",
        "OrderCancellationReceiptRecorded.v1",
        "OrderCancelled.v1",
        "OrderRejected.v1",
        "OrderExpired.v1",
        "OrderStateUnknown.v1",
        "OrderRecoveryStarted.v1",
        "OrderRecovered.v1",
        "CapitalAllocationProposed.v1",
        "CapitalAllocated.v1",
        "CapitalAllocationReduced.v1",
        "PositionOpened.v1",
        "PositionIncreased.v1",
        "PositionReduced.v1",
        "PositionClosed.v1",
        "LedgerEntryAppended.v1",
        "RiskWarningRaised.v1",
        "RiskDecisionDenied.v1",
        "DailyLossLimitReached.v1",
        "DrawdownLimitReached.v1",
        "ExposureLimitReached.v1",
        "TradingBlocked.v1",
        "TradingUnblocked.v1",
        "GlobalKillActivated.v1",
        "GlobalKillCleared.v1",
        "ReconciliationStarted.v1",
        "ReconciliationCompleted.v1",
        "ReconciliationMismatchDetected.v1",
        "ReconciliationCriticalMismatch.v1",
        "ReconciliationRecovered.v1",
        "AgentTaskCreated.v1",
        "AgentTaskStarted.v1",
        "AgentTaskCompleted.v1",
        "AgentTaskFailed.v1",
        "AgentAvailabilityChanged.v1",
        "AgentPermissionChanged.v1",
        "AgentMemoryUpdated.v1",
        "ExperienceRecordCreated.v1",
        "AIProviderAvailabilityChanged.v1",
        "AIProviderUsageLimited.v1",
        "HypothesisCreated.v1",
        "ExperimentStarted.v1",
        "ExperimentCompleted.v1",
        "StrategyCandidateCreated.v1",
        "StrategyPromoted.v1",
        "StrategyDegraded.v1",
        "StrategySuspended.v1",
        "StrategyRetired.v1",
        "ModelRegistered.v1",
        "ModelPromoted.v1",
        "ModelRolledBack.v1",
        "StrategyPromotionDenied.v1",
        "ModelPromotionDenied.v1",
        "SystemIncidentOpened.v1",
        "SystemIncidentResolved.v1",
        "CertificationLevelChanged.v1",
        "SecretRotationRequired.v1",
        "ServiceHealthChanged.v1",
    }
)


class PayloadReference(Contract):
    """Immutable content-addressed payload; no arbitrary untrusted mutable dict."""

    artifact_ref: Identifier
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    payload_schema_ref: Identifier


class EventEnvelope(Contract):
    event_id: Identifier
    event_type: Identifier
    schema_version: Literal["1"]
    occurred_at: Timestamp
    tenant_id: Identifier
    source_service: Identifier
    trace_id: Identifier
    correlation_id: Identifier
    causation_id: Identifier | None = None
    actor_id: Identifier | None = None
    payload: PayloadReference

    @model_validator(mode="after")
    def catalog(self) -> Self:
        if self.event_type not in EVENT_TYPES:
            raise ValueError("unknown V1 event type")
        return self
