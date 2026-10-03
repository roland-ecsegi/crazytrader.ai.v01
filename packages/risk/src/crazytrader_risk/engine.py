"""Spot risk evaluation against a trusted immutable internal snapshot.

This pure function accepts fixtures for tests. Only an internal state loader may
supply production context; no agent/API accepts arbitrary context as authority.
ALLOW alone grants no submission: execution must reserve and recheck bound state.
"""

from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext

from crazytrader_contracts.models import (
    IntentType,
    Lifecycle,
    RiskEffect,
    TradeIntent,
    utc,
)
from crazytrader_contracts.risk import RiskAuthorization, RiskContext, RiskEvaluationDecision
from crazytrader_platform.storage import canonical, digest

ZERO = Decimal(0)


def evaluate(intent: TradeIntent, context: RiskContext, now: datetime) -> RiskAuthorization:
    intent = TradeIntent.model_validate(intent.model_dump())
    context = RiskContext.model_validate(context.model_dump())
    utc(now)
    reasons: list[str] = []
    owner, profile = context.owner_limits, context.profile_limits
    age = timedelta(seconds=min(owner.state_max_age_seconds, profile.state_max_age_seconds))
    quantity, notional = ZERO, None
    derived = RiskEffect.INCREASING if intent.side == "BUY" else RiskEffect.REDUCING
    if intent.intent_type == IntentType.REBALANCE:
        reasons.append("AMBIGUOUS_REBALANCE")
    if intent.risk_effect != derived:
        reasons.append("RISK_DIRECTION_MISMATCH")
    increasing = derived == RiskEffect.INCREASING
    if digest(canonical(intent)) != context.intent_sha256:
        reasons.append("INTENT_HASH_MISMATCH")
    if (intent.tenant_id, intent.portfolio_id, intent.mode) != (
        context.tenant_id,
        context.portfolio.portfolio_id,
        context.portfolio.mode,
    ):
        reasons.append("OWNERSHIP_OR_MODE_MISMATCH")
    if (
        intent.portfolio_state_ref,
        intent.market_state_ref,
        intent.capital_budget_ref,
        intent.instrument_id,
        intent.symbol,
    ) != (
        context.portfolio_state_ref,
        context.market_state_ref,
        context.budget_ref,
        context.instrument_id,
        context.metadata.symbol,
    ):
        reasons.append("STATE_REFERENCE_MISMATCH")
    if not intent.created_at <= now < intent.expires_at:
        reasons.append("INTENT_EXPIRED_OR_FUTURE")
    if (
        not timedelta(0) <= now - context.observed_at <= age
        or not timedelta(0) <= now - context.portfolio.as_of <= age
    ):
        reasons.append("STATE_STALE_OR_FUTURE")
    if context.venue_health != "HEALTHY":
        reasons.append("VENUE_STATE_UNPROVEN")
    if context.metadata.status != "TRADING":
        reasons.append("SYMBOL_NOT_TRADING")
    if (
        not timedelta(0)
        <= now - context.metadata.observed_at
        <= timedelta(seconds=min(owner.metadata_max_age_seconds, profile.metadata_max_age_seconds))
    ):
        reasons.append("METADATA_STALE_OR_FUTURE")
    if intent.max_slippage > min(owner.max_slippage, profile.max_slippage):
        reasons.append("SLIPPAGE_LIMIT")
    if intent.mode == "STRATEGY":
        if (intent.risk_profile_version_id, intent.strategy_version_id) != (
            context.risk_profile_version_id,
            context.strategy_version_id,
        ):
            reasons.append("PROFILE_OR_STRATEGY_VERSION_MISMATCH")
        stages = {
            "SIMULATION": {
                Lifecycle.VALIDATED,
                Lifecycle.OUT_OF_SAMPLE,
                Lifecycle.WALK_FORWARD,
                Lifecycle.PAPER,
                Lifecycle.SHADOW,
                Lifecycle.CANARY_ELIGIBLE,
                Lifecycle.LIVE,
            },
            "TESTNET": {
                Lifecycle.VALIDATED,
                Lifecycle.OUT_OF_SAMPLE,
                Lifecycle.WALK_FORWARD,
                Lifecycle.PAPER,
                Lifecycle.SHADOW,
                Lifecycle.CANARY_ELIGIBLE,
                Lifecycle.LIVE,
            },
            "PAPER": {Lifecycle.PAPER, Lifecycle.SHADOW, Lifecycle.CANARY_ELIGIBLE, Lifecycle.LIVE},
            "SHADOW": {Lifecycle.SHADOW, Lifecycle.CANARY_ELIGIBLE, Lifecycle.LIVE},
            "LIVE": {Lifecycle.LIVE},
        }
        if increasing and context.strategy_lifecycle not in stages[context.execution_mode]:
            reasons.append("STRATEGY_LIFECYCLE_DENIED")
        if context.profile_name is None:
            reasons.append("RISK_PROFILE_UNAVAILABLE")
    # L5 cannot authorize LIVE under current AGENTS invariant10.
    required_level = {"SIMULATION": 2, "TESTNET": 2, "PAPER": 3, "SHADOW": 4, "LIVE": 6}[
        context.execution_mode
    ]
    level = int(context.certification.current_level[1:])
    if context.execution_mode == "LIVE" and (level < 6 or not context.owner_live_activated):
        reasons.append("LIVE_CERTIFICATION_OR_ACTIVATION_DENIED")
    if increasing and (level < required_level or context.certification.blockers):
        reasons.append("CERTIFICATION_DENIED")
    if context.certification.last_reviewed_at > now or context.certification.achieved_at > now:
        reasons.append("FUTURE_CERTIFICATION")
    if (
        context.execution_mode in {"SIMULATION", "TESTNET"}
        and context.metadata.environment != "SANDBOX"
    ):
        reasons.append("ENVIRONMENT_MISMATCH")
    if increasing and intent.source_type == "math_engine":
        if (
            not intent.model_version_ids
            or intent.model_version_ids != context.model_version_ids
            or len(context.model_lifecycles) != len(context.model_version_ids)
        ):
            reasons.append("MATH_MODEL_PROVENANCE_UNAVAILABLE")
        allowed_stages = (
            {
                Lifecycle.VALIDATED,
                Lifecycle.OUT_OF_SAMPLE,
                Lifecycle.WALK_FORWARD,
                Lifecycle.PAPER,
                Lifecycle.SHADOW,
                Lifecycle.CANARY_ELIGIBLE,
                Lifecycle.LIVE,
            }
            if context.execution_mode in {"SIMULATION", "TESTNET"}
            else {Lifecycle.PAPER, Lifecycle.SHADOW, Lifecycle.CANARY_ELIGIBLE, Lifecycle.LIVE}
            if context.execution_mode == "PAPER"
            else {Lifecycle.SHADOW, Lifecycle.CANARY_ELIGIBLE, Lifecycle.LIVE}
            if context.execution_mode == "SHADOW"
            else {Lifecycle.LIVE}
        )
        if any(stage not in allowed_stages for stage in context.model_lifecycles):
            reasons.append("MATH_MODEL_LIFECYCLE_DENIED")
    price_usable = (
        context.price is not None
        and context.market.health == "HEALTHY"
        and context.market.last_exchange_at is not None
        and context.market.last_received_at is not None
        and all(
            timedelta(0) <= now - time <= age
            for time in (context.market.last_exchange_at, context.market.last_received_at)
        )
    )
    conversion = intent.conversion_metadata
    if conversion is not None and (
        conversion.price != context.price
        or conversion.price_state_ref != context.market_state_ref
        or conversion.venue_metadata_version != context.metadata.metadata_version
        or conversion.quantity_step != context.metadata.quantity_step
    ):
        reasons.append("CONVERSION_PROVENANCE_MISMATCH")
    with localcontext() as arithmetic:
        arithmetic.prec = 100
        if intent.requested_quantity is not None:
            quantity = intent.requested_quantity
            if quantity % context.metadata.quantity_step:
                reasons.append("QUANTITY_STEP_MISMATCH")
            if price_usable and context.price is not None:
                notional = quantity * context.price
        elif not price_usable or context.price is None:
            reasons.append("NOTIONAL_CONVERSION_UNAVAILABLE")
        else:
            assert intent.requested_notional is not None
            quantity = (
                intent.requested_notional / context.price / context.metadata.quantity_step
            ).to_integral_value(rounding=ROUND_DOWN) * context.metadata.quantity_step
            notional = quantity * context.price
        if (
            not context.metadata.min_quantity <= quantity <= context.metadata.max_quantity
            or quantity == 0
        ):
            reasons.append("VENUE_QUANTITY_FILTER_DENIED")
        if notional is not None and notional < context.metadata.min_notional:
            reasons.append("VENUE_MIN_NOTIONAL_DENIED")
        held = next(
            (
                b.total_held
                for b in context.portfolio.balances
                if b.asset == context.metadata.base_asset
            ),
            ZERO,
        )
        if not increasing:
            if (
                quantity > held - context.pending_sell_quantity
                or held - context.pending_sell_quantity < 0
            ):
                reasons.append("REDUCTION_WOULD_OVERSELL")
            if not context.owner_reduction_authorized or context.kill_scope == "CANCEL_ONLY":
                reasons.append("REDUCTION_PERMISSION_DENIED")
            if context.reconciliation_health != "HEALTHY" or context.accounting_health != "HEALTHY":
                reasons.append("REDUCTION_OWNERSHIP_UNPROVEN")
        else:
            if (
                context.market.health != "HEALTHY"
                or context.market.last_exchange_at is None
                or context.market.last_received_at is None
            ):
                reasons.append("MARKET_UNHEALTHY")
            elif any(
                not timedelta(0) <= now - time <= age
                for time in (context.market.last_exchange_at, context.market.last_received_at)
            ):
                reasons.append("MARKET_STALE_OR_FUTURE")
            if context.reconciliation_health != "HEALTHY" or context.accounting_health != "HEALTHY":
                reasons.append("ACCOUNTING_OR_RECONCILIATION_UNHEALTHY")
            if context.kill_scope != "NONE" or not (
                context.mode_enabled and context.portfolio_enabled and context.strategy_enabled
            ):
                reasons.append("NEW_RISK_KILLED_OR_PAUSED")
            if context.daily_loss is None or context.drawdown is None:
                reasons.append("PNL_VALUATION_UNKNOWN")
            else:
                if context.daily_loss >= min(owner.max_daily_loss, profile.max_daily_loss):
                    reasons.append("DAILY_LOSS_LIMIT")
                if context.drawdown >= min(owner.max_drawdown, profile.max_drawdown):
                    reasons.append("DRAWDOWN_LIMIT")
            if context.liquidity is None or context.liquidity < max(
                owner.min_liquidity, profile.min_liquidity
            ):
                reasons.append("LIQUIDITY_LIMIT")
            if context.spread is None or context.spread > min(owner.max_spread, profile.max_spread):
                reasons.append("SPREAD_LIMIT")
            expected_window = timedelta(
                seconds=max(owner.order_window_seconds, profile.order_window_seconds)
            )
            if (
                context.window_started_at > now
                or abs((now - context.window_started_at) - expected_window) > age
            ):
                reasons.append("ORDER_WINDOW_UNPROVEN")
            if context.orders_in_window >= min(
                owner.max_orders_per_window, profile.max_orders_per_window
            ):
                reasons.append("ORDER_FREQUENCY_LIMIT")
            if (
                context.active_positions >= min(owner.max_positions, profile.max_positions)
                and intent.intent_type == IntentType.OPEN
            ):
                reasons.append("CONCURRENT_POSITION_LIMIT")
            if notional is None:
                reasons.append("PRICE_UNAVAILABLE")
            else:
                available = next(
                    (
                        b.available
                        for b in context.portfolio.balances
                        if b.asset == context.metadata.quote_asset
                    ),
                    ZERO,
                )
                if notional > available:
                    reasons.append("INSUFFICIENT_AVAILABLE_CAPITAL")
                for name, exposure, limit in (
                    ("TOTAL", context.total_exposure, min(owner.total_cap, profile.total_cap)),
                    ("MODE", context.mode_exposure, min(owner.mode_cap, profile.mode_cap)),
                    (
                        "PORTFOLIO",
                        context.portfolio_exposure,
                        min(owner.portfolio_cap, profile.portfolio_cap),
                    ),
                    (
                        "STRATEGY",
                        context.strategy_exposure,
                        min(owner.strategy_cap, profile.strategy_cap),
                    ),
                    ("SYMBOL", context.symbol_exposure, min(owner.symbol_cap, profile.symbol_cap)),
                ):
                    if exposure is None:
                        reasons.append(name + "_EXPOSURE_UNKNOWN")
                    elif exposure + notional > limit:
                        reasons.append(name + "_CAP")
                if notional > min(owner.order_cap, profile.order_cap):
                    reasons.append("ORDER_NOTIONAL_CAP")
    context_hash = digest(canonical(context))
    key = digest(context.intent_sha256 + context_hash + now.isoformat())
    # Expired intent gets DENY evidence with a short evidence lifetime, never submission permission.
    expiry = min(
        intent.expires_at,
        now + age,
        context.observed_at + age,
        context.portfolio.as_of + age,
        context.metadata.observed_at
        + timedelta(seconds=min(owner.metadata_max_age_seconds, profile.metadata_max_age_seconds)),
    )
    if (
        increasing
        and context.market.last_exchange_at is not None
        and context.market.last_received_at is not None
    ):
        expiry = min(
            expiry, context.market.last_exchange_at + age, context.market.last_received_at + age
        )
    if expiry <= now:
        expiry = now + timedelta(seconds=1)  # DENY evidence only; stale/expired checks above deny.
    decision = RiskEvaluationDecision(
        risk_decision_id="risk:" + key,
        intent_id=intent.intent_id,
        decision="DENY" if reasons else "ALLOW",
        risk_effect=derived,
        reason_codes=tuple(dict.fromkeys(reasons)) or ("RISK_CHECKS_PASSED",),
        calculated_exposure=context.total_exposure,
        drawdown_state=context.drawdown,
        market_health=context.market.health,
        reconciliation_health=context.reconciliation_health,
        ruleset_version="spot-hard-risk.v1",
        created_at=now,
    )
    return RiskAuthorization(
        decision=decision,
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        intent_sha256=context.intent_sha256,
        context_sha256=context_hash,
        limits_sha256=digest(canonical(owner) + canonical(profile)),
        quantity=quantity,
        notional=notional,
        evaluated_at=now,
        expires_at=expiry,
        execution_mode=context.execution_mode,
    )
