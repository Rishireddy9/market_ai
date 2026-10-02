"""Single-position cash-equity backtest with a non-loosening ATR trailing stop."""

from typing import Any

import pandas as pd

from agents.market_agent import MarketAgent
from agents.risk_agent import RiskAgent
from agents.strategy_agent import StrategyAgent, TradeSignal
from backtester.metrics import calculate_metrics
from config.settings import Settings, settings
from data.indicators import add_indicators
from execution.trailing_stop import ratchet_trailing_stop


class BacktestEngine:
    def __init__(self, configuration: Settings = settings) -> None:
        self.configuration = configuration

    def run(self, bars: pd.DataFrame, symbol: str = "^NSEI") -> dict[str, Any]:
        required = {"Open", "High", "Low", "Close"}
        missing = required.difference(bars.columns)
        if missing:
            raise ValueError(f"Backtest data is missing columns: {sorted(missing)}.")
        if bars.empty:
            raise ValueError("Cannot backtest empty market data.")

        data = add_indicators(bars).dropna(subset=["ema20", "ema50", "rsi", "atr"])
        if len(data) < 2:
            raise ValueError("Not enough complete bars to run the backtest.")

        market_agent = MarketAgent()
        strategy_agent = StrategyAgent()
        risk_agent = RiskAgent(self.configuration)
        equity = self.configuration.initial_capital
        peak_equity = equity
        daily_pnl = 0.0
        current_day: object | None = None
        position: dict[str, Any] | None = None
        trades: list[dict[str, Any]] = []

        for index in range(1, len(data)):
            row = data.iloc[index]
            timestamp = data.index[index]
            day = timestamp.date() if hasattr(timestamp, "date") else timestamp
            if day != current_day:
                current_day = day
                daily_pnl = 0.0

            if position is not None:
                open_price = float(row["Open"])
                low = float(row["Low"])
                high = float(row["High"])
                stop = float(position["current_stop"])
                if low <= stop:
                    exit_price = min(stop, open_price)
                    pnl = (exit_price - position["signal"].entry_price) * position["quantity"]
                    trade = self._make_trade(
                        position, exit_price, timestamp, "trailing_stop", pnl
                    )
                    trades.append(trade)
                    equity += pnl
                    daily_pnl += pnl
                    peak_equity = max(peak_equity, equity)
                    position = None
                else:
                    position["high_water_mark"] = max(position["high_water_mark"], high)
                    position["current_stop"] = ratchet_trailing_stop(
                        entry_price=position["signal"].entry_price,
                        initial_stop=position["signal"].stop_price,
                        current_stop=position["current_stop"],
                        high_water_mark=position["high_water_mark"],
                        current_atr=float(row["atr"]),
                        activation_r=self.configuration.trailing_activation_r,
                        atr_multiple=self.configuration.trailing_atr_multiple,
                    )

            if position is None:
                state = market_agent.analyze(data.iloc[: index + 1])
                signal = strategy_agent.generate(state, symbol)
                if signal is not None:
                    decision = risk_agent.validate_and_size(
                        signal,
                        equity=equity,
                        daily_pnl=daily_pnl,
                        peak_equity=peak_equity,
                    )
                    if decision.approved:
                        position = {
                            "signal": signal,
                            "quantity": decision.quantity,
                            "entry_index": index,
                            "initial_stop": signal.stop_price,
                            "current_stop": signal.stop_price,
                            "high_water_mark": signal.entry_price,
                            "equity_at_entry": equity,
                        }

        if position is not None:
            signal = position["signal"]
            exit_price = float(data["Close"].iloc[-1])
            pnl = (exit_price - signal.entry_price) * position["quantity"]
            trades.append(
                self._make_trade(position, exit_price, data.index[-1], "end_of_data", pnl)
            )

        metrics = calculate_metrics(trades, self.configuration.initial_capital)
        return {"trades": trades, "metrics": metrics}

    @staticmethod
    def _make_trade(
        position: dict[str, Any],
        exit_price: float,
        exit_time: object,
        exit_reason: str,
        pnl: float,
    ) -> dict[str, Any]:
        signal: TradeSignal = position["signal"]
        quantity: int = position["quantity"]
        position_value = signal.entry_price * quantity
        equity_at_entry = position["equity_at_entry"]
        return {
            "symbol": signal.symbol,
            "entry_time": signal.timestamp,
            "exit_time": str(exit_time),
            "entry_price": signal.entry_price,
            "initial_stop": position["initial_stop"],
            "final_stop": position["current_stop"],
            "exit_price": exit_price,
            "quantity": quantity,
            "exit_reason": exit_reason,
            "pnl": pnl,
            "underlying_return_pct": (exit_price / signal.entry_price - 1) * 100,
            "position_return_pct": pnl / position_value * 100,
            "account_return_pct": pnl / equity_at_entry * 100,
        }
