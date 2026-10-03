"""Immutable signed loopback dispatch protocol binding; no new execution authority."""

from typing import Literal, Self

from pydantic import model_validator

from .codec import canonical, digest
from .execution import ExecutionRequest
from .market import Hash
from .models import Contract, Timestamp


class FixtureDispatchBound(Contract):
    schema_version: Literal["1"] = "1"
    protocol: Literal["LOOPBACK_DEADLINE_GUARD_V1"] = "LOOPBACK_DEADLINE_GUARD_V1"
    request: ExecutionRequest
    bound_at: Timestamp
    request_sha256: Hash
    sdk_version: Literal["3.0.0"] = "3.0.0"
    maximum_signature_window_ms: Literal[5000] = 5000
    child_source_sha256: Literal["113680db83443dacad4b124b407a298f75a1579ebdc0cf5d188833c2f937530b"]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (
            self.request.execution_mode != "SIMULATION"
            or self.request.side != "SELL"
            or not self.request.created_at <= self.bound_at < self.request.expires_at
            or self.request_sha256 != digest(canonical(self.request))
        ):
            raise ValueError("original scoped simulation dispatch bound required")
        return self
