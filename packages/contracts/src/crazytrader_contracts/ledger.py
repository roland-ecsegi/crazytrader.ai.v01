"""Append-only, per-asset balanced accounting contracts."""

from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .models import Contract, Fill, Identifier, Money, NonNegative, Timestamp
from .venue_fills import VenueQuoteFill

Account = Literal[
    "AVAILABLE", "RESERVED", "INVENTORY", "EXTERNAL", "FEES", "CAPITAL", "REALIZED_PNL"
]


class LedgerPosting(Contract):
    posting_id: Identifier
    portfolio_id: Identifier | None
    account: Account
    asset: Identifier
    amount: Money
    valuation_ref: Identifier | None = None

    @model_validator(mode="after")
    def ownership(self) -> Self:
        if self.amount == 0:
            raise ValueError("zero posting forbidden")
        if (self.account == "EXTERNAL") != (self.portfolio_id is None):
            raise ValueError("external is tenant-scoped; other accounts require portfolio")
        return self


class LedgerTransaction(Contract):
    schema_version: Literal["1"] = "1"
    transaction_id: Identifier
    tenant_id: Identifier
    source_event_id: Identifier
    actor_id: Identifier
    transaction_type: Literal[
        "FUNDING", "ALLOCATION", "RESERVATION", "RELEASE", "FILL", "FEE", "TRANSFER", "CORRECTION"
    ]
    reason: Identifier
    provenance_ref: Identifier
    related_order_id: Identifier | None = None
    related_fill_id: Identifier | None = None
    correction_of_id: Identifier | None = None
    fill_data: Fill | None = None
    fill_side: Literal["BUY", "SELL"] | None = None
    base_asset: Identifier | None = None
    quote_asset: Identifier | None = None
    timestamp: Timestamp
    postings: Annotated[tuple[LedgerPosting, ...], Field(min_length=2, max_length=100)]

    @model_validator(mode="after")
    def balanced(self) -> Self:
        if len({p.posting_id for p in self.postings}) != len(self.postings):
            raise ValueError("duplicate posting ID")
        with localcontext() as context:
            context.prec = 100
            totals: dict[str, Decimal] = {}
            for posting in self.postings:
                totals[posting.asset] = totals.get(posting.asset, Decimal(0)) + posting.amount
            if any(total != 0 for total in totals.values()):
                raise ValueError("transaction must balance separately for every asset")
        if (self.transaction_type == "CORRECTION") != (self.correction_of_id is not None):
            raise ValueError("compensation requires original transaction reference")
        if self.correction_of_id == self.transaction_id:
            raise ValueError("self-correction forbidden")
        if self.transaction_type in {"RESERVATION", "RELEASE"} and self.related_order_id is None:
            raise ValueError("reservation/release requires order attribution")
        if any(p.account == "RESERVED" for p in self.postings) and self.related_order_id is None:
            raise ValueError("reserved balance must be order-attributed")
        if self.transaction_type == "FILL" and (
            self.related_order_id is None or self.related_fill_id is None
        ):
            raise ValueError("fill accounting requires order and fill references")
        if self.transaction_type == "FILL":
            if (
                self.fill_data is None
                or self.fill_side is None
                or self.base_asset is None
                or self.quote_asset is None
            ):
                raise ValueError("fill requires immutable venue accounting data")
            if self.base_asset == self.quote_asset:
                raise ValueError("distinct fill assets required")
            fill = self.fill_data
            if fill.order_id != self.related_order_id or fill.venue_fill_id != self.related_fill_id:
                raise ValueError("fill attribution mismatch")
            if any(p.valuation_ref is None for p in self.postings):
                raise ValueError("fill requires valuation provenance")
            portfolios = {p.portfolio_id for p in self.postings if p.account != "EXTERNAL"}
            if len(portfolios) != 1 or None in portfolios:
                raise ValueError("fill must have one portfolio attribution")
            with localcontext() as context:
                context.prec = 100
                expected_base = (
                    fill.quantity if self.fill_side == "BUY" else fill.quantity.copy_negate()
                )
                value = fill.quantity * fill.price
                expected_quote = value.copy_negate() if self.fill_side == "BUY" else value
                if fill.fee_asset == self.base_asset:
                    expected_base -= fill.fee_amount
                elif fill.fee_asset == self.quote_asset:
                    expected_quote -= fill.fee_amount
                else:
                    fee_change = sum(
                        (
                            p.amount
                            for p in self.postings
                            if p.asset == fill.fee_asset
                            and p.account in {"AVAILABLE", "RESERVED", "INVENTORY"}
                        ),
                        Decimal(0),
                    )
                    if fee_change != fill.fee_amount.copy_negate():
                        raise ValueError("third-asset fee must debit explicit owned funds")
                actual_base = sum(
                    (
                        p.amount
                        for p in self.postings
                        if p.asset == self.base_asset
                        and p.account in {"AVAILABLE", "RESERVED", "INVENTORY"}
                    ),
                    Decimal(0),
                )
                actual_quote = sum(
                    (
                        p.amount
                        for p in self.postings
                        if p.asset == self.quote_asset
                        and p.account in {"AVAILABLE", "RESERVED", "INVENTORY"}
                    ),
                    Decimal(0),
                )
                actual_fee = sum(
                    (
                        p.amount
                        for p in self.postings
                        if p.asset == fill.fee_asset and p.account == "FEES"
                    ),
                    Decimal(0),
                )
                if (actual_base, actual_quote, actual_fee) != (
                    expected_base,
                    expected_quote,
                    fill.fee_amount,
                ):
                    raise ValueError("fill postings disagree with venue amounts/fees")
        elif any(
            value is not None
            for value in (self.fill_data, self.fill_side, self.base_asset, self.quote_asset)
        ):
            raise ValueError("fill accounting fields only for fill transactions")
        return self


