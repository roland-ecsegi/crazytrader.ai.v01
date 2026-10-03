"""Reconstruct weighted-average quote costs from immutable venue fills.

Fraction preserves exact accounting math. Decimal display conversion is explicitly
18-place half-even; this read view never grants risk/trading permission. Third-asset
fees remain unvalued until a separate sourced conversion exists; P&L then is UNKNOWN.
"""

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction

from crazytrader_contracts.ledger import (
    JournalTransaction,
    PositionAttribution,
    VenueFillLedgerTransaction,
)


def display(value: Fraction) -> Decimal:
    with localcontext() as context:
        context.prec = 100
        return (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
            Decimal("0.000000000000000001"), rounding=ROUND_HALF_EVEN
        )


def positions(
    history: tuple[JournalTransaction, ...], tenant: str, portfolio: str, now: datetime
) -> tuple[PositionAttribution, ...]:
    # Full compensations cancel accounting effect; journal itself remains immutable.
    by_id = {tx.transaction_id: tx for tx in history}
    effective: dict[str, int] = {}
    for tx in reversed(history):
        coefficient = effective.setdefault(tx.transaction_id, 1)
        if tx.correction_of_id is not None:
            if tx.correction_of_id not in by_id:
                raise ValueError("correction provenance unavailable")
            effective[tx.correction_of_id] = effective.get(tx.correction_of_id, 1) - coefficient
    state: dict[tuple[str, str], tuple[Fraction, Fraction, Fraction, bool, tuple[str, ...]]] = {}
    for tx in history:
        if tx.tenant_id != tenant:
            raise ValueError("mixed-tenant accounting history")
        if tx.transaction_type != "FILL" or effective.get(tx.transaction_id, 1) == 0:
            continue
        if not any(p.portfolio_id == portfolio for p in tx.postings):
            continue
        fill = tx.fill_data
        if fill is None or tx.base_asset is None or tx.quote_asset is None:
            raise ValueError("immutable fill valuation unavailable")
        key = tx.base_asset, tx.quote_asset
        quantity, cost, realized, pending, refs = state.get(
            key, (Fraction(0), Fraction(0), Fraction(0), False, ())
        )
        base_fee = Fraction(fill.fee_amount) if fill.fee_asset == tx.base_asset else Fraction(0)
        quote_fee = Fraction(fill.fee_amount) if fill.fee_asset == tx.quote_asset else Fraction(0)
        gross = (
            Fraction(tx.quote_evidence.quote_quantity)
            if isinstance(tx, VenueFillLedgerTransaction)
            else Fraction(fill.quantity) * Fraction(fill.price)
        )
        if tx.fill_side == "BUY":
            acquired = Fraction(fill.quantity) - base_fee
            if acquired <= 0:
                raise ValueError("fee consumes acquisition")
            quantity += acquired
            cost += gross + quote_fee
        else:
            disposed = Fraction(fill.quantity) + base_fee
            if disposed > quantity or quantity <= 0:
                raise ValueError("inventory cost provenance unavailable")
            released_cost = cost * disposed / quantity
            quantity -= disposed
            cost -= released_cost
            realized += gross - quote_fee - released_cost
        pending = pending or fill.fee_asset not in key and fill.fee_amount > 0
        new_refs = tuple(
            sorted(set(refs) | {p.valuation_ref for p in tx.postings if p.valuation_ref})
        )
        state[key] = quantity, cost, realized, pending, new_refs
    return tuple(
        PositionAttribution(
            tenant_id=tenant,
            portfolio_id=portfolio,
            base_asset=base,
            quote_asset=quote,
            quantity=display(quantity),
            cost_basis=display(cost),
            realized_pnl=None if pending else display(realized),
            fee_valuation_pending=pending,
            valuation_refs=refs,
            valuation_policy="weighted-average.quote-18-half-even.v1",
            as_of=now,
        )
        for (base, quote), (quantity, cost, realized, pending, refs) in sorted(state.items())
    )
