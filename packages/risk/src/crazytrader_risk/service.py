"""Internal risk boundary: caller supplies only immutable intent and authenticated identity.

No order endpoint. Authentication is supplied by the eventual owner/service transport;
this object is internal, never an agent tool with caller-selected healthy context.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.models import TradeIntent
from crazytrader_contracts.risk import RiskBoundaryRejection, RiskEvaluationRecord
from crazytrader_market.archive import S3Artifacts
from crazytrader_platform.storage import ConflictError

from .engine import evaluate
from .policy import OPAClient, PolicyRouter
from .store import RiskStore, StateUnavailable


class RiskService:
    def __init__(
        self,
        store: RiskStore,
        objects: S3Artifacts,
        policy: OPAClient | PolicyRouter,
        clock: Callable[[], datetime],
    ) -> None:
        self.store, self.objects, self.policy, self.clock = store, objects, policy, clock

    def evaluate(self, intent: TradeIntent, authenticated_actor: str) -> RiskEvaluationRecord:
        intent = TradeIntent.model_validate(intent.model_dump())
        now = self.clock()
        reason: Literal[
            "AUTHENTICATED_ACTOR_REQUIRED",
            "TRUSTED_STATE_UNAVAILABLE",
            "POLICY_CONFIGURATION_MISMATCH",
        ] = "TRUSTED_STATE_UNAVAILABLE"
        try:
            if not authenticated_actor:
                reason = "AUTHENTICATED_ACTOR_REQUIRED"
                raise StateUnavailable("authenticated actor required")
            context = self.store.context(
                intent.tenant_id, authenticated_actor, digest(canonical(intent))
            )
            config = self.store.validate_backbone(context, self.objects, now)
            remote = self.policy.remote if isinstance(self.policy, PolicyRouter) else self.policy
            if config.policy_bundle_sha256 != remote.policy_hash or (
                isinstance(self.policy, PolicyRouter)
                and self.policy.local.enabled != config.offline_protective_authorized
            ):
                reason = "POLICY_CONFIGURATION_MISMATCH"
                raise StateUnavailable("owner-approved policy configuration mismatch")
        except Exception:
            # No fabricated context/ALLOW. Persist a sanitized boundary denial before returning.
            # If DB/audit fails, exception still prevents authorization; no in-memory fallback.
            rejection = RiskBoundaryRejection(
                tenant_id=intent.tenant_id,
                actor_id=authenticated_actor or "unauthenticated",
                intent_id=intent.intent_id,
                intent_sha256=digest(canonical(intent)),
                reason_code=reason,
                occurred_at=now,
            )
            fingerprint = digest(canonical(rejection))
            self.store.store.append(
                EventEnvelope(
                    event_id="boundary:" + fingerprint,
                    event_type="RiskDecisionDenied.v1",
                    schema_version="1",
                    tenant_id=intent.tenant_id,
                    source_service="risk-engine",
                    actor_id=rejection.actor_id,
                    occurred_at=now,
                    trace_id=intent.trace_id,
                    correlation_id=intent.intent_id,
                    payload=PayloadReference(
                        artifact_ref=fingerprint,
                        sha256=fingerprint,
                        payload_schema_ref="RiskBoundaryRejection.v1",
                    ),
                ),
                rejection,
            )
            raise StateUnavailable(reason) from None
        authorization = evaluate(intent, context, now)
        if isinstance(self.policy, PolicyRouter):
            policy = self.policy.authorize(
                intent, context, authorization, config.actor_permissions, config.symbol_allowlist
            )
        else:
            policy = self.policy.authorize(
                intent,
                context,
                authorization,
                self.clock(),
                config.actor_permissions,
                config.symbol_allowlist,
            )
        record = RiskEvaluationRecord(
            intent=intent, context=context, authorization=authorization, policy=policy
        )
        # Record is only evidence. Phase5 must revalidate state and reserve atomically.
        try:
            self.store.record(record)
        except ConflictError:
            raise StateUnavailable("immutable financial proposal collision") from None
        return record
