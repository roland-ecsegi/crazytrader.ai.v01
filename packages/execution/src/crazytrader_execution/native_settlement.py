"""Source-first native simulation journal/state completion and durable fault containment."""

import json
from datetime import datetime

import psycopg
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import ExecutionState, NativeSimulationResultRecord
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.native_fills import (
    NativeSimulationFill,
    NativeSimulationIncident,
    sourced_fill,
)
from crazytrader_ledger.commands import account_native_fill
from crazytrader_ledger.store import LedgerStore
from crazytrader_platform.storage import ConflictError
from crazytrader_risk.store import StateUnavailable

from .native_registry import NativeSimulationRegistry
from .state import transition


class NativeSimulationSettlement:
    def __init__(self, registry: NativeSimulationRegistry) -> None:
        self.registry, self.execution, self.store = registry, registry.execution, registry.store

    def apply(self, record: NativeSimulationResultRecord, now: datetime) -> ExecutionState:
        record = NativeSimulationResultRecord.model_validate(record.model_dump())
        # This commit precedes every financial attempt, preserving raw truth on DB interruption.
        saved = self.registry.record(record.receipt)
        if saved != record:
            raise ConflictError("native settlement admission differs from original source")
        request, receipt = record.admission.request, record.receipt
        source = digest(canonical(record))
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            current = self.execution._load(conn, request.execution_request_id)
            if now < current.updated_at or now < receipt.observed_at:
                raise StateUnavailable("native reconciliation clock moved backwards")
            posted = conn.execute(
                "SELECT receipt_digest FROM ct_native_simulation_postings "
                "WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()
            if posted is not None:
                if posted["receipt_digest"] != source or current.state != OrderState.FILLED:
                    self._incident(conn, record, "FINANCIAL_ATTRIBUTION_FAILED", now)
                return current
            if not receipt.available:
                self._incident(conn, record, "SOURCE_UNAVAILABLE", now)
                return current
            if current.state not in {OrderState.UNKNOWN, OrderState.RECOVERY_REQUIRED}:
                raise StateUnavailable("native financial settlement requires owned recovery state")
            original = current
            try:
                with conn.transaction():
                    fill, gross = sourced_fill(receipt)
                    evidence = NativeSimulationFill(
                        receipt=receipt, fill=fill, quote_quantity=gross
                    )
                    symbol = receipt.job.venue_rules.rules.symbol_record()
                    tx = account_native_fill(
                        "native-tx:" + digest(canonical(evidence)),
                        request.tenant_id,
                        "native-financial-source:" + source,
                        request.actor_id,
                        "native-result:" + source,
                        fill.timestamp,
                        request.portfolio_id,
                        request.side,
                        str(symbol["baseAsset"]),
                        str(symbol["quoteAsset"]),
                        evidence,
                        "native-result:" + source,
                    )
                    LedgerStore(self.store).append_in_transaction(conn, tx)
                    if current.state == OrderState.UNKNOWN:
                        recovery = transition(
                            current,
                            OrderState.RECOVERY_REQUIRED,
                            now,
                            "NATIVE_COMPLETE_FILL_SOURCE",
                            "reconciliation:" + source,
                        )
                        self.execution._write(conn, recovery)
                        current = recovery.resulting_state
                    raw = json.loads(receipt.raw_json or "")
                    complete = transition(
                        current,
                        OrderState.FILLED,
                        now,
                        "NATIVE_CANONICAL_FILL_SETTLED",
                        "reconciliation:" + source,
                        filled=request.quantity,
                        venue_id=raw["fills"][0]["venue_order_id"],
                    )
                    self.execution._write(conn, complete)
                    conn.execute(
                        "INSERT INTO ct_native_simulation_postings(execution_request_id,"
                        "receipt_digest,ledger_tx_id) VALUES(%s,%s,%s)",
                        (request.execution_request_id, source, tx.transaction_id),
                    )
                    # Check deferred balance/source/state constraints inside the savepoint.
                    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    conn.execute("SET CONSTRAINTS ALL DEFERRED")
                    return complete.resulting_state
            except (
                ValueError,
                ConflictError,
                psycopg.IntegrityError,
                psycopg.errors.RaiseException,
            ):
                self._incident(conn, record, "FINANCIAL_ATTRIBUTION_FAILED", now)
                return original

    def _incident(
        self,
        conn: psycopg.Connection[dict[str, object]],
        record: NativeSimulationResultRecord,
        reason: str,
        now: datetime,
    ) -> None:
        request = record.admission.request
        source = digest(canonical(record))
        key = "native-incident:" + digest(
            json.dumps(
                [
                    record.receipt.job_sha256,
                    record.receipt.available,
                    record.receipt.raw_json,
                    reason,
                ],
                separators=(",", ":"),
            )
        )
        prior = conn.execute(
            "SELECT 1 FROM ct_native_simulation_incidents WHERE incident_id=%s",
            (key,),
        ).fetchone()
        if prior is not None:
            return
        incident = NativeSimulationIncident.model_validate(
            dict(
                incident_id=key,
                tenant_id=request.tenant_id,
                actor_id=request.actor_id,
                execution_request_id=request.execution_request_id,
                receipt_digest=source,
                reason=reason,
                occurred_at=now,
            )
        )
        body = canonical(incident)
        conn.execute(
            "INSERT INTO ct_native_simulation_incidents(incident_id,tenant_id,"
            "execution_request_id,receipt_digest,body,digest) VALUES(%s,%s,%s,%s,%s,%s)",
            (key, request.tenant_id, request.execution_request_id, source, body, digest(body)),
        )
        event = EventEnvelope(
            event_id=key,
            event_type="NativeSimulationCriticalMismatch.v1",
            schema_version="1",
            occurred_at=now,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            source_service="reconciliation",
            trace_id=key,
            correlation_id=request.execution_request_id,
            payload=PayloadReference(
                artifact_ref=digest(body),
                sha256=digest(body),
                payload_schema_ref="NativeSimulationIncident.v1",
            ),
        )
        self.store.append_in_transaction(conn, event, incident)
