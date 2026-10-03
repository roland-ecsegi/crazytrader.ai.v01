"""Typed internal accounting commands; these never grant trading permission."""

from datetime import datetime
from decimal import Decimal, localcontext

from crazytrader_contracts.ledger import Account, LedgerPosting, LedgerTransaction
from crazytrader_contracts.models import Fill, decimal_input
from crazytrader_platform.storage import digest


def positive(value: str | Decimal) -> Decimal:
    amount = decimal_input(value)
    if amount <= 0:
        raise ValueError("positive amount required")
    return amount


def negate(value: Decimal) -> Decimal:
    return value.copy_negate()  # unary minus otherwise uses ambient Decimal context


def posting(
    transaction_id: str,
    label: str,
    portfolio: str | None,
    account: Account,
    asset: str,
    amount: Decimal,
    valuation: str | None = None,
) -> LedgerPosting:
    return LedgerPosting(
        posting_id="posting:" + digest(transaction_id + ":" + label),
        portfolio_id=portfolio,
        account=account,
        asset=asset,
        amount=amount,
        valuation_ref=valuation,
    )


def move(
    transaction_id: str,
    tenant: str,
    source_event: str,
    actor: str,
    provenance: str,
    now: datetime,
    portfolio: str,
    asset: str,
    amount: str | Decimal,
    operation: str,
    order: str | None = None,
    destination: str | None = None,
    reserve_account: Account = "AVAILABLE",
) -> LedgerTransaction:
    quantity = positive(amount)
    source_account: Account
    target: Account
    if reserve_account not in {"AVAILABLE", "INVENTORY"}:
        raise ValueError("invalid reservation custody account")
    if operation == "FUNDING":
        source_portfolio, source_account, target = None, "EXTERNAL", "AVAILABLE"
    elif operation == "RESERVATION":
        source_portfolio, source_account, target = portfolio, reserve_account, "RESERVED"
    elif operation == "RELEASE":
        source_portfolio, source_account, target = portfolio, "RESERVED", reserve_account
    elif (
        operation in {"TRANSFER", "ALLOCATION"}
        and destination is not None
        and destination != portfolio
    ):
        source_portfolio, source_account, target = portfolio, "AVAILABLE", "AVAILABLE"
    else:
        raise ValueError("unsupported accounting movement")
    target_portfolio = destination if operation in {"TRANSFER", "ALLOCATION"} else portfolio
    return LedgerTransaction.model_validate(
        {
            "transaction_id": transaction_id,
            "tenant_id": tenant,
            "source_event_id": source_event,
            "actor_id": actor,
            "transaction_type": operation,
            "reason": operation,
            "provenance_ref": provenance,
            "timestamp": now,
            "related_order_id": order,
            "postings": (
                posting(
                    transaction_id,
                    "source",
                    source_portfolio,
                    source_account,
                    asset,
                    negate(quantity),
                ),
                posting(transaction_id, "target", target_portfolio, target, asset, quantity),
            ),
        }
    )


def compensate(
    original: LedgerTransaction,
    transaction_id: str,
    source_event: str,
    actor: str,
    reason: str,
    provenance: str,
    now: datetime,
) -> LedgerTransaction:
    return LedgerTransaction(
        transaction_id=transaction_id,
        tenant_id=original.tenant_id,
        source_event_id=source_event,
        actor_id=actor,
        transaction_type="CORRECTION",
        reason=reason,
        provenance_ref=provenance,
        correction_of_id=original.transaction_id,
        related_order_id=original.related_order_id,
        related_fill_id=original.related_fill_id,
        timestamp=now,
        postings=tuple(
            posting(
                transaction_id,
                str(i),
                p.portfolio_id,
                p.account,
                p.asset,
                negate(p.amount),
                p.valuation_ref,
            )
            for i, p in enumerate(original.postings)
        ),
    )


def account_fill(
    transaction_id: str,
    tenant: str,
    source_event: str,
    actor: str,
    provenance: str,
    now: datetime,
    portfolio: str,
    side: str,
    base: str,
    quote: str,
    fill: Fill,
    valuation_ref: str,
) -> LedgerTransaction:
    if base == quote:
        raise ValueError("distinct fill assets required")
    with localcontext() as context:
        context.prec = 100
        value = decimal_input(fill.quantity * fill.price)
        # Contract scale is bounded; never silently round a venue notional.
        base_change = fill.quantity if side == "BUY" else negate(fill.quantity)
        quote_change = negate(value) if side == "BUY" else value
    if side not in {"BUY", "SELL"}:
        raise ValueError("invalid fill side")
    rows = [
        posting(
            transaction_id,
            "inventory",
            portfolio,
            "INVENTORY" if side == "BUY" else "RESERVED",
            base,
            base_change,
            valuation_ref,
        ),
        posting(
            transaction_id, "venue-base", None, "EXTERNAL", base, negate(base_change), valuation_ref
        ),
        posting(
            transaction_id,
            "cash",
            portfolio,
            "RESERVED" if side == "BUY" else "AVAILABLE",
            quote,
            quote_change,
            valuation_ref,
        ),
        posting(
            transaction_id,
            "venue-quote",
            None,
            "EXTERNAL",
            quote,
            negate(quote_change),
            valuation_ref,
        ),
    ]
    if fill.fee_amount > 0:
        fee_account: Account = (
            ("INVENTORY" if side == "BUY" else "RESERVED")
            if fill.fee_asset == base
            else "AVAILABLE"
        )
        rows.extend(
            [
                posting(
                    transaction_id,
                    "fee-charge",
                    portfolio,
                    fee_account,
                    fill.fee_asset,
                    negate(fill.fee_amount),
                    valuation_ref,
                ),
                posting(
                    transaction_id,
                    "fee-expense",
                    portfolio,
                    "FEES",
                    fill.fee_asset,
                    fill.fee_amount,
                    valuation_ref,
                ),
            ]
        )
    return LedgerTransaction(
        transaction_id=transaction_id,
        tenant_id=tenant,
        source_event_id=source_event,
        actor_id=actor,
        transaction_type="FILL",
        reason="VENUE_FILL",
        provenance_ref=provenance,
        related_order_id=fill.order_id,
        related_fill_id=fill.venue_fill_id,
        timestamp=now,
        postings=tuple(rows),
        fill_data=fill,
        fill_side=side,
        base_asset=base,
        quote_asset=quote,
    )
