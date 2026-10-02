"""Options-chain provider contract; no fictitious or scraped live chain is supplied."""

from typing import Any, Protocol


class OptionChainProvider(Protocol):
    def get_option_chain(self, underlying: str) -> list[dict[str, Any]]:
        """Return broker-verified contracts, quotes, expiry, and lot-size metadata."""


def fetch_option_chain(
    provider: OptionChainProvider | None,
    underlying: str,
) -> list[dict[str, Any]]:
    if not underlying.strip():
        raise ValueError("An options underlying is required.")
    if provider is None:
        raise RuntimeError(
            "Options trading is disabled: configure a broker-backed options-chain "
            "provider with live quotes, expiry, lot size, and liquidity data."
        )
    chain = provider.get_option_chain(underlying.strip())
    if not chain:
        raise RuntimeError(f"The configured provider returned no contracts for {underlying}.")
    return chain
