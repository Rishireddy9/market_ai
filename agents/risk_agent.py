"""Hard pre-trade risk checks and stop-based position sizing."""

from dataclasses import dataclass
import math

from agents.strategy_agent import TradeSignal
from config.settings import Settings, settings


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    quantity: int
    risk_amount: float
    reason: str


class RiskAgent:
    def __init__(self, configuration: Settings = settings) -> None:
        self.configuration = configuration

    def validate_and_size(
        self,
        signal: TradeSignal,
        equity: float,
        daily_pnl: float = 0.0,
        open_positions: int = 0,
        peak_equity: float | None = None,
    ) -> RiskDecision:
        if equity <= 0 or not math.isfinite(equity):
            return RiskDecision(False, 0, 0.0, "Account equity must be positive and finite.")
        if not math.isfinite(daily_pnl) or open_positions < 0:
            return RiskDecision(False, 0, 0.0, "Portfolio risk inputs are invalid.")
        if signal.direction != "LONG":
            return RiskDecision(False, 0, 0.0, "Only long cash-market paper orders are supported.")
        if signal.symbol.strip().startswith("^"):
            return RiskDecision(
                False,
                0,
                0.0,
                "Index values are not directly tradable cash-market symbols.",
            )
        if not all(
            math.isfinite(value)
            for value in (signal.entry_price, signal.stop_price, signal.target_price)
        ):
            return RiskDecision(False, 0, 0.0, "Signal prices must be finite.")
        if signal.entry_price <= 0 or signal.stop_price <= 0:
            return RiskDecision(False, 0, 0.0, "Entry and stop prices must be positive.")
        if not signal.stop_price < signal.entry_price < signal.target_price:
            return RiskDecision(False, 0, 0.0, "Long orders require stop < entry < target.")

        per_unit_risk = signal.entry_price - signal.stop_price
        reward_risk = (signal.target_price - signal.entry_price) / per_unit_risk
        if reward_risk < self.configuration.minimum_risk_reward:
            return RiskDecision(
                False,
                0,
                0.0,
                f"Reward/risk {reward_risk:.2f} is below the configured minimum.",
            )
        if open_positions >= self.configuration.max_open_positions:
            return RiskDecision(False, 0, 0.0, "Maximum open-position limit reached.")
        if daily_pnl <= -(equity * self.configuration.max_daily_loss):
            return RiskDecision(False, 0, 0.0, "Daily loss limit reached; entries are blocked.")

        account_peak = peak_equity if peak_equity is not None else equity
        if not math.isfinite(account_peak) or account_peak <= 0 or equity <= account_peak * (
            1 - self.configuration.max_account_drawdown
        ):
            return RiskDecision(False, 0, 0.0, "Maximum account drawdown reached.")

        risk_budget = equity * self.configuration.risk_per_trade
        quantity = min(
            math.floor(risk_budget / per_unit_risk),
            math.floor(equity / signal.entry_price),
        )
        if quantity < 1:
            return RiskDecision(
                False,
                0,
                risk_budget,
                "Capital is insufficient for one share at the configured stop distance.",
            )
        return RiskDecision(
            True,
            quantity,
            quantity * per_unit_risk,
            "Approved by configured paper-trading risk limits.",
        )