class AssetBalance(Contract):
    asset: Identifier
    available: Money
    reserved: Money
    inventory: Money
    fees: Money
    total_held: Money

    @model_validator(mode="after")
    def reconciled(self) -> Self:
        with localcontext() as context:
            context.prec = 100
            if min(self.available, self.reserved, self.inventory) < 0:
                raise ValueError("negative controlled balance")
            if self.total_held != self.available + self.reserved + self.inventory:
                raise ValueError("held balance attribution mismatch")
        return self


class PortfolioSnapshot(Contract):
    schema_version: Literal["1"] = "1"
    tenant_id: Identifier
    portfolio_id: Identifier
    mode: Literal["MATH", "STRATEGY", "RESERVE"]
    as_of: Timestamp
    balances: tuple[AssetBalance, ...]

    @model_validator(mode="after")
    def unique_assets(self) -> Self:
        if len({balance.asset for balance in self.balances}) != len(self.balances):
            raise ValueError("duplicate snapshot asset")
        return self


class PositionAttribution(Contract):
    tenant_id: Identifier
    portfolio_id: Identifier
    base_asset: Identifier
    quote_asset: Identifier
    quantity: NonNegative
    cost_basis: NonNegative
    realized_pnl: Money | None
    fee_valuation_pending: bool
    valuation_refs: tuple[Identifier, ...]
    valuation_policy: Literal["weighted-average.quote-18-half-even.v1"]
    as_of: Timestamp


class VenueFillLedgerTransaction(Contract):
    schema_version: Literal["1"] = "1"
    transaction_id: Identifier
    tenant_id: Identifier
    source_event_id: Identifier
    actor_id: Identifier
    transaction_type: Literal["FILL"] = "FILL"
    reason: Identifier
    provenance_ref: Identifier
    related_order_id: Identifier | None = None
    related_fill_id: Identifier | None = None
    correction_of_id: Identifier | None = None
    fill_data: Fill | None = None
    fill_side: Literal["BUY", "SELL"] | None = None
    base_asset: Identifier | None = None
    quote_asset: Identifier | None = None
    timestamp: Timestamp
    postings: Annotated[tuple[LedgerPosting, ...], Field(min_length=2, max_length=100)]

    quote_evidence: VenueQuoteFill

    @model_validator(mode="after")
    def balanced(self) -> Self:
        evidence = self.quote_evidence
        if (
            self.tenant_id != evidence.identity.tenant_id
            or self.fill_data != evidence.identity.fill
            or self.fill_side != evidence.identity.side
        ):
            raise ValueError("actual quote journal evidence mismatch")
        if self.transaction_type != "FILL":
            raise ValueError("actual quote evidence only authorizes fill accounting")
        _validate_journal(self, evidence.quote_quantity)
        return self


