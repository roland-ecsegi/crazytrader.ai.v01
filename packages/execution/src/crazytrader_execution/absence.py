"""Source-first bounded fixture absence assessment; never retries/releases by itself."""

from datetime import UTC, datetime

from crazytrader_contracts.absence import FixtureAbsenceAssessment
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import ExecutionRequest, ExecutionTransition
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.risk import OwnerRiskConfiguration
from crazytrader_risk.store import RiskStore, StateUnavailable

from .account_reconciliation import FixtureAccountReconciler
from .fixture_transport import SDKFixtureTransport
from .store import ExecutionStore


class FixtureAbsenceAssessor:
    def __init__(self, execution: ExecutionStore, transport: SDKFixtureTransport) -> None:
        self.execution, self.store, self.transport = execution, execution.store, transport
        self.accounts = FixtureAccountReconciler(execution, transport)

    def assess(self, request_id: str, authenticated_actor: str) -> FixtureAbsenceAssessment:
        self.execution.require_sdk_account(request_id)
        state = self.execution.load(request_id)
        request = state.request
        if request.actor_id != authenticated_actor or request.execution_mode != "SIMULATION":
            raise StateUnavailable("absence assessment owner/simulation authority denied")
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            RiskStore(self.store).configuration(request.tenant_id, authenticated_actor)
            state = self.execution._load(conn, request_id)
            if state.state not in {OrderState.UNKNOWN, OrderState.RECOVERY_REQUIRED}:
                raise StateUnavailable("absence assessment requires owned ambiguous dispatch")
            head = self.accounts._head(conn, request.tenant_id)
            symbols = {request.symbol}
            for row in conn.execute(
                "SELECT body FROM ct_risk_configs WHERE tenant_id=%s", (request.tenant_id,)
            ).fetchall():
                symbols.update(
                    OwnerRiskConfiguration.model_validate_json(str(row["body"])).symbol_allowlist
                )
            for row in conn.execute(
                "SELECT body FROM ct_execution_requests WHERE tenant_id=%s", (request.tenant_id,)
            ).fetchall():
                symbols.add(ExecutionRequest.model_validate_json(str(row["body"])).symbol)
        if len(symbols) > 32:
            raise StateUnavailable("absence configured symbol coverage exceeds fixture reader")
        lookup = self.transport.lookup(request)
        account = self.transport.account(request, tuple(sorted(symbols)))
        # Preserve both raw signed sources before any comparison/assessment attempt.
        with self.store.connection() as conn:
            conn.execute(
                "INSERT INTO ct_fixture_order_lookups(digest,execution_request_id,body) "
                "VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (digest(canonical(lookup)), request_id, canonical(lookup)),
            )
            conn.execute(
                "INSERT INTO ct_account_read_sources(digest,tenant_id,venue_account_ref,"
                "anchor_request_id,body,observed_at) VALUES(%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (
                    digest(canonical(account)),
                    request.tenant_id,
                    request.venue_account_ref,
                    request_id,
                    canonical(account),
                    account.finished_at,
                ),
            )
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            current = self.execution._load(conn, request_id)
            findings = set()
            if self.accounts._head(conn, request.tenant_id) != head or current != state:
                findings.add("CONCURRENT_STATE")
            if state.filled_quantity != 0 or state.venue_order_id is not None:
                findings.add("KNOWN_ORDER_OR_FILL")
            if not lookup.explicitly_not_found:
                findings.add("LOOKUP_UNPROVEN")
            if not account.available:
                findings.add("ACCOUNT_UNAVAILABLE")
            else:
                try:
                    with conn.transaction():
                        findings.update(
                            self.accounts._compare(conn, account) - {"STATE_UNRESOLVED"}
                        )
                        others = conn.execute(
                            "SELECT t.body FROM ct_execution_current c "
                            "JOIN ct_execution_transitions t "
                            "ON t.transition_id=c.transition_id JOIN ct_execution_requests r "
                            "ON r.execution_request_id=c.execution_request_id "
                            "WHERE r.tenant_id=%s AND r.execution_request_id!=%s",
                            (request.tenant_id, request_id),
                        ).fetchall()
                        if any(
                            ExecutionTransition.model_validate_json(
                                str(r["body"])
                            ).resulting_state.state
                            in {
                                OrderState.SUBMITTING,
                                OrderState.SUBMITTED,
                                OrderState.UNKNOWN,
                                OrderState.RECOVERY_REQUIRED,
                                OrderState.CANCEL_PENDING,
                            }
                            for r in others
                        ):
                            findings.add("OTHER_UNRESOLVED_STATE")
                except Exception:
                    findings.add("COMPARISON_FAILED")
            now = datetime.now(UTC)
            candidate = dict(
                state=state,
                lookup=lookup,
                account=account,
                internal_head_sha256=head,
                actor_id=authenticated_actor,
                verdict="PROVEN" if not findings else "DENIED",
                findings=tuple(sorted(findings)),
                occurred_at=now,
            )
            try:
                assessment = FixtureAbsenceAssessment.model_validate(candidate)
            except ValueError:
                findings.add("SOURCE_SCOPE_OR_FRESHNESS")
                assessment = FixtureAbsenceAssessment.model_validate(
                    candidate
                    | {
                        "verdict": "DENIED",
                        "findings": tuple(sorted(findings)),
                    }
                )
            body = canonical(assessment)
            conn.execute(
                "INSERT INTO ct_fixture_absence_assessments(digest,execution_request_id,"
                "lookup_digest,account_digest,body,verdict) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    digest(body),
                    request_id,
                    digest(canonical(lookup)),
                    digest(canonical(account)),
                    body,
                    assessment.verdict,
                ),
            )
            event = EventEnvelope(
                event_id="absence-assessment:" + digest(body),
                event_type="FixtureAbsenceAssessed.v1",
                schema_version="1",
                occurred_at=now,
                tenant_id=request.tenant_id,
                actor_id=authenticated_actor,
                source_service="reconciliation",
                trace_id="absence-assessment:" + digest(body),
                correlation_id=request_id,
                payload=PayloadReference(
                    artifact_ref=digest(body),
                    sha256=digest(body),
                    payload_schema_ref="FixtureAbsenceAssessment.v1",
                ),
            )
            self.store.append_in_transaction(conn, event, assessment)
            return assessment
