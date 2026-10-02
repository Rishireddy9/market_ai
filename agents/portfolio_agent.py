"""Small portfolio state model for paper trading and backtests."""

from dataclasses import dataclass, field


@dataclass
class PortfolioState:
    initial_capital: float
    cash: float = field(init=False)
    realized_pnl: float = 0.0
    peak_equity: float = field(init=False)
    open_positions: int = 0

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive.")
        self.cash = self.initial_capital
        self.peak_equity = self.initial_capital

    @property
    def equity(self) -> float:
        return self.initial_capital + self.realized_pnl

    def record_realized_pnl(self, amount: float) -> None:
        self.realized_pnl += amount
        self.peak_equity = max(self.peak_equity, self.equity)
