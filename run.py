"""Run one historical-data analysis cycle, optionally recording a paper order."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from typing import Any

from agents.market_agent import MarketAgent
from agents.portfolio_agent import PortfolioState
from agents.risk_agent import RiskAgent
from agents.strategy_agent import StrategyAgent
from backtester.engine import BacktestEngine
from config.settings import settings
from data.indicators import add_indicators
from data.market_data import MarketData
from database.db import TradeDatabase
from execution.paper_executor import PaperExecutor
from execution.upstox_sandbox import UpstoxSandboxExecutor


LOGGER = logging.getLogger("market_ai")


def run_cycle(
    symbol: str,
    place_paper_order: bool = False,
    upstox_sandbox: bool = False,
    instrument_token: str | None = None,
) -> dict[str, Any]:
    if place_paper_order and upstox_sandbox:
        raise ValueError("Choose either local --paper recording or --upstox-sandbox.")
    if upstox_sandbox and not instrument_token:
        raise ValueError("--instrument-token is required with --upstox-sandbox.")
    if not symbol.strip():
        raise ValueError("A market symbol is required.")
    bars = MarketData().get_history(symbol)
    state = MarketAgent().analyze(add_indicators(bars))
    signal = StrategyAgent().generate(state, symbol)
    if signal is None:
        return {
            "status": "NO_SIGNAL",
            "market_state": asdict(state),
            "message": "Strategy conditions were not met; no order was created.",
        }

    if not place_paper_order and not upstox_sandbox:
        return {
            "status": "ANALYSIS_ONLY",
            "market_state": asdict(state),
            "signal": signal.to_dict(),
            "message": "Use --paper to record a simulated order. No live orders are supported.",
        }

    portfolio = PortfolioState(settings.initial_capital)
    risk = RiskAgent(settings).validate_and_size(
        signal,
        equity=portfolio.equity,
        peak_equity=portfolio.peak_equity,
    )
    if not risk.approved:
        return {
            "status": "REJECTED",
            "market_state": asdict(state),
            "signal": signal.to_dict(),
            "reason": risk.reason,
        }

    if upstox_sandbox:
        sandbox_result = UpstoxSandboxExecutor().execute(
            signal,
            risk.quantity,
            instrument_token or "",
        )
        TradeDatabase(settings.database_path).record_order(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "symbol": signal.symbol,
                "direction": signal.direction,
                "quantity": risk.quantity,
                "entry_price": signal.entry_price,
                "stop_price": signal.stop_price,
                "target_price": signal.target_price,
                "status": sandbox_result["status"],
                "sandbox_order_response": sandbox_result["response"],
            }
        )
        return {
            "status": sandbox_result["status"],
            "market_state": asdict(state),
            "signal": signal.to_dict(),
            "risk": asdict(risk),
            "result": sandbox_result,
        }

    result = {
        "status": "SIMULATED_NOT_ROUTED",
        "risk": asdict(risk),
        "order": PaperExecutor(TradeDatabase(settings.database_path)).execute(
            signal,
            risk.quantity,
        ),
    }
    return {
        "status": result["status"],
        "market_state": asdict(state),
        "signal": signal.to_dict(),
        "result": result,
    }


def run_backtest(symbol: str) -> dict[str, Any]:
    bars = MarketData().get_history(symbol)
    result = BacktestEngine(settings).run(bars, symbol)
    return {
        "status": "HISTORICAL_BACKTEST",
        "symbol": symbol,
        "bars": len(bars),
        "warning": (
            "Historical simulation only; Yahoo data may be delayed. Results exclude "
            "brokerage, taxes, slippage, and market impact and do not predict future returns."
        ),
        **result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbol",
        default="^NSEI",
        help="Yahoo Finance symbol, e.g. ^NSEI, ^BSESN, RELIANCE.NS.",
    )
    parser.add_argument(
        "--paper",
        action="store_true",
        help="Record a risk-checked simulated proposal; does not simulate fills or route orders.",
    )
    parser.add_argument(
        "--upstox-sandbox",
        action="store_true",
        help="Explicitly submit an eligible order to Upstox's sandbox API (not live).",
    )
    parser.add_argument(
        "--instrument-token",
        help="Exact NSE_EQ|ISIN from Upstox instruments; required for --upstox-sandbox.",
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Simulate historical entries with ATR trailing stops; no orders are created.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if sum((args.paper, args.backtest, args.upstox_sandbox)) > 1:
        parser.error("Choose only one of --paper, --backtest, or --upstox-sandbox.")
    result = (
        run_backtest(args.symbol)
        if args.backtest
        else run_cycle(
            args.symbol,
            place_paper_order=args.paper,
            upstox_sandbox=args.upstox_sandbox,
            instrument_token=args.instrument_token,
        )
    )
    LOGGER.info("%s", json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
