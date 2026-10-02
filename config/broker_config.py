"""Broker settings and an explicit guard against accidental live execution."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class BrokerConfig:
    provider: str | None
    api_key: str | None
    api_secret: str | None
    live_enabled: bool

    @classmethod
    def from_env(cls) -> "BrokerConfig":
        enabled = os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower()
        return cls(
            provider=os.getenv("BROKER_PROVIDER"),
            api_key=os.getenv("BROKER_API_KEY"),
            api_secret=os.getenv("BROKER_API_SECRET"),
            live_enabled=enabled in {"1", "true", "yes"},
        )

    def require_live_broker(self) -> None:
        raise RuntimeError(
            "Live trading is not implemented. Configure a supported Indian broker "
            "adapter, market-data feed, and independent safeguards before enabling it."
        )
