import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from crazytrader_contracts.events import EVENT_TYPES, EventEnvelope
from crazytrader_contracts.models import CertificationState, Order, TradeIntent
from pydantic import ValidationError

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def intent_data() -> dict[str, object]:
    return {
        "intent_id": "ti_01",
        "schema_version": "1",
        "tenant_id": "local-owner",
        "portfolio_id": "strategy-medium",
        "mode": "STRATEGY",
        "source_type": "strategy_engine",
        "source_id": "strategy-agent",
        "strategy_version_id": "trend-breakout@17",
        "risk_profile_version_id": "medium@3",
        "capital_budget_ref": "alloc_01",
        "instrument_id": "binance:spot:BTCUSDT",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "intent_type": "OPEN",
        "risk_effect": "RISK_INCREASING",
        "requested_notional": "40.00",
        "confidence": "0.84",
        "expected_edge": "0.012",
        "expected_horizon": "PT2H",
        "max_slippage": "0.0015",
        "reason_code": "TREND_REGIME_BREAKOUT",
        "evidence_refs": ["ev_01"],
        "market_state_ref": "ms_01",
        "portfolio_state_ref": "ps_01",
        "created_at": "2026-10-02T00:00:00Z",
        "expires_at": "2026-10-02T02:00:00Z",
        "trace_id": "trace_01",
    }


def test_decimal_roundtrip_and_immutable_nested_values() -> None:
    intent = TradeIntent.model_validate(intent_data())
    assert intent.requested_notional == Decimal("40.00")
    assert '"requested_notional":"40.00"' in intent.model_dump_json()
    assert TradeIntent.model_validate_json(intent.model_dump_json()) == intent
    assert isinstance(intent.evidence_refs, tuple)
    with pytest.raises(ValidationError):
        intent.requested_notional = Decimal("50")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("requested_notional", 40.1),
        ("requested_notional", 40),
        ("requested_notional", True),
        ("requested_notional", "NaN"),
        ("requested_notional", "Infinity"),
        ("requested_notional", "-1"),
        ("requested_notional", "0"),
        ("requested_notional", "1e-9999"),
        ("requested_notional", " 40 "),
        ("requested_notional", "1e2"),
        ("created_at", 1790899200),
        ("expected_horizon", "PT0S"),
        ("requested_quantity", "0.001"),
        ("requested_notional", None),
        ("confidence", "1.1"),
        ("max_slippage", "-0.1"),
        ("schema_version", "2"),
        ("risk_effect", "RISK_REDUCING"),
        ("source_type", "agent"),
        ("mode", "RESERVE"),
        ("strategy_version_id", None),
        ("risk_profile_version_id", None),
        ("created_at", "2026-10-02T00:00:00"),
        ("created_at", "2026-10-02T00:00:00+02:00"),
        ("expires_at", "2026-10-02T00:00:00Z"),
        ("evidence_refs", []),
        ("expected_horizon", "PT"),
        ("expected_horizon", "soon"),
        ("api_secret", "not-a-real-secret"),
    ],
)
def test_intent_rejects_unsafe_or_ambiguous_inputs(key: str, value: object) -> None:
    data = intent_data()
    data[key] = value
    with pytest.raises(ValidationError):
        TradeIntent.model_validate(data)


def test_reduction_proposal_valid_without_changing_authority() -> None:
    data = intent_data()
    data.update(intent_type="CLOSE", risk_effect="RISK_REDUCING", side="SELL")
    assert TradeIntent.model_validate(data).risk_effect == "RISK_REDUCING"


def test_catalog_exactly_matches_spec() -> None:
    spec = Path("docs/specs/EVENT_CATALOG.md").read_text()
    assert EVENT_TYPES == frozenset(re.findall(r"^- ([A-Za-z]+\.v1)$", spec, re.M))


def test_event_roundtrip_and_unknown_version_rejected() -> None:
    data = {
        "event_id": "e_01",
        "event_type": "TradeIntentCreated.v1",
        "schema_version": "1",
        "occurred_at": NOW,
        "tenant_id": "local-owner",
        "source_service": "strategy-engine",
        "trace_id": "trace_01",
        "correlation_id": "ti_01",
        "payload": {
            "artifact_ref": "artifact_01",
            "sha256": "a" * 64,
            "payload_schema_ref": "TradeIntent.v1",
        },
    }
    event = EventEnvelope.model_validate(data)
    assert EventEnvelope.model_validate_json(event.model_dump_json()) == event
    data["event_type"] = "TradeIntentCreated.v2"
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(data)


