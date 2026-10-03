"""Owned registry -> current deterministic policy -> one cancel send -> query settlement.

Literal-loopback fixture only. Cancellation receipt never releases financial authority.
"""

from collections.abc import Callable
from datetime import datetime

import psycopg
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import CancellationEvaluationRecord, CancellationReceipt
from crazytrader_contracts.models import Contract, OrderState
from crazytrader_contracts.risk import (
    CancellationContext,
    CancellationRequest,
    OwnerRiskConfiguration,
)
from crazytrader_platform.storage import ConflictError
from crazytrader_risk.policy import OPAClient, PolicyRouter
from crazytrader_risk.store import StateUnavailable

from .fixture_transport import SDKFixtureTransport
from .state import transition
from .store import ExecutionStore


class FixtureCancellationRunner:
    def __init__(
        self,
        execution: ExecutionStore,
        transport: SDKFixtureTransport,
        policy: OPAClient | PolicyRouter,
        clock: Callable[[], datetime],
    ) -> None:
        self.execution, self.transport, self.policy, self.clock = (
            execution,
            transport,
            policy,
            clock,
        )

    def _audit(
        self, conn: psycopg.Connection[dict[str, object]], payload: Contract, event_type: str
    ) -> None:
        if isinstance(payload, CancellationEvaluationRecord):
            tenant, actor = payload.context.tenant_id, payload.context.actor_id
            occurred = payload.authorization.evaluated_at
            correlation = payload.request.request_id
        elif isinstance(payload, CancellationReceipt):
            tenant, actor = payload.tenant_id, payload.actor_id
            occurred, correlation = payload.observed_at, payload.cancellation_request_id
        else:
            raise ValueError("unsupported cancellation audit payload")
        fingerprint = digest(canonical(payload))
        event = EventEnvelope.model_validate(
            {
                "event_id": "cancel:" + fingerprint,
                "event_type": event_type,
                "schema_version": "1",
                "occurred_at": occurred,
                "tenant_id": tenant,
                "actor_id": actor,
                "source_service": "execution",
                "trace_id": correlation,
                "correlation_id": correlation,
                "payload": PayloadReference(
                    artifact_ref=fingerprint,
                    sha256=fingerprint,
                    payload_schema_ref=type(payload).__name__ + ".v1",
                ),
            }
        )
        self.execution.store.append_in_transaction(conn, event, payload)

    def cancel_once(
        self, execution_id: str, cancel: CancellationRequest, authenticated_actor: str
    ) -> CancellationReceipt | None:
        cancel = CancellationRequest.model_validate(cancel.model_dump())
        with self.execution.store.connection() as conn:
            self.execution._lock(conn, cancel.tenant_id)
            current = self.execution._load(conn, execution_id)
            request = current.request
            if authenticated_actor != request.actor_id or not authenticated_actor:
                raise StateUnavailable("authenticated owned-order actor required")
            if request.execution_mode != "SIMULATION":
                raise StateUnavailable("fixture cancellation has no signed/live authority")
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
                request.tenant_id,
                request.portfolio_id,
                request.order_id,
                request.client_order_id,
                request.intent_id,
                request.intent_sha256,
                request.symbol,
                request.environment,
                request.execution_mode,
            ):
                raise StateUnavailable("cancellation owned execution mismatch")
            previous = conn.execute(
                "SELECT request_digest FROM ct_cancellation_evaluations WHERE request_id=%s",
                (cancel.request_id,),
            ).fetchone()
            if previous is not None:
                if previous["request_digest"] != digest(canonical(cancel)):
                    raise ConflictError("cancellation request identity collision")
                return None  # claimed or denied requests never generate another wire send
            row = conn.execute(
                "SELECT c.body,c.digest FROM ct_risk_configs c JOIN ct_risk_active_configs a "
                "USING(tenant_id,actor_id,config_id) WHERE a.tenant_id=%s AND a.actor_id=%s",
                (cancel.tenant_id, authenticated_actor),
            ).fetchone()
            if row is None:
                raise StateUnavailable("owner cancellation authority unavailable")
            config = OwnerRiskConfiguration.model_validate_json(str(row["body"]))
            if digest(canonical(config)) != row["digest"]:
                raise ConflictError("owner cancellation configuration integrity failure")
            remote = self.policy.remote if isinstance(self.policy, PolicyRouter) else self.policy
            if config.policy_bundle_sha256 != remote.policy_hash or (
                isinstance(self.policy, PolicyRouter)
                and self.policy.local.enabled != config.offline_protective_authorized
            ):
                raise StateUnavailable("owner cancellation policy mismatch")
            now = self.clock()
            context = CancellationContext(
                tenant_id=request.tenant_id,
                actor_id=authenticated_actor,
                portfolio_id=request.portfolio_id,
                order_id=request.order_id,
                client_order_id=request.client_order_id,
                origin_intent_id=request.intent_id,
                origin_intent_sha256=request.intent_sha256,
                symbol=request.symbol,
                environment=request.environment,
                execution_mode=request.execution_mode,
                ownership_proof_ref="execution:" + digest(canonical(current)),
                venue_account_ref=request.venue_account_ref,
                order_state=current.state.value,
                observed_at=now,
                max_age_seconds=5,
                owner_cancel_authorized=(
                    "order.cancel" in config.actor_permissions
                    and config.execution_mode == request.execution_mode
                    and request.symbol in config.symbol_allowlist
                ),
                certification_level="L0",
                owner_live_activated=False,
            )
            if isinstance(self.policy, PolicyRouter):
                authorization = self.policy.authorize_cancel(
                    cancel, context, config.actor_permissions
                )
            else:
                authorization = self.policy.authorize_cancel(
                    cancel, context, now, config.actor_permissions
                )
            record = CancellationEvaluationRecord(
                execution_request_id=execution_id,
                owner_config_sha256=str(row["digest"]),
                execution_revision=current.revision,
                request=cancel,
                context=context,
                authorization=authorization,
            )
            body = canonical(record)
            conn.execute(
                "INSERT INTO ct_cancellation_evaluations"
                "(request_id,execution_request_id,request_digest,digest,body) "
                "VALUES(%s,%s,%s,%s,%s)",
                (cancel.request_id, execution_id, digest(canonical(cancel)), digest(body), body),
            )
            allowed = authorization.decision == "ALLOW" and self.clock() < authorization.expires_at
            self._audit(
                conn,
                record,
                "OrderCancellationAuthorized.v1"
                if authorization.decision == "ALLOW"
                else "OrderCancellationDenied.v1",
            )
            if not allowed:
                return None
            if current.state == OrderState.SUBMITTING:
                change = transition(
                    current,
                    OrderState.UNKNOWN,
                    self.clock(),
                    "CANCEL_PENDING_UNKNOWN_SUBMISSION",
                    "cancel:" + digest(body),
                )
                self.execution._write(conn, change)
                current = change.resulting_state
            if current.state == OrderState.UNKNOWN:
                change = transition(
                    current,
                    OrderState.RECOVERY_REQUIRED,
                    self.clock(),
                    "OWNED_CANCEL_RECOVERY",
                    "reconciliation:" + digest(body),
                )
                self.execution._write(conn, change)
                current = change.resulting_state
            if current.state != OrderState.CANCEL_PENDING:
                change = transition(
                    current,
                    OrderState.CANCEL_PENDING,
                    self.clock(),
                    "OWNED_CANCELLATION_AUTHORIZED",
                    "reconciliation:" + digest(body),
                )
                self.execution._write(conn, change)
        # Durable claim/audit before send. Crash leaves CANCEL_PENDING and retained reservation.
        receipt = self.transport.cancel(request, record, self.clock())
        with self.execution.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            body = canonical(receipt)
            conn.execute(
                "INSERT INTO ct_cancellation_receipts(digest,request_id,body) VALUES(%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (digest(body), cancel.request_id, body),
            )
            self._audit(conn, receipt, "OrderCancellationReceiptRecorded.v1")
        return receipt
