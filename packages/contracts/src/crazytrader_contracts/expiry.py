"""Expired, durably unsent simulation reservation release evidence."""

from decimal import Decimal, localcontext
from typing import Literal, Self

from pydantic import model_validator

from .execution import ExecutionRequest
from .ledger import LedgerTransaction
from .models import Contract, Identifier, Timestamp


class UnsentExecutionExpiry(Contract):
    schema_version: Literal["1"] = "1"
    source: Literal["DURABLE_UNSENT_EXECUTION"] = "DURABLE_UNSENT_EXECUTION"
    request: ExecutionRequest
    original_reservation: LedgerTransaction
    release: LedgerTransaction
    actor_id: Identifier
    occurred_at: Timestamp

    @model_validator(mode="after")
    def coherent(self) -> Self:
        request, original, release = self.request, self.original_reservation, self.release
        if (
            request.execution_mode != "SIMULATION"
            or request.side != "SELL"
            or self.actor_id != request.actor_id
            or self.occurred_at < request.expires_at
            or release.timestamp != self.occurred_at
            or original.transaction_type != "RESERVATION"
            or release.transaction_type != "RELEASE"
            or original.tenant_id != request.tenant_id
            or release.tenant_id != request.tenant_id
            or original.related_order_id != request.order_id
            or release.related_order_id != request.order_id
            or release.actor_id != self.actor_id
            or any(
                p.portfolio_id != request.portfolio_id
                or p.account not in {"AVAILABLE", "INVENTORY", "RESERVED"}
                for p in original.postings + release.postings
            )
        ):
            raise ValueError("owned expired unsent reservation/release required")
        with localcontext() as exact:
            exact.prec = 100
            by_custody: dict[tuple[str, str], Decimal] = {}
            for posting in original.postings + release.postings:
                key = posting.asset, posting.account
                by_custody[key] = by_custody.get(key, Decimal(0)) + posting.amount
            if any(by_custody.values()) or len({p.asset for p in original.postings}) != 1:
                raise ValueError("expiry must restore complete original custody")
            if (
                sum(p.amount for p in original.postings if p.account == "RESERVED")
                != request.quantity
            ):
                raise ValueError("expiry reservation quantity differs from original request")
        return self
