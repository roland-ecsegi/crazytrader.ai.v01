"""Owned-order cancellation proof independent of market/P&L/AI availability."""

from datetime import datetime, timedelta

from crazytrader_contracts.models import utc
from crazytrader_contracts.risk import CancellationContext, CancellationRequest
from crazytrader_platform.storage import canonical, digest


def cancellation_input(
    cancel: CancellationRequest,
    context: CancellationContext,
    now: datetime,
    permissions: tuple[str, ...],
    policy_hash: str,
) -> dict[str, object]:
    cancel = CancellationRequest.model_validate(cancel.model_dump())
    context = CancellationContext.model_validate(context.model_dump())
    utc(now)
    reasons = []
    if (
        cancel.tenant_id,
        cancel.portfolio_id,
        cancel.order_id,
        cancel.client_order_id,
        cancel.origin_intent_id,
        cancel.origin_intent_sha256,
        cancel.symbol,
        cancel.environment,
        cancel.execution_mode,
    ) != (
        context.tenant_id,
        context.portfolio_id,
        context.order_id,
        context.client_order_id,
        context.origin_intent_id,
        context.origin_intent_sha256,
        context.symbol,
        context.environment,
        context.execution_mode,
    ):
        reasons.append("CANCEL_OWNERSHIP_MISMATCH")
    if not cancel.created_at <= now < cancel.expires_at:
        reasons.append("CANCEL_EXPIRED_OR_FUTURE")
    if not timedelta(0) <= now - context.observed_at <= timedelta(seconds=context.max_age_seconds):
        reasons.append("CANCEL_PROOF_STALE_OR_FUTURE")
    if not context.owner_cancel_authorized or "order.cancel" not in permissions:
        reasons.append("CANCEL_PERMISSION_DENIED")
    if context.order_state not in {
        "SUBMITTING",
        "SUBMITTED",
        "ACKNOWLEDGED",
        "PARTIALLY_FILLED",
        "CANCEL_PENDING",
        "UNKNOWN",
        "RECOVERY_REQUIRED",
    }:
        reasons.append("ORDER_NOT_CANCELLABLE")
    if context.execution_mode == "LIVE" and (
        context.certification_level != "L6"
        or not context.owner_live_activated
        or "live.activate" not in permissions
    ):
        reasons.append("LIVE_CANCELLATION_DENIED")
    return {
        "action": "CANCEL",
        "schema_version": "1",
        "cancel_json": canonical(cancel),
        "cancel_context_json": canonical(context),
        "request_sha256": digest(canonical(cancel)),
        "context_sha256": digest(canonical(context)),
        "cancel_guard": not reasons,
        "guard_reason_codes": reasons,
        "now": now.isoformat(),
        "actor_permissions": permissions,
        "tenant_id": context.tenant_id,
        "actor_id": context.actor_id,
        "policy_bundle_sha256": policy_hash,
    }
