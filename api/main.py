"""Read-only market analysis API; no endpoint places a live order."""

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException

from agents.market_agent import MarketAgent
from agents.strategy_agent import StrategyAgent
from data.indicators import add_indicators
from data.market_data import MarketData, MarketDataError

app = FastAPI(
    title="Indian Market Paper-Trading Prototype",
    description="Historical market analysis only; live order routing is not implemented.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "execution": "paper-only"}


@app.get("/analyze/{symbol}")
def analyze(symbol: str) -> dict[str, Any]:
    try:
        bars = MarketData().get_history(symbol)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    state = MarketAgent().analyze(add_indicators(bars))
    signal = StrategyAgent().generate(state, symbol)
    return {
        "market_state": asdict(state),
        "signal": signal.to_dict() if signal is not None else None,
        "execution": "analysis-only",
    }
