"""Immutable V1 contracts. Financial wire values are decimal strings, never floats."""

import re
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    model_validator,
)


def decimal_input(value: object) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("financial values must be decimal strings or Decimal")
    if isinstance(value, str) and not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("decimal wire values require canonical decimal notation")
    try:
        result = Decimal(value)
    except Exception as exc:
        raise ValueError("invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("nonfinite financial value")
    # Bound precision and exponents before later arithmetic/serialization.
    parts = result.as_tuple()
    if not isinstance(parts.exponent, int):
        raise ValueError("invalid decimal exponent")
    if len(parts.digits) > 38 or not -18 <= parts.exponent <= 18:
        raise ValueError("decimal exceeds V1 precision/scale")
    return result


def timestamp_input(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("timestamps must be datetime or ISO8601 strings")
    return value


def utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must include UTC offset")
    return value


DECIMAL_PATTERN = r"^-?[0-9]+(\.[0-9]+)?$"
Money = Annotated[
    Decimal,
    BeforeValidator(decimal_input),
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
    WithJsonSchema({"type": "string", "pattern": DECIMAL_PATTERN}),
]
Positive = Annotated[Money, Field(gt=0)]
NonNegative = Annotated[Money, Field(ge=0)]
Ratio = Annotated[Money, Field(ge=0, le=1)]
Identifier = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.:@/-]+$")]
Text = Annotated[str, Field(min_length=1, max_length=4096)]
Timestamp = Annotated[datetime, BeforeValidator(timestamp_input), AfterValidator(utc)]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)


class Mode(StrEnum):
    MATH = "MATH"
    STRATEGY = "STRATEGY"
    RESERVE = "RESERVE"


class RiskEffect(StrEnum):
    INCREASING = "RISK_INCREASING"
    REDUCING = "RISK_REDUCING"
    NEUTRAL = "RISK_NEUTRAL"


class IntentType(StrEnum):
    OPEN = "OPEN"
    INCREASE = "INCREASE"
    REDUCE = "REDUCE"
    CLOSE = "CLOSE"
    REBALANCE = "REBALANCE"


class OrderState(StrEnum):
    CREATED = "CREATED"
    RISK_PENDING = "RISK_PENDING"
    AUTHORIZED = "AUTHORIZED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    DENIED = "DENIED"
    REJECTED = "REJECTED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class Lifecycle(StrEnum):
    DRAFT = "DRAFT"
    BACKTESTED = "BACKTESTED"
    VALIDATED = "VALIDATED"
    OUT_OF_SAMPLE = "OUT_OF_SAMPLE"
    WALK_FORWARD = "WALK_FORWARD"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    CANARY_ELIGIBLE = "CANARY_ELIGIBLE"
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


class ConversionMetadata(Contract):
    price: Positive
    price_state_ref: Identifier
    venue_metadata_version: Identifier
    rounding: Literal["DOWN"]
    quantity_step: Positive


class TradeIntent(Contract):
    intent_id: Identifier
    schema_version: Literal["1"]
    tenant_id: Identifier
    portfolio_id: Identifier
    mode: Literal[Mode.MATH, Mode.STRATEGY]
    source_type: Literal["math_engine", "strategy_engine", "owner_manual", "portfolio_rebalance"]
    source_id: Identifier
    strategy_version_id: Identifier | None = None
    model_version_ids: tuple[Identifier, ...] = ()
    risk_profile_version_id: Identifier | None = None
    capital_budget_ref: Identifier
    instrument_id: Identifier
    symbol: Identifier
    side: Literal["BUY", "SELL"]
    intent_type: IntentType
    risk_effect: RiskEffect
    requested_notional: Positive | None = None
    requested_quantity: Positive | None = None
    conversion_metadata: ConversionMetadata | None = None
    confidence: Ratio | None = None
    expected_edge: Money | None = None
    expected_horizon: Annotated[str, Field(pattern=r"^PT([0-9]+H)?([0-9]+M)?([0-9]+S)?$")]
    max_slippage: Ratio
    reason_code: Identifier
    evidence_refs: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    market_state_ref: Identifier
    portfolio_state_ref: Identifier
    created_at: Timestamp
    expires_at: Timestamp
    trace_id: Identifier

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (self.requested_notional is None) == (self.requested_quantity is None):
            raise ValueError("exactly one authoritative sizing input required")
        if self.expires_at <= self.created_at:
            raise ValueError("expiry must follow creation")
        if not any(int(part) > 0 for part in re.findall(r"[0-9]+", self.expected_horizon)):
            raise ValueError("horizon must have a duration")
        if self.source_type == "math_engine" and self.mode != Mode.MATH:
            raise ValueError("math source requires Math Mode")
        if self.source_type == "strategy_engine" and (
            self.mode != Mode.STRATEGY or self.strategy_version_id is None
        ):
            raise ValueError("strategy source requires Strategy Mode and version")
        if self.mode == Mode.STRATEGY and self.risk_profile_version_id is None:
            raise ValueError("Strategy Mode requires versioned risk profile")
        expected = {
            IntentType.OPEN: RiskEffect.INCREASING,
            IntentType.INCREASE: RiskEffect.INCREASING,
            IntentType.REDUCE: RiskEffect.REDUCING,
            IntentType.CLOSE: RiskEffect.REDUCING,
        }.get(self.intent_type)
        if expected is not None and expected != self.risk_effect:
            raise ValueError("intent type contradicts proposed risk effect")
        return self


