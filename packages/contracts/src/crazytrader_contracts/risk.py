"""Trusted-state risk inputs and bound evidence; never agent order capability."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .ledger import PortfolioSnapshot
from .market import Hash, InstrumentMetadata, MarketStatus, Sequence
from .models import (
    CertificationState,
    Contract,
    Identifier,
    Lifecycle,
    NonNegative,
    Positive,
    Ratio,
    RiskEffect,
    Timestamp,
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