def test_order_rejects_overfill_and_fake_filled_state() -> None:
    data = {
        "order_id": "o_01",
        "intent_id": "ti_01",
        "execution_request_id": "ex_01",
        "client_order_id": "client_01",
        "state": "UNKNOWN",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "requested_quantity": "1",
        "filled_quantity": "0",
        "created_at": NOW,
        "updated_at": NOW,
    }
    assert Order.model_validate(data).state == "UNKNOWN"
    for update in ({"filled_quantity": "2", "average_fill_price": "10"}, {"state": "FILLED"}):
        with pytest.raises(ValidationError):
            Order.model_validate(data | update)


def test_certification_claim_requires_evidence() -> None:
    data = {
        "tenant_id": "local-owner",
        "current_level": "L0",
        "achieved_at": NOW,
        "evidence_refs": [],
        "blockers": [],
        "last_reviewed_at": NOW,
    }
    assert CertificationState.model_validate(data).current_level == "L0"
    data["current_level"] = "L6"
    with pytest.raises(ValidationError):
        CertificationState.model_validate(data)


@pytest.mark.parametrize(
    "name",
    [
        "RiskDecision",
        "PolicyDecision",
        "Fill",
        "Portfolio",
        "StrategyVersion",
        "ModelVersion",
        "AuditEvent",
    ],
)
def test_remaining_foundations_roundtrip_and_reject_extras(name: str) -> None:
    from crazytrader_contracts import models

    records = {
        "RiskDecision": {
            "risk_decision_id": "rd_1",
            "intent_id": "ti_1",
            "decision": "DENY",
            "risk_effect": "RISK_INCREASING",
            "reason_codes": ["STALE_DATA"],
            "calculated_exposure": "40.00",
            "drawdown_state": "0.01",
            "market_health": "DEGRADED",
            "reconciliation_health": "UNKNOWN",
            "ruleset_version": "risk@1",
            "created_at": NOW,
        },
        "PolicyDecision": {
            "policy_decision_id": "pd_1",
            "intent_id": "ti_1",
            "actor_id": "actor_1",
            "decision": "DENY",
            "reason_codes": ["UNCERTIFIED"],
            "policy_bundle_version": "policy@1",
            "created_at": NOW,
        },
        "Fill": {
            "fill_id": "f_1",
            "order_id": "o_1",
            "venue_fill_id": "v_1",
            "quantity": "0.1",
            "price": "40",
            "fee_amount": "0.01",
            "fee_asset": "USDT",
            "timestamp": NOW,
        },
        "Portfolio": {
            "portfolio_id": "p_1",
            "tenant_id": "local-owner",
            "name": "Math",
            "mode": "MATH",
            "status": "STOPPED",
            "base_currency": "USDT",
            "created_at": NOW,
        },
        "StrategyVersion": {
            "strategy_version_id": "s@1",
            "strategy_id": "s",
            "semantic_version": "1.0.0",
            "artifact_ref": "artifact_1",
            "config_hash": "a" * 64,
            "lifecycle_stage": "DRAFT",
            "validation_evidence_refs": [],
            "created_at": NOW,
        },
        "ModelVersion": {
            "model_version_id": "m@1",
            "model_id": "m",
            "artifact_ref": "artifact_1",
            "dataset_version": "data@1",
            "feature_set_version": "features@1",
            "training_config_hash": "a" * 64,
            "metrics": [{"name": "score", "value": "0.1"}],
            "lifecycle_stage": "DRAFT",
            "validation_evidence_refs": [],
            "created_at": NOW,
        },
        "AuditEvent": {
            "audit_event_id": "audit_1",
            "actor_id": "owner",
            "action": "PAUSE",
            "resource_type": "portfolio",
            "resource_id": "p_1",
            "trace_id": "trace_1",
            "payload_ref": "payload_1",
            "timestamp": NOW,
        },
    }
    model = getattr(models, name)
    instance = model.model_validate(records[name])
    assert model.model_validate_json(instance.model_dump_json()) == instance
    with pytest.raises(ValidationError):
        model.model_validate(records[name] | {"bypass": True})
