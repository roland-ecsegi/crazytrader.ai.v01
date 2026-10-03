"""Query-only stable-ID fixture recovery; never retries submissions or fabricates health."""

from collections.abc import Callable
from datetime import datetime

from crazytrader_contracts.execution import ExecutionState
from crazytrader_contracts.models import OrderState

from .fixture_transport import SDKFixtureTransport
from .store import ExecutionStore


class FixtureReconciler:
    def __init__(
        self, store: ExecutionStore, transport: SDKFixtureTransport, clock: Callable[[], datetime]
    ) -> None:
        self.store, self.transport, self.clock = store, transport, clock

    def recover(self, request_id: str) -> ExecutionState:
        current = self.store.start_recovery(request_id, self.clock())
        if current.state != OrderState.RECOVERY_REQUIRED:
            return current
        observation = self.transport.query(current.request, self.clock())
        return self.store.recover_open_order(observation)
