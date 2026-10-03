"""Canonical PostgreSQL journal. Every posting/event/outbox is one transaction."""

from datetime import datetime
from decimal import Decimal, localcontext

import psycopg
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import NativeSimulationResultRecord
from crazytrader_contracts.ledger import (
    Account,
    AssetBalance,
    JournalTransaction,
    NativeFillLedgerTransaction,
    PortfolioSnapshot,
    VenueFillLedgerTransaction,
)
from crazytrader_contracts.models import Portfolio
from crazytrader_contracts.venue_rules import VenueRuleReceipt
from crazytrader_platform.storage import ConflictError, EventStore, canonical, digest
from pydantic import TypeAdapter

JOURNAL: TypeAdapter[JournalTransaction] = TypeAdapter(JournalTransaction)


class InsufficientFunds(ValueError):
    """An append would overdraw a controlled account."""


class LedgerStore:
    def __init__(self, store: EventStore) -> None:
        self.store = store

    def register(self, portfolio: Portfolio) -> bool:
        body = canonical(portfolio)
        with self.store.connection() as conn:
            inserted = conn.execute(
                "INSERT INTO ct_portfolios(portfolio_id,tenant_id,mode,digest,body) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING portfolio_id",
                (
                    portfolio.portfolio_id,
                    portfolio.tenant_id,
                    portfolio.mode.value,
                    digest(body),
                    body,
                ),
            ).fetchone()
            if inserted is not None:
                return True
            row = conn.execute(
                "SELECT digest FROM ct_portfolios WHERE portfolio_id=%s", (portfolio.portfolio_id,)
            ).fetchone()
            if row is None or row["digest"] != digest(body):
                raise ConflictError("portfolio immutable ownership/content collision")
            return False

    def balance(self, tenant: str, portfolio: str, account: Account, asset: str) -> Decimal:
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(sum(amount),0) AS balance FROM ct_ledger_postings "
                "WHERE tenant_id=%s AND portfolio_id=%s AND account=%s AND asset=%s",
                (tenant, portfolio, account, asset),
            ).fetchone()
            if row is None or not isinstance(row["balance"], Decimal):
                raise RuntimeError("accounting query unavailable")
            return row["balance"]

    def append(self, transaction: JournalTransaction) -> bool:
        transaction = JOURNAL.validate_python(transaction.model_dump())
        with self.store.connection() as conn:
            return self.append_in_transaction(conn, transaction)

    def append_in_transaction(
        self, conn: psycopg.Connection[dict[str, object]], transaction: JournalTransaction
    ) -> bool:
        """Shared transaction for execution reservation/fill plus its durable state."""
        transaction = JOURNAL.validate_python(transaction.model_dump())
        body = canonical(transaction)
        fingerprint = digest(body)
        if isinstance(transaction, NativeFillLedgerTransaction):
            job = transaction.native_evidence.receipt.job
            rows = conn.execute(
                "SELECT body,digest FROM ct_native_simulation_receipts "
                "WHERE execution_request_id=%s AND available",
                (job.execution_request_id,),
            ).fetchall()
            owned = False
            for native_row in rows:
                source = NativeSimulationResultRecord.model_validate_json(str(native_row["body"]))
                if digest(canonical(source)) != native_row["digest"]:
                    raise ConflictError("native durable financial source corrupted")
                if source.receipt == transaction.native_evidence.receipt:
                    symbol = job.venue_rules.rules.symbol_record()
                    owned = (
                        transaction.tenant_id == job.tenant_id
                        and transaction.actor_id == source.admission.actor_id
                        and transaction.base_asset == symbol["baseAsset"]
                        and transaction.quote_asset == symbol["quoteAsset"]
                        and transaction.related_order_id == job.order_id
                        and transaction.timestamp == job.event_at
                        and all(
                            p.portfolio_id in {None, job.portfolio_id} for p in transaction.postings
                        )
                    )
            if not owned:
                raise ConflictError("native fill requires original owned durable source")
        if isinstance(transaction, VenueFillLedgerTransaction):
            row = conn.execute(
                "SELECT body,digest FROM ct_venue_rule_receipts WHERE digest=%s",
                (transaction.quote_evidence.venue_rule_receipt_sha256,),
            ).fetchone()
            if row is None:
                raise ValueError("actual quote fill requires durable venue precision proof")
            receipt = VenueRuleReceipt.model_validate_json(str(row["body"]))
            symbol = receipt.rules.symbol_record()
            if digest(canonical(receipt)) != row["digest"] or (
                receipt.tenant_id,
                receipt.rules.symbol,
                receipt.rules.quote_precision,
                symbol["baseAsset"],
                symbol["quoteAsset"],
            ) != (
                transaction.tenant_id,
                transaction.quote_evidence.identity.symbol,
                transaction.quote_evidence.quote_precision,
                transaction.base_asset,
                transaction.quote_asset,
            ):
                raise ConflictError("actual quote fill precision/asset ownership mismatch")
        event = EventEnvelope(
            event_id="ledger:" + digest(transaction.transaction_id),
            event_type=(
                "LedgerNativeFillAppended.v1"
                if isinstance(transaction, NativeFillLedgerTransaction)
                else "LedgerVenueFillAppended.v1"
                if isinstance(transaction, VenueFillLedgerTransaction)
                else "LedgerEntryAppended.v1"
            ),
            schema_version="1",
            occurred_at=transaction.timestamp,
            tenant_id=transaction.tenant_id,
            source_service="ledger",
            actor_id=transaction.actor_id,
            trace_id="ledger:" + digest(transaction.transaction_id),
            correlation_id=transaction.source_event_id,
            payload=PayloadReference(
                artifact_ref=fingerprint,
                sha256=fingerprint,
                payload_schema_ref=type(transaction).__name__ + ".v1",
            ),
        )
        # Tenant-wide serialization is intentionally conservative for Enterprise Local.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("ledger:" + transaction.tenant_id,),
        )
        previous = conn.execute(
            "SELECT transaction_id,digest FROM ct_ledger_transactions WHERE "
            "transaction_id=%s OR (tenant_id=%s AND source_event_id=%s) "
            "OR (tenant_id=%s AND transaction_type='FILL' AND related_fill_id=%s) "
            "OR (tenant_id=%s AND transaction_type='RESERVATION' AND related_order_id=%s) "
            "OR (tenant_id=%s AND correction_of_id=%s)",
            (
                transaction.transaction_id,
                transaction.tenant_id,
                transaction.source_event_id,
                transaction.tenant_id,
                transaction.related_fill_id if transaction.transaction_type == "FILL" else None,
                transaction.tenant_id,
                transaction.related_order_id
                if transaction.transaction_type == "RESERVATION"
                else None,
                transaction.tenant_id,
                transaction.correction_of_id,
            ),
        ).fetchall()
        if previous:
            if len(previous) != 1 or previous[0] != {
                "transaction_id": transaction.transaction_id,
                "digest": fingerprint,
            }:
                raise ConflictError("transaction/source ID content collision")
            return False
        conn.execute(
            "INSERT INTO ct_ledger_transactions "
            "(transaction_id,tenant_id,source_event_id,digest,body,transaction_type,"
            "correction_of_id,related_order_id,related_fill_id) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                transaction.transaction_id,
                transaction.tenant_id,
                transaction.source_event_id,
                fingerprint,
                body,
                transaction.transaction_type,
                transaction.correction_of_id,
                transaction.related_order_id,
                transaction.related_fill_id,
            ),
        )
        for posting in transaction.postings:
            conn.execute(
                "INSERT INTO ct_ledger_postings "
                "(posting_id,transaction_id,tenant_id,portfolio_id,account,asset,amount,"
                "valuation_ref) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    posting.posting_id,
                    transaction.transaction_id,
                    transaction.tenant_id,
                    posting.portfolio_id,
                    posting.account,
                    posting.asset,
                    posting.amount,
                    posting.valuation_ref,
                ),
            )
        negative = conn.execute(
            "SELECT 1 FROM ct_ledger_postings WHERE tenant_id=%s "
            "AND account IN ('AVAILABLE','RESERVED','INVENTORY') "
            "GROUP BY portfolio_id,account,asset HAVING sum(amount)<0 LIMIT 1",
            (transaction.tenant_id,),
        ).fetchone()
        if negative:
            raise InsufficientFunds("insufficient controlled account funds")
        negative_reservation = conn.execute(
            "SELECT 1 FROM ct_ledger_postings p "
            "JOIN ct_ledger_transactions t USING(transaction_id) "
            "WHERE p.tenant_id=%s AND p.account='RESERVED' "
            "GROUP BY p.portfolio_id,p.asset,t.related_order_id "
            "HAVING sum(p.amount)<0 OR t.related_order_id IS NULL LIMIT 1",
            (transaction.tenant_id,),
        ).fetchone()
        if negative_reservation:
            raise InsufficientFunds("insufficient order-attributed reservation")
        self.store.append_in_transaction(conn, event, transaction)
        return True

    def history(self, tenant: str) -> tuple[JournalTransaction, ...]:
        with self.store.connection() as conn:
            rows = conn.execute(
                "SELECT body,digest FROM ct_ledger_transactions WHERE tenant_id=%s "
                "ORDER BY recorded_at,transaction_id",
                (tenant,),
            ).fetchall()
            transactions = []
            for row in rows:
                transaction = JOURNAL.validate_json(str(row["body"]))
                if digest(canonical(transaction)) != row["digest"]:
                    raise ConflictError("ledger history integrity failure")
                transactions.append(transaction)
            return tuple(transactions)

    def snapshot(self, tenant: str, portfolio_id: str, now: datetime) -> PortfolioSnapshot:
        with self.store.connection() as conn:
            portfolio = conn.execute(
                "SELECT mode FROM ct_portfolios WHERE tenant_id=%s AND portfolio_id=%s",
                (tenant, portfolio_id),
            ).fetchone()
            if portfolio is None:
                raise ValueError("portfolio ownership mismatch")
            rows = conn.execute(
                "SELECT asset,account,sum(amount) AS amount FROM ct_ledger_postings "
                "WHERE tenant_id=%s AND portfolio_id=%s GROUP BY asset,account "
                "ORDER BY asset,account",
                (tenant, portfolio_id),
            ).fetchall()
        values: dict[str, dict[str, Decimal]] = {}
        for row in rows:
            if not isinstance(row["amount"], Decimal):
                raise RuntimeError("exact ledger amounts required")
            values.setdefault(str(row["asset"]), {})[str(row["account"])] = row["amount"]
        balances = []
        with localcontext() as context:
            context.prec = 100
            for asset, accounts in values.items():
                available = accounts.get("AVAILABLE", Decimal(0))
                reserved = accounts.get("RESERVED", Decimal(0))
                inventory = accounts.get("INVENTORY", Decimal(0))
                balances.append(
                    AssetBalance(
                        asset=asset,
                        available=available,
                        reserved=reserved,
                        inventory=inventory,
                        fees=accounts.get("FEES", Decimal(0)),
                        total_held=available + reserved + inventory,
                    )
                )
        return PortfolioSnapshot.model_validate(
            {
                "tenant_id": tenant,
                "portfolio_id": portfolio_id,
                "mode": portfolio["mode"],
                "as_of": now,
                "balances": tuple(balances),
            }
        )
