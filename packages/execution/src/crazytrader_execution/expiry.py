"""Release expired AUTHORIZED simulation custody only with durable no-dispatch proof."""

from datetime import datetime
from decimal import Decimal

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.expiry import UnsentExecutionExpiry
from crazytrader_contracts.ledger import LedgerTransaction
from crazytrader_contracts.models import OrderState
from crazytrader_ledger.commands import release_custody
from crazytrader_ledger.store import LedgerStore
from crazytrader_platform.storage import ConflictError
from crazytrader_risk.store import RiskStore, StateUnavailable

from .state import transition
from .store import ExecutionStore


class UnsentExpiryService:
    def __init__(self, execution: ExecutionStore) -> None:
        self.execution, self.store = execution, execution.store

    def expire(
        self, request_id: str, authenticated_actor: str, now: datetime
    ) -> UnsentExecutionExpiry | None:
        current = self.execution.load(request_id)
        request = current.request
        if request.actor_id != authenticated_actor or request.execution_mode != "SIMULATION":
            raise StateUnavailable("unsent expiry owner/simulation authority denied")
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            RiskStore(self.store).configuration(request.tenant_id, authenticated_actor)
            current = self.execution._load(conn, request_id)
            previous = conn.execute(
                "SELECT body,digest FROM ct_unsent_execution_expiries "
                "WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if previous is not None:
                saved = UnsentExecutionExpiry.model_validate_json(str(previous["body"]))
                if digest(canonical(saved)) != previous["digest"]:
                    raise ConflictError("expiry source corrupted")
                return saved
            if now < request.expires_at or now < current.updated_at:
                return None
            if current.state != OrderState.AUTHORIZED:
                return None
            started = conn.execute(
                "SELECT 1 FROM ct_execution_transitions WHERE execution_request_id=%s "
                "AND body::jsonb->'resulting_state'->>'state' NOT IN("
                "'CREATED','RISK_PENDING','AUTHORIZED') "
                "UNION ALL SELECT 1 FROM ct_execution_observations WHERE execution_request_id=%s "
                "UNION ALL SELECT 1 FROM ct_native_simulation_receipts "
                "WHERE execution_request_id=%s LIMIT 1",
                (request_id, request_id, request_id),
            ).fetchone()
            if started is not None:
                raise StateUnavailable("expiry cannot release dispatched or ambiguous funds")
            row = conn.execute(
                "SELECT t.body,t.digest,r.reserve_amount FROM ct_execution_reservations r "
                "JOIN ct_ledger_transactions t ON t.transaction_id=r.reservation_tx_id "
                "WHERE r.execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if row is None:
                raise StateUnavailable("expiry original custody unavailable")
            original = LedgerTransaction.model_validate_json(str(row["body"]))
            if digest(canonical(original)) != row["digest"] or not isinstance(
                row["reserve_amount"], Decimal
            ):
                raise ConflictError("expiry original custody corrupted")
            release = release_custody(
                original,
                row["reserve_amount"],
                "unsent-expiry-release:" + request_id,
                "unsent-expiry-source:" + request_id,
                authenticated_actor,
                "unsent-expiry:" + request_id,
                now,
            )
            evidence = UnsentExecutionExpiry(
                request=request,
                original_reservation=original,
                release=release,
                actor_id=authenticated_actor,
                occurred_at=now,
            )
            LedgerStore(self.store).append_in_transaction(conn, release)
            change = transition(
                current,
                OrderState.EXPIRED,
                now,
                "AUTHORIZED_REQUEST_EXPIRED_UNSENT",
                "unsent-expiry:" + digest(canonical(evidence)),
            )
            self.execution._write(conn, change)
            body = canonical(evidence)
            conn.execute(
                "INSERT INTO ct_unsent_execution_expiries(execution_request_id,digest,body,"
                "release_tx_id) VALUES(%s,%s,%s,%s)",
                (request_id, digest(body), body, release.transaction_id),
            )
            event = EventEnvelope(
                event_id="unsent-expiry:" + digest(body),
                event_type="UnsentExecutionExpired.v1",
                schema_version="1",
                occurred_at=now,
                tenant_id=request.tenant_id,
                actor_id=authenticated_actor,
                source_service="execution",
                trace_id="unsent-expiry:" + digest(body),
                correlation_id=request_id,
                payload=PayloadReference(
                    artifact_ref=digest(body),
                    sha256=digest(body),
                    payload_schema_ref="UnsentExecutionExpiry.v1",
                ),
            )
            self.store.append_in_transaction(conn, event, evidence)
            return evidence
