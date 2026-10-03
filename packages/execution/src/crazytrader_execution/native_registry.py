"""Owned native simulation admission/source persistence; no financial completion claim."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, localcontext

import psycopg
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import NativeSimulationAdmission, NativeSimulationResultRecord
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.risk import RiskEvaluationRecord
from crazytrader_contracts.simulation import (
    NativeSimulationJob,
    NativeSimulationReceipt,
    SimulationCostProfile,
)
from crazytrader_contracts.venue_rules import VenueRuleReceipt
from crazytrader_ledger.store import LedgerStore
from crazytrader_platform.storage import ConflictError
from crazytrader_risk.store import StateUnavailable

from .native_transport import NativeSimulationTransport
from .state import transition
from .store import ExecutionStore


class NativeSimulationRegistry:
    def __init__(self, execution: ExecutionStore) -> None:
        self.execution, self.store = execution, execution.store

    def admission(self, request_id: str) -> NativeSimulationAdmission:
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT body,digest FROM ct_native_simulation_jobs WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
        if row is None:
            raise StateUnavailable("owned native admission unavailable")
        admission = NativeSimulationAdmission.model_validate_json(str(row["body"]))
        if digest(canonical(admission)) != row["digest"]:
            raise ConflictError("native admission source corrupted")
        return admission

    def admit(
        self, request_id: str, costs: SimulationCostProfile, now: datetime
    ) -> NativeSimulationAdmission:
        costs = SimulationCostProfile.model_validate(costs.model_dump())
        current = self.execution.load(request_id)
        request = current.request
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            existing = conn.execute(
                "SELECT body FROM ct_native_simulation_jobs WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if existing is not None:
                saved = self.admission(request_id)
                if saved.request != request or saved.job.costs != costs:
                    raise ConflictError("native admission immutable collision")
                return saved
            current = self.execution._load(conn, request_id)
            if current.state != OrderState.AUTHORIZED:
                raise StateUnavailable("native admission requires an unsent authorized request")
            # A simulated account chooses one backend; do not reinterpret SDK venue truth.
            prior_sdk = conn.execute(
                "SELECT 1 FROM ct_execution_requests r JOIN ct_execution_current c"
                " USING(execution_request_id) "
                "WHERE r.tenant_id=%s AND r.venue_account_ref=%s "
                "AND NOT EXISTS(SELECT 1 FROM ct_native_simulation_jobs n WHERE n."
                "execution_request_id=r.execution_request_id) "
                "AND (c.state IN('SUBMITTING','SUBMITTED','ACKNOWLEDGED','PARTIALL"
                "Y_FILLED','FILLED','CANCEL_PENDING','CANCELLED','UNKNOWN','RECOVE"
                "RY_REQUIRED','REJECTED') "
                "OR EXISTS(SELECT 1 FROM ct_fixture_dispatch_bounds d WHERE d.execution_request_id="
                "r.execution_request_id) "
                "OR EXISTS(SELECT 1 FROM ct_execution_observations v WHERE v.execu"
                "tion_request_id=r.execution_request_id)) LIMIT 1",
                (request.tenant_id, request.venue_account_ref),
            ).fetchone()
            if prior_sdk is not None:
                raise StateUnavailable("simulated account already belongs to SDK fixture backend")
            proof = conn.execute(
                "SELECT * FROM ct_execution_reservations WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if proof is None or proof["ledger_head_sha256"] != self.execution._journal_head(
                conn, request.tenant_id
            ):
                raise StateUnavailable("native starting custody proof changed")
            row = conn.execute(
                "SELECT body,digest FROM ct_venue_rule_receipts WHERE digest=%s",
                (proof["venue_rules_digest"],),
            ).fetchone()
            if row is None:
                raise StateUnavailable("native full rules unavailable")
            rules = VenueRuleReceipt.model_validate_json(str(row["body"]))
            if digest(canonical(rules)) != row["digest"]:
                raise ConflictError("native full rules corrupted")
            risk_row = conn.execute(
                "SELECT body FROM ct_risk_evaluations WHERE record_digest=%s",
                (request.risk_record_sha256,),
            ).fetchone()
            if risk_row is None:
                raise StateUnavailable("native approved reference unavailable")
            risk = RiskEvaluationRecord.model_validate_json(str(risk_row["body"]))
            if digest(canonical(risk)) != request.risk_record_sha256 or risk.context.price is None:
                raise StateUnavailable("native approved reference corrupted or unknown")
            snapshot = LedgerStore(self.store).snapshot(
                request.tenant_id, request.portfolio_id, now
            )
            with localcontext() as exact:
                exact.prec = 100
                totals = {
                    b.asset: b.available + b.inventory + b.reserved for b in snapshot.balances
                }
            symbol = rules.rules.symbol_record()
            job = NativeSimulationJob(
                execution_request_id=request_id,
                order_id=request.order_id,
                request_sha256=digest(canonical(request)),
                tenant_id=request.tenant_id,
                portfolio_id=request.portfolio_id,
                venue_account_ref=request.venue_account_ref,
                client_order_id=request.client_order_id,
                symbol=request.symbol,
                quantity=request.quantity,
                reference_price=risk.context.price,
                reference_risk_record_sha256=request.risk_record_sha256,
                ledger_head_sha256=str(proof["ledger_head_sha256"]),
                venue_rules=rules,
                costs=costs,
                starting_base=totals.get(str(symbol["baseAsset"]), Decimal(0)),
                starting_quote=totals.get(str(symbol["quoteAsset"]), Decimal(0)),
                event_at=now,
            )
            admission = NativeSimulationAdmission(
                request=request, job=job, actor_id=request.actor_id, occurred_at=now
            )
            conn.execute(
                "INSERT INTO ct_native_simulation_jobs(execution_request_id,tenant"
                "_id,venue_account_ref,digest,job_digest,body) VALUES(%s,%s,%s,%s,"
                "%s,%s)",
                (
                    request_id,
                    request.tenant_id,
                    request.venue_account_ref,
                    digest(canonical(admission)),
                    digest(canonical(job)),
                    canonical(admission),
                ),
            )
            self._event(
                conn,
                "NativeSimulationAdmitted.v1",
                admission,
                request.tenant_id,
                request.actor_id,
                now,
                request_id,
            )
            return admission

    def record(self, receipt: NativeSimulationReceipt) -> NativeSimulationResultRecord:
        receipt = NativeSimulationReceipt.model_validate(receipt.model_dump())
        admission = self.admission(receipt.job.execution_request_id)
        record = NativeSimulationResultRecord(admission=admission, receipt=receipt)
        request = admission.request
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            current = self.execution._load(conn, request.execution_request_id)
            if current.state == OrderState.AUTHORIZED:
                raise StateUnavailable("native receipt has no durable dispatch claim")
            conn.execute(
                "INSERT INTO ct_native_simulation_receipts(digest,execution_reques"
                "t_id,job_digest,body,available,observed_at) VALUES(%s,%s,%s,%s,%s"
                ",%s) ON CONFLICT DO NOTHING",
                (
                    digest(canonical(record)),
                    request.execution_request_id,
                    receipt.job_sha256,
                    canonical(record),
                    receipt.available,
                    receipt.observed_at,
                ),
            )
            self._event(
                conn,
                "NativeSimulationReceiptRecorded.v1",
                record,
                request.tenant_id,
                request.actor_id,
                receipt.observed_at,
                request.execution_request_id,
            )
            if current.state == OrderState.SUBMITTING:
                change = transition(
                    current,
                    OrderState.UNKNOWN,
                    receipt.observed_at,
                    "NATIVE_RESULT_REQUIRES_FINANCIAL_RECONCILIATION",
                    "nautilus-result:" + digest(canonical(record)),
                )
                self.execution._write(conn, change)
        return record

    def _event(
        self,
        conn: psycopg.Connection[dict[str, object]],
        event_type: str,
        payload: NativeSimulationAdmission | NativeSimulationResultRecord,
        tenant: str,
        actor: str,
        now: datetime,
        request_id: str,
    ) -> None:
        fingerprint = digest(canonical(payload))
        event = EventEnvelope(
            event_id="native-source:" + fingerprint,
            event_type=event_type,
            schema_version="1",
            occurred_at=now,
            tenant_id=tenant,
            actor_id=actor,
            source_service="execution",
            trace_id="native-source:" + fingerprint,
            correlation_id=request_id,
            payload=PayloadReference(
                artifact_ref=fingerprint,
                sha256=fingerprint,
                payload_schema_ref=type(payload).__name__ + ".v1",
            ),
        )
        self.store.append_in_transaction(conn, event, payload)


class NativeSimulationRunner:
    def __init__(
        self,
        registry: NativeSimulationRegistry,
        transport: NativeSimulationTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self.registry, self.execution, self.transport, self.clock = (
            registry,
            registry.execution,
            transport,
            clock,
        )

    def submit_once(
        self, request_id: str, costs: SimulationCostProfile, *, interrupt_after_result: bool = False
    ) -> NativeSimulationResultRecord | None:
        admission = self.registry.admit(request_id, costs, self.clock())
        claim = self.execution.claim_submission(request_id, self.clock(), native=True)
        if claim is None:
            return None
        receipt = self.transport.simulate(
            admission.job, interrupt_after_result=interrupt_after_result
        )
        return self.registry.record(receipt)

    def recover_source(self, request_id: str) -> NativeSimulationResultRecord | None:
        admission = self.registry.admission(request_id)
        self.execution.recover_interrupted_submission(request_id, self.clock())
        receipt = self.transport.recover_result(admission.job)
        if receipt is None:
            return None
        return self.registry.record(receipt)
