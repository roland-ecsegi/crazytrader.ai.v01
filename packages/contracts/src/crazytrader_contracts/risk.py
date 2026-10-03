"""Trusted-state risk inputs and bound evidence; never agent order capability."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .codec import canonical, digest
from .ledger import PortfolioSnapshot
from .market import Hash, InstrumentMetadata, MarketStatus, Sequence
from .models import (
    CertificationState,
    Contract,
    Identifier,
    Lifecycle,
    NonNegative,
    PolicyDecision,
    Positive,
    Ratio,
    RiskEffect,
    Timestamp,
    TradeIntent,
)


class RiskLimits(Contract):
    version: Identifier
    total_cap: NonNegative
    mode_cap: NonNegative
    portfolio_cap: NonNegative
    strategy_cap: NonNegative
    symbol_cap: NonNegative
    order_cap: NonNegative
    max_positions: Sequence
    max_orders_per_window: Sequence
    order_window_seconds: Annotated[int, Field(strict=True, ge=1, le=86400)]
    max_daily_loss: NonNegative
    max_drawdown: Ratio
    min_liquidity: NonNegative
    max_spread: Ratio
    max_slippage: Ratio
    metadata_max_age_seconds: Annotated[int, Field(strict=True, ge=1, le=3600)]
    state_max_age_seconds: Annotated[int, Field(strict=True, ge=1, le=30)]


class RiskContext(Contract):
    schema_version: Literal["1"] = "1"
    context_id: Identifier
    intent_sha256: Hash
    tenant_id: Identifier
    portfolio: PortfolioSnapshot
    portfolio_state_ref: Identifier
    market_state_ref: Identifier
    budget_ref: Identifier
    instrument_id: Identifier
    metadata: InstrumentMetadata
    market: MarketStatus
    price: Positive | None
    observed_at: Timestamp
    certification: CertificationState
    execution_mode: Literal["SIMULATION", "TESTNET", "PAPER", "SHADOW", "LIVE"]
    owner_live_activated: Annotated[bool, Field(strict=True)] = False
    owner_reduction_authorized: Annotated[bool, Field(strict=True)] = False
    actor_id: Identifier
    owner_limits: RiskLimits
    profile_limits: RiskLimits
    risk_profile_version_id: Identifier | None = None
    profile_name: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    strategy_version_id: Identifier | None = None
    strategy_lifecycle: Lifecycle | None = None
    model_version_ids: tuple[Identifier, ...] = ()
    model_lifecycles: tuple[Lifecycle, ...] = ()
    total_exposure: NonNegative | None
    mode_exposure: NonNegative | None
    portfolio_exposure: NonNegative | None
    strategy_exposure: NonNegative | None
    symbol_exposure: NonNegative | None
    pending_sell_quantity: NonNegative
    active_positions: Sequence
    orders_in_window: Sequence
    window_started_at: Timestamp
    daily_loss: NonNegative | None
    drawdown: Ratio | None
    liquidity: NonNegative | None
    spread: Ratio | None
    venue_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    reconciliation_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    accounting_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    kill_scope: Literal["NONE", "NEW_ORDERS", "CANCEL_ONLY", "FLATTEN_APPROVED"]
    mode_enabled: Annotated[bool, Field(strict=True)]
    portfolio_enabled: Annotated[bool, Field(strict=True)]
    strategy_enabled: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def ownership(self) -> Self:
        if (
            self.portfolio.tenant_id != self.tenant_id
            or self.certification.tenant_id != self.tenant_id
        ):
            raise ValueError("risk context ownership mismatch")
        if (self.market.symbol, self.market.environment, self.market.metadata_version) != (
            self.metadata.symbol,
            self.metadata.environment,
            self.metadata.metadata_version,
        ):
            raise ValueError("market/instrument context mismatch")
        if self.execution_mode == "TESTNET" and self.metadata.environment != "SANDBOX":
            raise ValueError("testnet requires sandbox metadata")
        if self.execution_mode == "LIVE" and self.metadata.environment != "PUBLIC":
            raise ValueError("live requires public metadata")
        return self


class RiskEvaluationDecision(Contract):
    schema_version: Literal["1"] = "1"
    risk_decision_id: Identifier
    intent_id: Identifier
    decision: Literal["ALLOW", "DENY"]
    risk_effect: RiskEffect
    reason_codes: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    calculated_exposure: NonNegative | None
    drawdown_state: Ratio | None
    market_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    reconciliation_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    ruleset_version: Identifier
    created_at: Timestamp


class RiskAuthorization(Contract):
    schema_version: Literal["1"] = "1"
    decision: RiskEvaluationDecision
    tenant_id: Identifier
    actor_id: Identifier
    intent_sha256: Hash
    context_sha256: Hash
    limits_sha256: Hash
    quantity: NonNegative
    notional: NonNegative | None
    evaluated_at: Timestamp
    expires_at: Timestamp
    execution_mode: Literal["SIMULATION", "TESTNET", "PAPER", "SHADOW", "LIVE"]

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.expires_at <= self.evaluated_at:
            raise ValueError("authorization expiry must follow evaluation")
        return self


class CancellationRequest(Contract):
    """Maintenance of an existing TradeIntent-derived order, no new exposure."""

    schema_version: Literal["1"] = "1"
    request_id: Identifier
    tenant_id: Identifier
    portfolio_id: Identifier
    order_id: Identifier
    client_order_id: Identifier
    origin_intent_id: Identifier
    origin_intent_sha256: Hash
    symbol: Identifier
    environment: Literal["SANDBOX", "PUBLIC"]
    execution_mode: Literal["SIMULATION", "TESTNET", "PAPER", "SHADOW", "LIVE"]
    created_at: Timestamp
    expires_at: Timestamp

    @model_validator(mode="after")
    def expiry(self) -> Self:
        if self.expires_at <= self.created_at:
            raise ValueError("cancel expiry must follow creation")
        return self


class CancellationContext(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    actor_id: Identifier
    portfolio_id: Identifier
    order_id: Identifier
    client_order_id: Identifier
    origin_intent_id: Identifier
    origin_intent_sha256: Hash
    symbol: Identifier
    environment: Literal["SANDBOX", "PUBLIC"]
    execution_mode: Literal["SIMULATION", "TESTNET", "PAPER", "SHADOW", "LIVE"]
    ownership_proof_ref: Identifier
    venue_account_ref: Identifier
    order_state: Literal[
        "CREATED",
        "SUBMITTING",
        "SUBMITTED",
        "ACKNOWLEDGED",
        "PARTIALLY_FILLED",
        "CANCEL_PENDING",
        "UNKNOWN",
        "RECOVERY_REQUIRED",
        "FILLED",
        "CANCELLED",
        "REJECTED",
        "EXPIRED",
    ]
    observed_at: Timestamp
    max_age_seconds: Annotated[int, Field(strict=True, ge=1, le=30)]
    owner_cancel_authorized: Annotated[bool, Field(strict=True)]
    certification_level: Literal["L0", "L1", "L2", "L3", "L4", "L5", "L6"]
    owner_live_activated: Annotated[bool, Field(strict=True)]


class CancellationAuthorization(Contract):
    schema_version: Literal["1"] = "1"
    request_id: Identifier
    tenant_id: Identifier
    actor_id: Identifier
    order_id: Identifier
    client_order_id: Identifier
    origin_intent_id: Identifier
    request_sha256: Hash
    context_sha256: Hash
    policy_bundle_sha256: Hash
    decision: Literal["ALLOW", "DENY"]
    reason_codes: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    evaluated_at: Timestamp
    expires_at: Timestamp


class PolicyAuthorization(Contract):
    schema_version: Literal["1"] = "1"
    decision: PolicyDecision
    risk_authorization: RiskAuthorization
    policy_bundle_sha256: Hash
    evaluated_at: Timestamp
    expires_at: Timestamp

    @model_validator(mode="after")
    def bound(self) -> Self:
        risk = self.risk_authorization
        if (
            self.decision.intent_id != risk.decision.intent_id
            or self.decision.actor_id != risk.actor_id
        ):
            raise ValueError("policy/risk identity mismatch")
        if self.decision.created_at != self.evaluated_at or self.expires_at > risk.expires_at:
            raise ValueError("policy lifetime mismatch")
        if self.decision.decision == "ALLOW" and (
            risk.decision.decision != "ALLOW"
            or not risk.evaluated_at <= self.evaluated_at < self.expires_at
        ):
            raise ValueError("policy cannot outlive or override hard-risk denial")
        return self


class OwnerRiskConfiguration(Contract):
    schema_version: Literal["1"] = "1"
    config_id: Identifier
    tenant_id: Identifier
    actor_id: Identifier
    owner_authority_ref: Identifier
    owner_limits: RiskLimits
    profile_limits: RiskLimits
    risk_profile_version_id: Identifier | None
    profile_name: Literal["LOW", "MEDIUM", "HIGH"] | None
    execution_mode: Literal["SIMULATION", "TESTNET", "PAPER", "SHADOW", "LIVE"]
    symbol_allowlist: tuple[Identifier, ...]
    actor_permissions: tuple[
        Literal["risk.increase", "risk.reduce", "order.cancel", "live.activate"], ...
    ]
    owner_live_activated: Annotated[bool, Field(strict=True)]
    offline_protective_authorized: Annotated[bool, Field(strict=True)]
    policy_bundle_sha256: Hash


class VenueSafetyFact(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    environment: Literal["SANDBOX", "PUBLIC"]
    execution_mode: Literal["SIMULATION", "TESTNET", "PAPER", "SHADOW", "LIVE"]
    venue_account_ref: Identifier
    source_service: Literal["reconciliation"] = "reconciliation"
    venue_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    reconciliation_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    observed_at: Timestamp
    evidence_ref: Identifier


class RiskEvaluationRecord(Contract):
    schema_version: Literal["1"] = "1"
    intent: TradeIntent
    context: RiskContext
    authorization: RiskAuthorization
    policy: PolicyAuthorization | None

    @model_validator(mode="after")
    def integrity(self) -> Self:
        if self.authorization.intent_sha256 != digest(canonical(self.intent)):
            raise ValueError("risk record intent hash mismatch")
        if self.authorization.context_sha256 != digest(canonical(self.context)):
            raise ValueError("risk record context hash mismatch")
        if self.policy is not None and self.policy.risk_authorization != self.authorization:
            raise ValueError("risk/policy evidence mismatch")
        return self


class PortfolioSafetyFact(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    portfolio_id: Identifier
    source_service: Literal["portfolio-engine"] = "portfolio-engine"
    ledger_head_sha256: Hash
    mode: Literal["MATH", "STRATEGY"]
    symbol: Identifier
    strategy_version_id: Identifier | None
    accounting_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    total_exposure: NonNegative | None
    mode_exposure: NonNegative | None
    portfolio_exposure: NonNegative | None
    strategy_exposure: NonNegative | None
    symbol_exposure: NonNegative | None
    active_positions: Sequence
    orders_in_window: Sequence
    window_started_at: Timestamp
    daily_loss: NonNegative | None
    drawdown: Ratio | None
    observed_at: Timestamp
    evidence_ref: Identifier


class MarketSafetyFact(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    symbol: Identifier
    source_service: Literal["market-data"] = "market-data"
    metadata_version: Hash
    liquidity: NonNegative | None
    spread: Ratio | None
    observed_at: Timestamp
    evidence_ref: Identifier


class OperatingControls(Contract):
    schema_version: Literal["1"] = "1"
    control_version: Identifier
    tenant_id: Identifier
    portfolio_id: Identifier
    source_service: Literal["control-api"] = "control-api"
    owner_authority_ref: Identifier
    kill_scope: Literal["NONE", "NEW_ORDERS", "CANCEL_ONLY", "FLATTEN_APPROVED"]
    mode_enabled: Annotated[bool, Field(strict=True)]
    portfolio_enabled: Annotated[bool, Field(strict=True)]
    strategy_enabled: Annotated[bool, Field(strict=True)]
    occurred_at: Timestamp


class RiskBoundaryRejection(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    actor_id: Identifier
    intent_id: Identifier
    intent_sha256: Hash
    reason_code: Literal[
        "AUTHENTICATED_ACTOR_REQUIRED", "TRUSTED_STATE_UNAVAILABLE", "POLICY_CONFIGURATION_MISMATCH"
    ]
    occurred_at: Timestamp
