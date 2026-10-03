"""Source-first financial closure of bounded, absent loopback simulation orders."""

from datetime import UTC, datetime
from decimal import Decimal

from crazytrader_contracts.absence import FixtureOrderLookup, FixtureTimedOrderLookup
from crazytrader_contracts.absence_closure import FixtureAbsenceClosure
from crazytrader_contracts.account import VenueAccountRead
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.dispatch import FixtureDispatchBound
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import ExecutionRequest
from crazytrader_contracts.ledger import LedgerTransaction
from crazytrader_contracts.models import OrderState
from crazytrader_ledger.commands import release_custody
from crazytrader_ledger.store import LedgerStore
from crazytrader_platform.storage import ConflictError
from crazytrader_risk.store import RiskStore, StateUnavailable

from .absence import FixtureAbsenceAssessor
from .fixture_transport import SDKFixtureTransport
from .state import transition
from .store import ExecutionStore


class _TimedTransport(SDKFixtureTransport):
    def __init__(self, transport: SDKFixtureTransport) -> None:
        super().__init__(transport.endpoint, transport.sdk_python, transport.child)
        self.transport = transport
        self.captured: FixtureTimedOrderLookup | None = None

    def lookup(self, request: ExecutionRequest) -> FixtureOrderLookup:
        self.captured = self.transport.timed_lookup(request)
        return self.captured.lookup

    def account(self, request: ExecutionRequest, symbols: tuple[str, ...]) -> VenueAccountRead:
        return self.transport.account(request, symbols)


