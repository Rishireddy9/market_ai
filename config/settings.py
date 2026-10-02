"""Validated application settings; live execution is deliberately unavailable."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.02
    max_account_drawdown: float = 0.05
    max_open_positions: int = 1
    minimum_risk_reward: float = 2.0
    trailing_activation_r: float = 1.0
    trailing_atr_multiple: float = 2.0
    live_trading_enabled: bool = False
    database_path: str = "paper_trades.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            initial_capital=float(os.getenv("TRADING_CAPITAL", "100000")),
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.005")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "0.02")),
            max_account_drawdown=float(os.getenv("MAX_ACCOUNT_DRAWDOWN", "0.05")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "1")),
            minimum_risk_reward=float(os.getenv("MINIMUM_RISK_REWARD", "2.0")),
            trailing_activation_r=float(os.getenv("TRAILING_ACTIVATION_R", "1.0")),
            trailing_atr_multiple=float(os.getenv("TRAILING_ATR_MULTIPLE", "2.0")),
            database_path=os.getenv("TRADING_DATABASE_PATH", "paper_trades.sqlite3"),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("TRADING_CAPITAL must be positive.")
        for name, value in (
            ("RISK_PER_TRADE", self.risk_per_trade),
            ("MAX_DAILY_LOSS", self.max_daily_loss),
            ("MAX_ACCOUNT_DRAWDOWN", self.max_account_drawdown),
        ):
            if not 0 < value < 1:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.max_open_positions < 1:
            raise ValueError("MAX_OPEN_POSITIONS must be at least 1.")
        if self.minimum_risk_reward < 2:
            raise ValueError("MINIMUM_RISK_REWARD cannot be lower than 2.")
        if self.trailing_activation_r <= 0 or self.trailing_atr_multiple <= 0:
            raise ValueError("Trailing-stop settings must be positive.")


settings = Settings.from_env()
