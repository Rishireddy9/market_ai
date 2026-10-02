"""Rule-based strategy proposal; an LLM cannot create or execute orders."""

from dataclasses import asdict, dataclass

from agents.market_agent import MarketState


@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward_ratio: float
    reason: str
    timestamp: str

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


class StrategyAgent:
    ATR_STOP_MULTIPLE = 1.5
    TARGET_R_MULTIPLE = 3.0

    def generate(self, market_state: MarketState, symbol: str = "^NSEI") -> TradeSignal | None:
        if market_state.trend != "bullish" or not 50 <= market_state.rsi <= 70:
            return None
        stop_distance = market_state.atr * self.ATR_STOP_MULTIPLE
        if stop_distance <= 0 or stop_distance >= market_state.price:
            return None

        stop = market_state.price - stop_distance
        target = market_state.price + stop_distance * self.TARGET_R_MULTIPLE
        return TradeSignal(
            symbol=symbol,
            direction="LONG",
            entry_price=market_state.price,
            stop_price=stop,
            target_price=target,
            risk_reward_ratio=(target - market_state.price) / stop_distance,
            reason="Bullish EMA trend with RSI in the configured entry range.",
            timestamp=market_state.timestamp,
        )
