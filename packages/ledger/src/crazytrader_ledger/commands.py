"""Typed internal accounting commands; these never grant trading permission."""

from datetime import datetime
from decimal import Decimal, localcontext

from crazytrader_contracts.ledger import (
    Account,
    JournalTransaction,
    LedgerPosting,
    LedgerTransaction,
    VenueFillLedgerTransaction,
)
from crazytrader_contracts.models import Fill, decimal_input
from crazytrader_contracts.venue_fills import VenueQuoteFill
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
    original: JournalTransaction,
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


def account_actual_quote_fill(
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
    quote_evidence: VenueQuoteFill,
    valuation_ref: str,
) -> VenueFillLedgerTransaction:
    quote_evidence = VenueQuoteFill.model_validate(quote_evidence.model_dump())
    fill = quote_evidence.identity.fill
    if base == quote:
        raise ValueError("distinct fill assets required")
    with localcontext() as context:
        context.prec = 100
        value = quote_evidence.quote_quantity
        # Preserve actual quoteQty; no inferred cash or hidden rounding.
        base_change = fill.quantity if side == "BUY" else negate(fill.quantity)
        quote_change = negate(value) if side == "BUY" else value
    if side not in {"BUY", "SELL"}:
        raise ValueError("invalid fill side")
    rows = []
    changes: tuple[tuple[str, str | None, Account, str, Decimal], ...] = (
        ("inventory", portfolio, "INVENTORY" if side == "BUY" else "RESERVED", base, base_change),
        ("venue-base", None, "EXTERNAL", base, negate(base_change)),
        ("cash", portfolio, "RESERVED" if side == "BUY" else "AVAILABLE", quote, quote_change),
        ("venue-quote", None, "EXTERNAL", quote, negate(quote_change)),
    )
    for label, owner, account, asset, amount in changes:
        if amount != 0:
            rows.append(
                posting(transaction_id, label, owner, account, asset, amount, valuation_ref)
            )
    if fill.fee_amount > 0:
        fee_account: Account = (
            ("INVENTORY" if side == "BUY" else "RESERVED")
            if fill.fee_asset == base
            else ("RESERVED" if side == "BUY" and fill.fee_asset == quote else "AVAILABLE")
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
    return VenueFillLedgerTransaction(
        quote_evidence=quote_evidence,
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


def reserve_custody(
    transaction_id: str,
    tenant: str,
    source_event: str,
    actor: str,
    provenance: str,
    now: datetime,
    portfolio: str,
    asset: str,
    quantity: Decimal,
    order: str,
    inventory: Decimal,
    available: Decimal,
) -> LedgerTransaction:
    """Reserve one quantity atomically, consuming INVENTORY before AVAILABLE."""
    quantity = positive(quantity)
    inventory, available = decimal_input(inventory), decimal_input(available)
    if inventory < 0 or available < 0:
        raise ValueError("nonnegative custody balances required")
    with localcontext() as exact:
        exact.prec = 100
        held = min(inventory, quantity)
        cash = quantity - held
    if cash > available:
        raise ValueError("insufficient combined custody")
    rows = [posting(transaction_id, "reserved", portfolio, "RESERVED", asset, quantity)]
    allocations: tuple[tuple[Account, Decimal], ...] = (("INVENTORY", held), ("AVAILABLE", cash))
    for account, amount in allocations:
        if amount:
            rows.append(posting(transaction_id, account, portfolio, account, asset, negate(amount)))
    return LedgerTransaction(
        transaction_id=transaction_id,
        tenant_id=tenant,
        source_event_id=source_event,
        actor_id=actor,
        transaction_type="RESERVATION",
        reason="RESERVATION",
        provenance_ref=provenance,
        timestamp=now,
        related_order_id=order,
        postings=tuple(rows),
    )


def release_custody(
    original: LedgerTransaction,
    remaining: Decimal,
    transaction_id: str,
    source_event: str,
    actor: str,
    provenance: str,
    now: datetime,
) -> LedgerTransaction:
    """Restore unconsumed custody from the immutable original reservation postings."""
    original = LedgerTransaction.model_validate(original.model_dump())
    remaining = positive(remaining)
    if original.transaction_type != "RESERVATION" or original.related_order_id is None:
        raise ValueError("original reservation required")
    rows = original.postings
    assets, portfolios = {p.asset for p in rows}, {p.portfolio_id for p in rows}
    if len(assets) != 1 or len(portfolios) != 1 or None in portfolios:
        raise ValueError("single owned reservation custody required")
    if any(p.account not in {"INVENTORY", "AVAILABLE", "RESERVED"} for p in rows):
        raise ValueError("invalid reservation custody")
    with localcontext() as exact:
        exact.prec = 100
        reserved = sum((p.amount for p in rows if p.account == "RESERVED"), Decimal(0))
        held = -sum((p.amount for p in rows if p.account == "INVENTORY"), Decimal(0))
        available = -sum((p.amount for p in rows if p.account == "AVAILABLE"), Decimal(0))
        if reserved <= 0 or held < 0 or available < 0 or held + available != reserved:
            raise ValueError("invalid reservation allocation")
        if any((p.amount <= 0) != (p.account != "RESERVED") for p in rows):
            raise ValueError("reservation allocation direction mismatch")
        if remaining > reserved:
            raise ValueError("remaining exceeds original reservation")
        consumed = reserved - remaining
        held_left = max(Decimal(0), held - consumed)
        available_left = remaining - held_left
    portfolio, asset = next(iter(portfolios)), next(iter(assets))
    postings = [
        posting(transaction_id, "reserved", portfolio, "RESERVED", asset, negate(remaining))
    ]
    allocations: tuple[tuple[Account, Decimal], ...] = (
        ("INVENTORY", held_left),
        ("AVAILABLE", available_left),
    )
    for account, amount in allocations:
        if amount:
            postings.append(posting(transaction_id, account, portfolio, account, asset, amount))
    return LedgerTransaction(
        transaction_id=transaction_id,
        tenant_id=original.tenant_id,
        source_event_id=source_event,
        actor_id=actor,
        transaction_type="RELEASE",
        reason="RELEASE",
        provenance_ref=provenance,
        timestamp=now,
        related_order_id=original.related_order_id,
        postings=tuple(postings),
    )
