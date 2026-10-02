"""Historical market data retrieval; yfinance is not an execution-grade live feed."""

from typing import Final

import pandas as pd
import yfinance as yf


class MarketDataError(RuntimeError):
    """Raised when a usable OHLCV history cannot be retrieved."""


class MarketData:
    DEFAULT_INTERVAL: Final[str] = "5m"
    DEFAULT_PERIOD: Final[str] = "5d"

    def get_history(
        self,
        symbol: str = "^NSEI",
        period: str = DEFAULT_PERIOD,
        interval: str = DEFAULT_INTERVAL,
    ) -> pd.DataFrame:
        if not symbol.strip():
            raise ValueError("A market symbol is required.")
        frame = yf.download(
            symbol.strip(),
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
        )

        if frame.empty:
            raise MarketDataError(
                f"No historical bars returned for {symbol}; check the symbol and interval."
            )
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.loc[:, ~frame.columns.duplicated()].copy()
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required.difference(frame.columns)
        if missing:
            raise MarketDataError(
                f"Historical data for {symbol} is missing columns: {sorted(missing)}."
            )
        frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
        if frame.empty:
            raise MarketDataError(f"Historical data for {symbol} contains no usable bars.")
        return frame

    def get_nifty(self) -> pd.DataFrame:
        return self.get_history("^NSEI")

    def get_banknifty(self) -> pd.DataFrame:
        return self.get_history("^NSEBANK")

    def get_sensex(self) -> pd.DataFrame:
        return self.get_history("^BSESN")
