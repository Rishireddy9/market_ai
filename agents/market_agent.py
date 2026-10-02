"""Deterministic market-state extraction from completed OHLCV bars."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class MarketState:
    price: float
    trend: Literal["bullish", "bearish", "neutral"]
    rsi: float
    atr: float
    timestamp: str


class MarketAgent:
    def analyze(self, frame: pd.DataFrame) -> MarketState:
        required = {"Close", "ema20", "ema50", "rsi", "atr"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"Market data is missing indicators: {sorted(missing)}.")
        if frame.empty:
            raise ValueError("Cannot analyze empty market data.")

        latest = frame.iloc[-1]
        values = [float(latest[name]) for name in ("Close", "ema20", "ema50", "rsi", "atr")]
        price, ema20, ema50, rsi, atr = values
        if not all(pd.notna(value) for value in values):
            raise ValueError("The latest market bar has incomplete indicator values.")
        if price <= 0 or atr <= 0 or not 0 <= rsi <= 100:
            raise ValueError("The latest market bar contains invalid price or indicator values.")

        trend: Literal["bullish", "bearish", "neutral"]
        if ema20 > ema50:
            trend = "bullish"
        elif ema20 < ema50:
            trend = "bearish"
        else:
            trend = "neutral"
        timestamp = str(frame.index[-1])
        return MarketState(price, trend, rsi, atr, timestamp)
