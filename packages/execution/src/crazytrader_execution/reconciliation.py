"""Query-only stable-ID fixture recovery; never retries submissions or fabricates health."""

from collections.abc import Callable
from datetime import datetime

from crazytrader_contracts.execution import ExecutionState
from crazytrader_contracts.models import OrderState

from .fixture_transport import SDKFixtureTransport
from .settlement import FillSettlement
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
        if observation.status == "UNKNOWN" or observation.venue_order_id is None:
            return self.store.recover_open_order(observation)
        if (
            observation.status == "NEW"
            and observation.filled_quantity == 0
            and current.filled_quantity == 0
        ):
            return self.store.recover_open_order(observation)
        batch = self.transport.fills(current.request, observation, self.clock())
        return FillSettlement(self.store).apply(observation, batch)

    def reconcile(self, request_id: str) -> ExecutionState:
        current = self.store.load(request_id)
        if current.state in {
            OrderState.SUBMITTING,
            OrderState.SUBMITTED,
            OrderState.UNKNOWN,
            OrderState.RECOVERY_REQUIRED,
        }:
            return self.recover(request_id)
        if current.state not in {
            OrderState.ACKNOWLEDGED,
            OrderState.PARTIALLY_FILLED,
            OrderState.CANCEL_PENDING,
        }:
            return current
        observation = self.transport.query(current.request, self.clock())
        if observation.status == "UNKNOWN" or observation.venue_order_id is None:
            # Do not manufacture absence, terminal state or release funds.
            return current
        if (
            observation.status == "NEW"
            and observation.filled_quantity == 0
            and current.filled_quantity == 0
        ):
            return current
        batch = self.transport.fills(current.request, observation, self.clock())
        return FillSettlement(self.store).apply(observation, batch)
