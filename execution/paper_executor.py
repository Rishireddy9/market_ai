"""Explicitly simulated paper-order recorder; never connects to a broker."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from agents.strategy_agent import TradeSignal


class OrderStore(Protocol):
    def record_order(self, order: dict[str, Any]) -> int:
        ...


@dataclass(frozen=True)
class PaperOrder:
    created_at: str
    symbol: str
    direction: str
    quantity: int
    entry_price: float
    stop_price: float
    target_price: float
    status: str
    note: str


class PaperExecutor:
    def __init__(self, store: OrderStore | None = None) -> None:
        self.store = store

    def execute(self, signal: TradeSignal, quantity: int) -> dict[str, Any]:
        if quantity < 1:
            raise ValueError("Paper-order quantity must be at least one.")
        order = PaperOrder(
            created_at=datetime.now(timezone.utc).isoformat(),
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=quantity,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            target_price=signal.target_price,
            status="SIMULATED_NOT_ROUTED",
            note=(
                "Simulated at the signal price for testing only; no broker order or "
                "guaranteed fill was created."
            ),
        )
        result: dict[str, Any] = asdict(order)
        if self.store is not None:
            result["order_id"] = self.store.record_order(result)
        return result