def _validate_journal(
    self: LedgerTransaction | VenueFillLedgerTransaction, actual_quote: Decimal | None
) -> None:
    if len({p.posting_id for p in self.postings}) != len(self.postings):
        raise ValueError("duplicate posting ID")
    with localcontext() as context:
        context.prec = 100
        totals: dict[str, Decimal] = {}
        for posting in self.postings:
            totals[posting.asset] = totals.get(posting.asset, Decimal(0)) + posting.amount
        if any(total != 0 for total in totals.values()):
            raise ValueError("transaction must balance separately for every asset")
    if (self.transaction_type == "CORRECTION") != (self.correction_of_id is not None):
        raise ValueError("compensation requires original transaction reference")
    if self.correction_of_id == self.transaction_id:
        raise ValueError("self-correction forbidden")
    if self.transaction_type in {"RESERVATION", "RELEASE"} and self.related_order_id is None:
        raise ValueError("reservation/release requires order attribution")
    if any(p.account == "RESERVED" for p in self.postings) and self.related_order_id is None:
        raise ValueError("reserved balance must be order-attributed")
    if self.transaction_type == "FILL" and (
        self.related_order_id is None or self.related_fill_id is None
    ):
        raise ValueError("fill accounting requires order and fill references")
    if self.transaction_type == "FILL":
        if (
            self.fill_data is None
            or self.fill_side is None
            or self.base_asset is None
            or self.quote_asset is None
        ):
            raise ValueError("fill requires immutable venue accounting data")
        if self.base_asset == self.quote_asset:
            raise ValueError("distinct fill assets required")
        fill = self.fill_data
        if fill.order_id != self.related_order_id or fill.venue_fill_id != self.related_fill_id:
            raise ValueError("fill attribution mismatch")
        if any(p.valuation_ref is None for p in self.postings):
            raise ValueError("fill requires valuation provenance")
        portfolios = {p.portfolio_id for p in self.postings if p.account != "EXTERNAL"}
        if len(portfolios) != 1 or None in portfolios:
            raise ValueError("fill must have one portfolio attribution")
        with localcontext() as context:
            context.prec = 100
            expected_base = (
                fill.quantity if self.fill_side == "BUY" else fill.quantity.copy_negate()
            )
            value = fill.quantity * fill.price if actual_quote is None else actual_quote
            expected_quote = value.copy_negate() if self.fill_side == "BUY" else value
            if fill.fee_asset == self.base_asset:
                expected_base -= fill.fee_amount
            elif fill.fee_asset == self.quote_asset:
                expected_quote -= fill.fee_amount
            else:
                fee_change = sum(
                    (
                        p.amount
                        for p in self.postings
                        if p.asset == fill.fee_asset
                        and p.account in {"AVAILABLE", "RESERVED", "INVENTORY"}
                    ),
                    Decimal(0),
                )
                if fee_change != fill.fee_amount.copy_negate():
                    raise ValueError("third-asset fee must debit explicit owned funds")
            actual_base = sum(
                (
                    p.amount
                    for p in self.postings
                    if p.asset == self.base_asset
                    and p.account in {"AVAILABLE", "RESERVED", "INVENTORY"}
                ),
                Decimal(0),
            )
            actual_quote = sum(
                (
                    p.amount
                    for p in self.postings
                    if p.asset == self.quote_asset
                    and p.account in {"AVAILABLE", "RESERVED", "INVENTORY"}
                ),
                Decimal(0),
            )
            actual_fee = sum(
                (
                    p.amount
                    for p in self.postings
                    if p.asset == fill.fee_asset and p.account == "FEES"
                ),
                Decimal(0),
            )
            if (actual_base, actual_quote, actual_fee) != (
                expected_base,
                expected_quote,
                fill.fee_amount,
            ):
                raise ValueError("fill postings disagree with venue amounts/fees")
    elif any(
        value is not None
        for value in (self.fill_data, self.fill_side, self.base_asset, self.quote_asset)
    ):
        raise ValueError("fill accounting fields only for fill transactions")


JournalTransaction = LedgerTransaction | VenueFillLedgerTransaction
