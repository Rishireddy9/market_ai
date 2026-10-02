"""Indicator calculations from OHLCV bars."""

import pandas as pd


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"High", "Low", "Close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"OHLC data is missing columns: {sorted(missing)}.")
    if frame.empty:
        raise ValueError("Cannot calculate indicators for empty market data.")

    result = frame.copy()
    close = pd.to_numeric(result["Close"], errors="coerce")
    high = pd.to_numeric(result["High"], errors="coerce")
    low = pd.to_numeric(result["Low"], errors="coerce")
    if close.isna().all() or high.isna().all() or low.isna().all():
        raise ValueError("OHLC data has no numeric values.")

    result["ema20"] = close.ewm(span=20, min_periods=20, adjust=False).mean()
    result["ema50"] = close.ewm(span=50, min_periods=50, adjust=False).mean()

    change = close.diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)
    average_gain = gains.rolling(14, min_periods=14).mean()
    average_loss = losses.rolling(14, min_periods=14).mean()
    relative_strength = average_gain / average_loss.where(average_loss != 0)
    result["rsi"] = 100 - (100 / (1 + relative_strength))
    result.loc[(average_loss == 0) & (average_gain > 0), "rsi"] = 100

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["atr"] = true_range.rolling(14, min_periods=14).mean()
    return result
