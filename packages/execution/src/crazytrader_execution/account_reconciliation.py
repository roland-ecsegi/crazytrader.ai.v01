"""Source-first bounded fixture account comparison. Never grants certification."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Any

import psycopg
from crazytrader_contracts.account import (
    AccountReconciliationReport,
    Finding,
    VenueAccountRead,
    account_balances,
    history_rows,
)
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import ExecutionState, ExecutionTransition
from crazytrader_contracts.models import OrderState, decimal_input
from crazytrader_contracts.risk import OwnerRiskConfiguration
from crazytrader_ledger.attribution import positions
from crazytrader_ledger.store import LedgerStore
from crazytrader_risk.store import StateUnavailable

from .fixture_transport import SDKFixtureTransport
from .store import ExecutionStore


class FixtureAccountReconciler:
    def __init__(self, execution: ExecutionStore, transport: SDKFixtureTransport) -> None:
        self.execution, self.store, self.transport = execution, execution.store, transport

    def _head(self, conn: psycopg.Connection[dict[str, object]], tenant: str) -> str:
        rows = conn.execute(
            "SELECT digest FROM ct_ledger_transactions WHERE tenant_id=%s UNION ALL "
            "SELECT t.digest FROM ct_execution_current c JOIN ct_execution_transitions t "
            "ON t.transition_id=c.transition_id JOIN ct_execution_requests r "
            "ON r.execution_request_id=c.execution_request_id WHERE r.tenant_id=%s UNION ALL "
            "SELECT digest FROM ct_risk_configs WHERE tenant_id=%s UNION ALL "
            "SELECT encode(sha256(convert_to(config_id,'UTF8')),'hex') digest "
            "FROM ct_risk_active_configs WHERE tenant_id=%s ORDER BY digest",
            (tenant, tenant, tenant, tenant),
        ).fetchall()
        return digest(json.dumps([str(r["digest"]) for r in rows], separators=(",", ":")))

    def run(self, request_id: str) -> AccountReconciliationReport:
        self.execution.require_sdk_account(request_id)
        anchor = self.execution.load(request_id)
        request = anchor.request
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            head = self._head(conn, request.tenant_id)
            configs = conn.execute(
                "SELECT body FROM ct_risk_configs WHERE tenant_id=%s", (request.tenant_id,)
            ).fetchall()
            symbols = {request.symbol}
            for row in configs:
                symbols.update(
                    OwnerRiskConfiguration.model_validate_json(str(row["body"])).symbol_allowlist
                )
            registered = conn.execute(
                "SELECT body FROM ct_execution_requests WHERE tenant_id=%s", (request.tenant_id,)
            ).fetchall()
            for row in registered:
                symbols.add(json.loads(str(row["body"]))["symbol"])
        if len(symbols) > 32:
            raise StateUnavailable("configured account symbol scope exceeds bounded fixture reader")
        source = self.transport.account(request, tuple(sorted(symbols)))
        source = VenueAccountRead.model_validate(source.model_dump())
        if (
            source.tenant_id,
            source.venue_account_ref,
            source.anchor_request_id,
            source.anchor_request_sha256,
        ) != (request.tenant_id, request.venue_account_ref, request_id, digest(canonical(request))):
            raise StateUnavailable("account read ownership mismatch")
        body, fingerprint = canonical(source), digest(canonical(source))
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            # Preserve captured truth even when comparison fails or the internal head moved.
            conn.execute(
                "INSERT INTO "
                "ct_account_read_sources(digest,tenant_id,venue_account_ref,"
                "anchor_request_id,body,observed_at) "
                "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    fingerprint,
                    request.tenant_id,
                    request.venue_account_ref,
                    request_id,
                    body,
                    source.finished_at,
                ),
            )
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            findings: set[Finding] = set()
            if self._head(conn, request.tenant_id) != head:
                findings.add("CONCURRENT_STATE")
            if not source.available:
                findings.add("SOURCE_UNAVAILABLE")
            else:
                try:
                    with conn.transaction():
                        findings.update(self._compare(conn, source))
                except Exception:
                    findings.add("COMPARISON_FAILED")
            if source.finished_at - source.started_at > timedelta(
                seconds=10
            ) or not source.finished_at <= datetime.now(UTC) <= source.finished_at + timedelta(
                seconds=5
            ):
                findings.add("SOURCE_UNAVAILABLE")
            report = AccountReconciliationReport(
                tenant_id=request.tenant_id,
                actor_id=request.actor_id,
                venue_account_ref=request.venue_account_ref,
                source_sha256=fingerprint,
                internal_head_sha256=head,
                status="UNAVAILABLE"
                if not source.available
                or "COMPARISON_FAILED" in findings
                or "SOURCE_UNAVAILABLE" in findings
                else "MISMATCH"
                if findings
                else "MATCHED",
                findings=tuple(sorted(findings)),
                occurred_at=datetime.now(UTC),
            )
            report_body, report_digest = canonical(report), digest(canonical(report))
            conn.execute(
                "INSERT INTO "
                "ct_account_reconciliation_reports(digest,tenant_id,source_digest,"
                "blocks_new_risk,body) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (report_digest, request.tenant_id, fingerprint, bool(findings), report_body),
            )
            event = EventEnvelope(
                event_id="account-recon:" + report_digest,
                event_type="AccountReconciliationChecked.v1"
                if findings
                else "AccountReconciliationMatched.v1",
                schema_version="1",
                occurred_at=report.occurred_at,
                tenant_id=request.tenant_id,
                source_service="reconciliation",
                actor_id=request.actor_id,
                trace_id="account-recon:" + report_digest,
                correlation_id=request_id,
                payload=PayloadReference(
                    artifact_ref=report_digest,
                    sha256=report_digest,
                    payload_schema_ref="AccountReconciliationReport.v1",
                ),
            )
            self.store.append_in_transaction(conn, event, report)
            if findings:
                fault = digest(
                    json.dumps(
                        [
                            request.tenant_id,
                            request.venue_account_ref,
                            head,
                            report.findings,
                            source.raw_json,
                        ],
                        separators=(",", ":"),
                    )
                )
                fault_id = "account-fault:" + fault
                if (
                    conn.execute(
                        "SELECT 1 FROM ct_events WHERE event_id=%s", (fault_id,)
                    ).fetchone()
                    is None
                ):
                    critical = EventEnvelope.model_validate(
                        event.model_dump()
                        | {
                            "event_id": fault_id,
                            "event_type": "AccountReconciliationMismatch.v1",
                            "trace_id": fault_id,
                        }
                    )
                    self.store.append_in_transaction(conn, critical, report)
            return report

    def _compare(
        self, conn: psycopg.Connection[dict[str, object]], source: VenueAccountRead
    ) -> set[Finding]:
        findings: set[Finding] = set()
        raw = source.raw()
        after = account_balances(raw["after"])
        if raw["before"] != raw["after"]:
            findings.add("SOURCE_CHANGED")
        for account in (raw["before"], raw["after"]):
            if (
                account.get("canTrade") is not True
                or account.get("canWithdraw") is not False
                or account.get("accountType") != "SPOT"
                or account.get("permissions") != ["SPOT"]
            ):
                findings.add("PERMISSION_MISMATCH")
        rows = conn.execute(
            "SELECT asset,sum(amount) amount FROM ct_ledger_postings WHERE tenant_id=%s "
            "AND account IN('AVAILABLE','INVENTORY','RESERVED') GROUP BY asset",
            (source.tenant_id,),
        ).fetchall()
        internal = {str(r["asset"]): r["amount"] for r in rows}
        if any(
            internal.get(asset, Decimal(0)) != after.get(asset, Decimal(0))
            for asset in set(internal) | set(after)
        ):
            findings.add("BALANCE_MISMATCH")
        states = [
            ExecutionTransition.model_validate_json(str(r["body"])).resulting_state
            for r in conn.execute(
                "SELECT t.body FROM ct_execution_current c JOIN "
                "ct_execution_transitions t ON t.transition_id=c.transition_id "
                "JOIN ct_execution_requests r ON "
                "r.execution_request_id=c.execution_request_id WHERE r.tenant_id=%s",
                (source.tenant_id,),
            ).fetchall()
        ]
        if any(s.request.venue_account_ref != source.venue_account_ref for s in states):
            findings.add("UNSUPPORTED_ACCOUNT_SCOPE")
        known = {
            (s.request.symbol, s.venue_order_id): s for s in states if s.venue_order_id is not None
        }
        orders = [
            r
            for symbol in source.symbols
            for r in history_rows(raw["history"][symbol]["orders"], "orderId", symbol)
        ]
        observed = {(r["symbol"], str(r["orderId"])): r for r in orders}
        open_keys = {(r["symbol"], str(r["orderId"])) for r in raw["open"]}
        expected_open = {
            key for key, r in observed.items() if r["status"] in {"NEW", "PARTIALLY_FILLED"}
        }
        if open_keys != expected_open:
            findings.add("ORDER_MISMATCH")
        for row in orders + raw["open"]:
            key = row["symbol"], str(row["orderId"])
            current = known.get(key)
            if current is None:
                findings.add("UNOWNED_ORDER")
            elif not self._order_matches(current, row):
                findings.add("ORDER_MISMATCH")
        for current in states:
            if current.state in {
                OrderState.SUBMITTING,
                OrderState.SUBMITTED,
                OrderState.UNKNOWN,
                OrderState.RECOVERY_REQUIRED,
                OrderState.CANCEL_PENDING,
            }:
                findings.add("STATE_UNRESOLVED")
            if (
                current.venue_order_id is not None
                and (current.request.symbol, current.venue_order_id) not in observed
            ):
                findings.add("ORDER_MISMATCH")
            reservation = conn.execute(
                "SELECT reserve_asset,reserve_amount FROM ct_execution_reservations "
                "WHERE execution_request_id=%s",
                (current.request.execution_request_id,),
            ).fetchone()
            if reservation is not None:
                amount_row = conn.execute(
                    "SELECT COALESCE(sum(p.amount),0) amount FROM ct_ledger_postings p "
                    "JOIN ct_ledger_transactions t USING(transaction_id) "
                    "WHERE p.tenant_id=%s AND p.portfolio_id=%s AND p.account='RESERVED' "
                    "AND p.asset=%s AND t.related_order_id=%s",
                    (
                        source.tenant_id,
                        current.request.portfolio_id,
                        reservation["reserve_asset"],
                        current.request.order_id,
                    ),
                ).fetchone()
                if amount_row is None:
                    raise StateUnavailable("reservation accounting unavailable")
                amount = amount_row["amount"]
                terminal = current.state in {
                    OrderState.FILLED,
                    OrderState.CANCELLED,
                    OrderState.EXPIRED,
                    OrderState.REJECTED,
                }
                with localcontext() as exact:
                    exact.prec = 100
                    expected_reserved = (
                        Decimal(0)
                        if terminal
                        else decimal_input(str(reservation["reserve_amount"]))
                    )
                    if not terminal and current.request.side == "SELL":
                        for venue_fill in history_rows(
                            raw["history"][current.request.symbol]["fills"],
                            "id",
                            current.request.symbol,
                        ):
                            if str(venue_fill["orderId"]) == current.venue_order_id:
                                expected_reserved -= decimal_input(venue_fill["qty"])
                                if venue_fill["commissionAsset"] == reservation["reserve_asset"]:
                                    expected_reserved -= decimal_input(venue_fill["commission"])
                    elif not terminal:
                        findings.add("UNSUPPORTED_ACCOUNT_SCOPE")
                if amount != expected_reserved or expected_reserved < 0:
                    findings.add("RESERVATION_MISMATCH")
            elif current.state not in {
                OrderState.CREATED,
                OrderState.RISK_PENDING,
                OrderState.DENIED,
            }:
                findings.add("RESERVATION_MISMATCH")
        fills = [
            r
            for symbol in source.symbols
            for r in history_rows(raw["history"][symbol]["fills"], "id", symbol)
        ]
        stored_rows = conn.execute(
            "SELECT symbol,raw_trade_id,body,digest FROM ct_execution_fills WHERE "
            "tenant_id=%s AND venue_account_ref=%s",
            (source.tenant_id, source.venue_account_ref),
        ).fetchall()
        stored = {}
        for row in stored_rows:
            if digest(str(row["body"])) != row["digest"]:
                findings.add("FILL_MISMATCH")
            stored[(str(row["symbol"]), int(str(row["raw_trade_id"])))] = json.loads(
                str(row["body"])
            )
        seen = set()
        sums: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
        with localcontext() as exact:
            exact.prec = 100
            for row in fills:
                fill_key = row["symbol"], row["id"]
                seen.add(fill_key)
                previous = stored.get(fill_key)
                if previous is None:
                    findings.add("UNPOSTED_FILL")
                else:
                    identity = previous.get("identity", previous)
                    fill = identity["fill"]
                    timestamp = datetime.fromisoformat(fill["timestamp"].replace("Z", "+00:00"))
                    epoch = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=row["time"])
                    if timestamp != epoch:
                        findings.add("FILL_MISMATCH")
                    quote = (
                        decimal_input(previous["quote_quantity"])
                        if "quote_quantity" in previous
                        else decimal_input(fill["quantity"]) * decimal_input(fill["price"])
                    )
                    if (
                        str(row["orderId"]),
                        row["isBuyer"],
                        decimal_input(row["qty"]),
                        decimal_input(row["price"]),
                        decimal_input(row["quoteQty"]),
                        decimal_input(row["commission"]),
                        row["commissionAsset"],
                    ) != (
                        identity["venue_order_id"],
                        identity["side"] == "BUY",
                        decimal_input(fill["quantity"]),
                        decimal_input(fill["price"]),
                        quote,
                        decimal_input(fill["fee_amount"]),
                        fill["fee_asset"],
                    ):
                        findings.add("FILL_MISMATCH")
                order_key = row["symbol"], str(row["orderId"])
                quantity, quote = sums.get(order_key, (Decimal(0), Decimal(0)))
                sums[order_key] = (
                    quantity + decimal_input(row["qty"]),
                    quote + decimal_input(row["quoteQty"]),
                )
            for key, row in observed.items():
                quantity, quote = sums.get(key, (Decimal(0), Decimal(0)))
                if quantity != decimal_input(row["executedQty"]):
                    findings.add("FILL_MISMATCH")
                if quote != decimal_input(row["cummulativeQuoteQty"]):
                    findings.add("QUOTE_MISMATCH")
        if set(stored) != seen:
            findings.add("FILL_MISMATCH")
        ledger = LedgerStore(self.store)
        history = ledger.history(source.tenant_id)
        portfolios = {s.request.portfolio_id for s in states}
        for portfolio in portfolios:
            try:
                positions(history, source.tenant_id, portfolio, source.finished_at)
            except ValueError:
                findings.add("ATTRIBUTION_MISMATCH")
        return findings

    def _order_matches(self, current: ExecutionState, row: dict[str, Any]) -> bool:
        request = current.request
        statuses = {
            OrderState.ACKNOWLEDGED: "NEW",
            OrderState.PARTIALLY_FILLED: "PARTIALLY_FILLED",
            OrderState.FILLED: "FILLED",
            OrderState.CANCELLED: "CANCELED",
            OrderState.EXPIRED: "EXPIRED",
            OrderState.REJECTED: "REJECTED",
        }
        return (
            row["clientOrderId"] == request.client_order_id
            and row["side"] == request.side
            and row.get("type") == request.order_type
            and decimal_input(row["origQty"]) == request.quantity
            and decimal_input(row["executedQty"]) == current.filled_quantity
            and statuses.get(current.state) == row["status"]
        )