class RiskDecision(Contract):
    risk_decision_id: Identifier
    intent_id: Identifier
    decision: Literal["ALLOW", "DENY"]
    risk_effect: RiskEffect
    reason_codes: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    calculated_exposure: NonNegative
    drawdown_state: Ratio
    market_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    reconciliation_health: Literal["HEALTHY", "DEGRADED", "UNKNOWN"]
    ruleset_version: Identifier
    created_at: Timestamp


class PolicyDecision(Contract):
    policy_decision_id: Identifier
    intent_id: Identifier
    actor_id: Identifier
    decision: Literal["ALLOW", "DENY"]
    reason_codes: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    policy_bundle_version: Identifier
    created_at: Timestamp


class Order(Contract):
    order_id: Identifier
    intent_id: Identifier
    execution_request_id: Identifier
    venue_order_id: Identifier | None = None
    client_order_id: Identifier
    state: OrderState
    symbol: Identifier
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"]
    requested_quantity: Positive
    filled_quantity: NonNegative
    limit_price: Positive | None = None
    average_fill_price: Positive | None = None
    created_at: Timestamp
    updated_at: Timestamp

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.filled_quantity > self.requested_quantity:
            raise ValueError("fill exceeds requested quantity")
        if (self.order_type == "LIMIT") != (self.limit_price is not None):
            raise ValueError("limit price required only for LIMIT")
        if (self.filled_quantity > 0) != (self.average_fill_price is not None):
            raise ValueError("average fill price required exactly when filled")
        if self.state == OrderState.FILLED and self.filled_quantity != self.requested_quantity:
            raise ValueError("FILLED must be fully filled")
        if self.state == OrderState.PARTIALLY_FILLED and not (
            0 < self.filled_quantity < self.requested_quantity
        ):
            raise ValueError("PARTIALLY_FILLED requires partial quantity")
        if self.updated_at < self.created_at:
            raise ValueError("update precedes creation")
        return self


class Fill(Contract):
    fill_id: Identifier
    order_id: Identifier
    venue_fill_id: Identifier
    quantity: Positive
    price: Positive
    fee_amount: NonNegative
    fee_asset: Identifier
    timestamp: Timestamp


class Portfolio(Contract):
    portfolio_id: Identifier
    tenant_id: Identifier
    name: Text
    mode: Mode
    risk_profile_version_id: Identifier | None = None
    status: Literal["ACTIVE", "PAUSED", "STOPPED"]
    base_currency: Identifier
    created_at: Timestamp

    @model_validator(mode="after")
    def profile(self) -> Self:
        if self.mode == Mode.STRATEGY and self.risk_profile_version_id is None:
            raise ValueError("Strategy portfolio requires risk profile version")
        return self


class StrategyVersion(Contract):
    strategy_version_id: Identifier
    strategy_id: Identifier
    semantic_version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    artifact_ref: Identifier
    config_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    lifecycle_stage: Lifecycle
    validation_evidence_refs: tuple[Identifier, ...]
    created_at: Timestamp
    immutable_after_promotion: Literal[True] = True


class Metric(Contract):
    name: Identifier
    value: Money


class ModelVersion(Contract):
    model_version_id: Identifier
    model_id: Identifier
    artifact_ref: Identifier
    dataset_version: Identifier
    feature_set_version: Identifier
    training_config_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    metrics: tuple[Metric, ...]
    lifecycle_stage: Lifecycle
    validation_evidence_refs: tuple[Identifier, ...]
    created_at: Timestamp


class AuditEvent(Contract):
    audit_event_id: Identifier
    actor_id: Identifier
    action: Identifier
    resource_type: Identifier
    resource_id: Identifier
    trace_id: Identifier
    payload_ref: Identifier
    timestamp: Timestamp


class CertificationState(Contract):
    tenant_id: Identifier
    current_level: Literal["L0", "L1", "L2", "L3", "L4", "L5", "L6"]
    achieved_at: Timestamp
    evidence_refs: tuple[Identifier, ...]
    blockers: tuple[Text, ...]
    last_reviewed_at: Timestamp

    @model_validator(mode="after")
    def evidence(self) -> Self:
        if self.current_level != "L0" and not self.evidence_refs:
            raise ValueError("certification above L0 requires evidence references")
        if self.last_reviewed_at < self.achieved_at:
            raise ValueError("review precedes achievement")
        return self
