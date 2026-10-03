from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from crazytrader_contracts.ledger import AssetBalance, PortfolioSnapshot
from crazytrader_contracts.market import InstrumentMetadata, MarketStatus
from crazytrader_contracts.models import CertificationState, TradeIntent
from crazytrader_contracts.risk import RiskContext, RiskLimits
from crazytrader_platform.storage import canonical, digest
from crazytrader_risk.engine import evaluate

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def fixture(side="BUY"):
    intent = TradeIntent(
        intent_id="fixture-intent",
        schema_version="1",
        tenant_id="fixture",
        portfolio_id="math",
        mode="MATH",
        source_type="owner_manual",
        source_id="owner",
        capital_budget_ref="budget.v1",
        instrument_id="binance:BTCUSDT",
        symbol="BTCUSDT",
        side=side,
        intent_type="OPEN" if side == "BUY" else "REDUCE",
        risk_effect="RISK_INCREASING" if side == "BUY" else "RISK_REDUCING",
        requested_quantity="0.1",
        expected_horizon="PT1M",
        max_slippage="0.001",
        reason_code="FIXTURE",
        evidence_refs=("fixture.v1",),
        market_state_ref="market.v1",
        portfolio_state_ref="portfolio.v1",
        created_at=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(seconds=30),
        trace_id="trace",
    )
    limits = RiskLimits(
        version="limits.v1",
        total_cap="1000",
        mode_cap="500",
        portfolio_cap="500",
        strategy_cap="500",
        symbol_cap="500",
        order_cap="100",
        max_positions=5,
        max_orders_per_window=10,
        order_window_seconds=60,
        max_daily_loss="50",
        max_drawdown="0.1",
        min_liquidity="1000",
        max_spread="0.01",
        max_slippage="0.005",
        metadata_max_age_seconds=300,
        state_max_age_seconds=5,
    )
    metadata = InstrumentMetadata(
        environment="SANDBOX",
        symbol="BTCUSDT",
        metadata_version="a" * 64,
        base_asset="BTC",
        quote_asset="USDT",
        status="TRADING",
        tick_size="0.01",
        quantity_step="0.001",
        min_quantity="0.001",
        max_quantity="100",
        min_notional="5",
        observed_at=NOW,
    )
    market = MarketStatus(
        environment="SANDBOX",
        symbol="BTCUSDT",
        metadata_version="a" * 64,
        health="HEALTHY",
        reason_code="FRESH",
        occurred_at=NOW,
        last_trade_id=1,
        gap_target=None,
        last_exchange_at=NOW,
        last_received_at=NOW,
    )
    portfolio = PortfolioSnapshot(
        tenant_id="fixture",
        portfolio_id="math",
        mode="MATH",
        as_of=NOW,
        balances=(
            AssetBalance(
                asset="USDT",
                available="1000",
                reserved="0",
                inventory="0",
                fees="0",
                total_held="1000",
            ),
            AssetBalance(
                asset="BTC", available="0", reserved="0", inventory="1", fees="0", total_held="1"
            ),
        ),
    )
    certification = CertificationState(
        tenant_id="fixture",
        current_level="L2",
        achieved_at=NOW,
        last_reviewed_at=NOW,
        evidence_refs=("fixture-only",),
        blockers=(),
    )
    context = RiskContext(
        context_id="fixture-only",
        intent_sha256=digest(canonical(intent)),
        tenant_id="fixture",
        portfolio=portfolio,
        portfolio_state_ref="portfolio.v1",
        market_state_ref="market.v1",
        budget_ref="budget.v1",
        instrument_id="binance:BTCUSDT",
        metadata=metadata,
        market=market,
        price="100",
        observed_at=NOW,
        certification=certification,
        execution_mode="SIMULATION",
        owner_live_activated=False,
        owner_reduction_authorized=True,
        actor_id="owner",
        owner_limits=limits,
        profile_limits=limits,
        total_exposure="100",
        mode_exposure="100",
        portfolio_exposure="100",
        strategy_exposure="100",
        symbol_exposure="100",
        pending_sell_quantity="0",
        active_positions=1,
        orders_in_window=0,
        window_started_at=NOW - timedelta(seconds=60),
        daily_loss="0",
        drawdown="0",
        liquidity="2000",
        spread="0.001",
        venue_health="HEALTHY",
        reconciliation_health="HEALTHY",
        accounting_health="HEALTHY",
        kill_scope="NONE",
        mode_enabled=True,
        portfolio_enabled=True,
        strategy_enabled=True,
    )
    return intent, context


def update(context, **changes):
    return RiskContext.model_validate(context.model_dump() | changes)


