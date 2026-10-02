"""Performance metrics calculated from actual simulated trade results."""

from collections.abc import Iterable
from typing import Any


def calculate_metrics(
    results: Iterable[dict[str, Any]],
    initial_capital: float = 100_000.0,
) -> dict[str, float | int | None]:
    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive.")
    trades = list(results)
    pnls = [float(trade["pnl"]) for trade in trades]
    winners = [pnl for pnl in pnls if pnl > 0]
    losers = [pnl for pnl in pnls if pnl < 0]

    equity = initial_capital
    peak = equity
    max_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)

    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    profit_factor = gross_profit / gross_loss if gross_loss else None
    account_return_pct = sum(pnls) / initial_capital * 100
    return {
        "trade_count": len(pnls),
        "win_rate_pct": (len(winners) / len(pnls) * 100) if pnls else 0.0,
        "profit_factor": profit_factor,
        "net_pnl": sum(pnls),
        "account_return_pct": account_return_pct,
        "max_drawdown_pct": max_drawdown * 100,
        "trades_position_return_at_least_10pct": sum(
            float(trade.get("position_return_pct", 0.0)) >= 10 for trade in trades
        ),
        "trades_position_return_at_least_20pct": sum(
            float(trade.get("position_return_pct", 0.0)) >= 20 for trade in trades
        ),
        "trades_account_return_at_least_10pct": sum(
            float(trade.get("account_return_pct", 0.0)) >= 10 for trade in trades
        ),
        "trades_account_return_at_least_20pct": sum(
            float(trade.get("account_return_pct", 0.0)) >= 20 for trade in trades
        ),
    }