class FixtureAbsenceCloser:
    def __init__(self, execution: ExecutionStore, transport: SDKFixtureTransport) -> None:
        self.execution, self.store, self.transport = execution, execution.store, transport

    def close(self, request_id: str, authenticated_actor: str) -> FixtureAbsenceClosure | None:
        self.execution.require_sdk_account(request_id)
        request = self.execution.load(request_id).request
        if request.actor_id != authenticated_actor:
            raise StateUnavailable("absence closure owner denied")
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            RiskStore(self.store).configuration(request.tenant_id, authenticated_actor)
            prior = conn.execute(
                "SELECT digest,body FROM ct_fixture_absence_closures WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is not None:
                saved = FixtureAbsenceClosure.model_validate_json(str(prior["body"]))
                if digest(canonical(saved)) != prior["digest"]:
                    raise ConflictError("absence closure source corrupted")
                return saved
            row = conn.execute(
                "SELECT digest,body FROM ct_fixture_dispatch_bounds WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if row is None:
                return None
            bound = FixtureDispatchBound.model_validate_json(str(row["body"]))
            if bound.request != request or digest(canonical(bound)) != row["digest"]:
                raise ConflictError("original dispatch bound corrupted")
            state = self.execution._load(conn, request_id)
            if state.state not in {OrderState.UNKNOWN, OrderState.RECOVERY_REQUIRED}:
                return None
        capture = _TimedTransport(self.transport)
        assessor = FixtureAbsenceAssessor(self.execution, capture)
        try:
            assessment = assessor.assess(request_id, authenticated_actor)
        except StateUnavailable:
            # A concurrent closer may commit between our initial check and source capture.
            with self.store.connection() as conn:
                prior = conn.execute(
                    "SELECT digest,body FROM ct_fixture_absence_closures "
                    "WHERE execution_request_id=%s",
                    (request_id,),
                ).fetchone()
            if prior is None:
                raise
            saved = FixtureAbsenceClosure.model_validate_json(str(prior["body"]))
            if digest(canonical(saved)) != prior["digest"]:
                raise ConflictError("absence closure source corrupted") from None
            return saved
        timed = capture.captured
        if timed is None:
            raise StateUnavailable("paired signed lookup unavailable")
        # Commit the paired clock source before attempting any financial transaction.
        with self.store.connection() as conn:
            conn.execute(
                "INSERT INTO ct_fixture_timed_lookups"
                "(digest,execution_request_id,lookup_digest,body) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    digest(canonical(timed)),
                    request_id,
                    digest(canonical(timed.lookup)),
                    canonical(timed),
                ),
            )
        if assessment.verdict != "PROVEN":
            return None
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            RiskStore(self.store).configuration(request.tenant_id, authenticated_actor)
            prior = conn.execute(
                "SELECT digest,body FROM ct_fixture_absence_closures WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is not None:
                saved = FixtureAbsenceClosure.model_validate_json(str(prior["body"]))
                if digest(canonical(saved)) != prior["digest"]:
                    raise ConflictError("absence closure source corrupted")
                return saved
            current = self.execution._load(conn, request_id)
            if (
                current != assessment.state
                or assessor.accounts._head(conn, request.tenant_id)
                != assessment.internal_head_sha256
            ):
                return None
            row = conn.execute(
                "SELECT t.body,t.digest,r.reserve_amount,r.reserve_asset "
                "FROM ct_execution_reservations r JOIN ct_ledger_transactions t "
                "ON t.transaction_id=r.reservation_tx_id WHERE r.execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if row is None or not isinstance(row["reserve_amount"], Decimal):
                raise StateUnavailable("original absence custody unavailable")
            original = LedgerTransaction.model_validate_json(str(row["body"]))
            if digest(canonical(original)) != row["digest"]:
                raise ConflictError("absence original custody corrupted")
            remaining = conn.execute(
                "SELECT COALESCE(sum(p.amount),0) balance FROM ct_ledger_postings p "
                "JOIN ct_ledger_transactions t USING(transaction_id) WHERE p.tenant_id=%s "
                "AND p.portfolio_id=%s AND p.account='RESERVED' AND p.asset=%s "
                "AND t.related_order_id=%s",
                (request.tenant_id, request.portfolio_id, row["reserve_asset"], request.order_id),
            ).fetchone()
            if remaining is None or remaining["balance"] != row["reserve_amount"]:
                raise StateUnavailable("absence requires whole original reservation")
            now = datetime.now(UTC)
            release = release_custody(
                original,
                row["reserve_amount"],
                "fixture-absence-release:" + request_id,
                "fixture-absence-source:" + request_id,
                authenticated_actor,
                "fixture-absent:" + request_id,
                now,
            )
            try:
                closure = FixtureAbsenceClosure(
                    assessment=assessment,
                    dispatch_bound=bound,
                    timed_lookup=timed,
                    original_reservation=original,
                    release=release,
                    actor_id=authenticated_actor,
                    occurred_at=now,
                )
            except ValueError:
                return None
            body = canonical(closure)
            LedgerStore(self.store).append_in_transaction(conn, release)
            evidence = "reconciliation:fixture-absence:" + digest(body)
            if current.state == OrderState.UNKNOWN:
                recovery = transition(
                    current,
                    OrderState.RECOVERY_REQUIRED,
                    now,
                    "ELAPSED_WINDOW_ABSENCE_PROVEN",
                    evidence,
                )
                self.execution._write(conn, recovery)
                current = recovery.resulting_state
            self.execution._write(
                conn,
                transition(
                    current, OrderState.EXPIRED, now, "ELAPSED_WINDOW_ABSENCE_CLOSED", evidence
                ),
            )
            conn.execute(
                "INSERT INTO ct_fixture_absence_closures(execution_request_id,digest,body,"
                "assessment_digest,bound_digest,timed_digest,release_tx_id) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    request_id,
                    digest(body),
                    body,
                    digest(canonical(assessment)),
                    digest(canonical(bound)),
                    digest(canonical(timed)),
                    release.transaction_id,
                ),
            )
            event = EventEnvelope(
                event_id="fixture-absence:" + digest(body),
                event_type="FixtureAbsenceClosed.v1",
                schema_version="1",
                occurred_at=now,
                tenant_id=request.tenant_id,
                actor_id=authenticated_actor,
                source_service="reconciliation",
                trace_id="fixture-absence:" + digest(body),
                correlation_id=request_id,
                payload=PayloadReference(
                    artifact_ref=digest(body),
                    sha256=digest(body),
                    payload_schema_ref="FixtureAbsenceClosure.v1",
                ),
            )
            self.store.append_in_transaction(conn, event, closure)
            return closure