def test_allow_bound_to_exact_state_and_expiry():
    intent, context = fixture()
    authorization = evaluate(intent, context, NOW)
    assert authorization.decision.decision == "ALLOW"
    assert authorization.intent_sha256 == digest(canonical(intent))
    assert authorization.context_sha256 == digest(canonical(context))
    assert authorization.expires_at == NOW + timedelta(seconds=5)
    assert authorization.quantity == Decimal("0.1")
    assert authorization.notional == 10


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"kill_scope": "NEW_ORDERS"}, "NEW_RISK_KILLED_OR_PAUSED"),
        ({"mode_enabled": False}, "NEW_RISK_KILLED_OR_PAUSED"),
        ({"venue_health": "UNKNOWN"}, "VENUE_STATE_UNPROVEN"),
        ({"reconciliation_health": "DEGRADED"}, "ACCOUNTING_OR_RECONCILIATION_UNHEALTHY"),
        ({"accounting_health": "UNKNOWN"}, "ACCOUNTING_OR_RECONCILIATION_UNHEALTHY"),
        ({"daily_loss": None}, "PNL_VALUATION_UNKNOWN"),
        ({"daily_loss": "50"}, "DAILY_LOSS_LIMIT"),
        ({"drawdown": "0.1"}, "DRAWDOWN_LIMIT"),
        ({"liquidity": "999"}, "LIQUIDITY_LIMIT"),
        ({"spread": "0.02"}, "SPREAD_LIMIT"),
        ({"total_exposure": None}, "TOTAL_EXPOSURE_UNKNOWN"),
        ({"total_exposure": "995"}, "TOTAL_CAP"),
        ({"mode_exposure": "495"}, "MODE_CAP"),
        ({"portfolio_exposure": "495"}, "PORTFOLIO_CAP"),
        ({"strategy_exposure": "495"}, "STRATEGY_CAP"),
        ({"symbol_exposure": "495"}, "SYMBOL_CAP"),
        ({"orders_in_window": 10}, "ORDER_FREQUENCY_LIMIT"),
        ({"active_positions": 5}, "CONCURRENT_POSITION_LIMIT"),
        ({"price": None}, "PRICE_UNAVAILABLE"),
        ({"window_started_at": NOW}, "ORDER_WINDOW_UNPROVEN"),
        ({"observed_at": NOW - timedelta(seconds=6)}, "STATE_STALE_OR_FUTURE"),
        ({"observed_at": NOW + timedelta(seconds=1)}, "STATE_STALE_OR_FUTURE"),
        ({"intent_sha256": "f" * 64}, "INTENT_HASH_MISMATCH"),
    ],
)
def test_negative_matrix(changes, reason):
    intent, context = fixture()
    result = evaluate(intent, update(context, **changes), NOW)
    assert result.decision.decision == "DENY"
    assert reason in result.decision.reason_codes


def test_reduction_survives_market_kill_and_pnl_unknown_but_not_oversell():
    intent, context = fixture("SELL")
    stale = context.market.model_dump() | {
        "health": "DEGRADED",
        "reason_code": "STALE_OR_DISCONNECTED",
        "last_exchange_at": NOW - timedelta(seconds=30),
    }
    context = update(
        context,
        market=stale,
        price=None,
        kill_scope="FLATTEN_APPROVED",
        daily_loss=None,
        drawdown=None,
        total_exposure=None,
        mode_enabled=False,
        strategy_enabled=False,
    )
    result = evaluate(intent, context, NOW)
    assert result.decision.decision == "ALLOW"
    assert result.notional is None
    assert result.decision.drawdown_state is None
    assert result.decision.calculated_exposure is None
    assert (
        evaluate(intent, update(context, pending_sell_quantity="0.95"), NOW).decision.decision
        == "DENY"
    )
    assert (
        evaluate(intent, update(context, kill_scope="CANCEL_ONLY"), NOW).decision.decision == "DENY"
    )
    assert (
        evaluate(intent, update(context, owner_reduction_authorized=False), NOW).decision.decision
        == "DENY"
    )
    assert (
        evaluate(intent, update(context, accounting_health="UNKNOWN"), NOW).decision.decision
        == "DENY"
    )


def test_caller_cannot_label_buy_as_reduction():
    intent, context = fixture("SELL")
    forged = TradeIntent.model_validate(intent.model_dump() | {"side": "BUY"})
    context = update(context, intent_sha256=digest(canonical(forged)))
    result = evaluate(forged, context, NOW)
    assert result.decision.decision == "DENY"
    assert "RISK_DIRECTION_MISMATCH" in result.decision.reason_codes


def test_l0_and_l5_live_cannot_authorize_money():
    intent, context = fixture()
    cert = context.certification.model_dump() | {"current_level": "L0", "evidence_refs": ()}
    assert (
        "CERTIFICATION_DENIED"
        in evaluate(intent, update(context, certification=cert), NOW).decision.reason_codes
    )
    cert = context.certification.model_dump() | {"current_level": "L5"}
    metadata = context.metadata.model_dump() | {"environment": "PUBLIC"}
    market = context.market.model_dump() | {"environment": "PUBLIC"}
    result = evaluate(
        intent,
        update(
            context,
            certification=cert,
            metadata=metadata,
            market=market,
            execution_mode="LIVE",
            owner_live_activated=True,
        ),
        NOW,
    )
    assert "LIVE_CERTIFICATION_OR_ACTIVATION_DENIED" in result.decision.reason_codes


def test_high_profile_cannot_override_owner_caps_and_notional_rounds_down():
    intent, context = fixture()
    profile = context.profile_limits.model_dump() | {"order_cap": "10000", "total_cap": "10000"}
    owner = context.owner_limits.model_dump() | {"order_cap": "9"}
    result = evaluate(intent, update(context, profile_limits=profile, owner_limits=owner), NOW)
    assert "ORDER_NOTIONAL_CAP" in result.decision.reason_codes
    notional_intent = TradeIntent.model_validate(
        intent.model_dump() | {"requested_quantity": None, "requested_notional": "10.09"}
    )
    result = evaluate(
        notional_intent, update(context, intent_sha256=digest(canonical(notional_intent))), NOW
    )
    assert result.quantity == Decimal("0.100")
    assert result.notional == 10


def test_expired_changed_reference_and_off_step_denied():
    intent, context = fixture()
    assert (
        "INTENT_EXPIRED_OR_FUTURE"
        in evaluate(intent, context, NOW + timedelta(seconds=31)).decision.reason_codes
    )
    changed = TradeIntent.model_validate(
        intent.model_dump() | {"requested_quantity": "0.1001", "portfolio_state_ref": "wrong"}
    )
    result = evaluate(changed, update(context, intent_sha256=digest(canonical(changed))), NOW)
    assert "QUANTITY_STEP_MISMATCH" in result.decision.reason_codes
    assert "STATE_REFERENCE_MISMATCH" in result.decision.reason_codes
