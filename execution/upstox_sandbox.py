"""Upstox sandbox-only order placement; this client has no live API endpoint."""

import json
import math
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agents.strategy_agent import TradeSignal


SANDBOX_ORDER_URL = "https://sandbox.upstox.com/v2/order/place"


class UpstoxSandboxError(RuntimeError):
    """Raised when a sandbox order cannot be validated or submitted."""


class UpstoxSandboxExecutor:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token or os.getenv("UPSTOX_SANDBOX_ACCESS_TOKEN")

    def execute(
        self,
        signal: TradeSignal,
        quantity: int,
        instrument_token: str,
    ) -> dict[str, Any]:
        if not self.access_token:
            raise UpstoxSandboxError(
                "Set UPSTOX_SANDBOX_ACCESS_TOKEN in the environment; never paste it into code."
            )
        if not instrument_token.startswith("NSE_EQ|"):
            raise UpstoxSandboxError(
                "Sandbox integration currently accepts NSE cash-equity tokens only "
                "(NSE_EQ|ISIN); options and index instruments are disabled."
            )
        if signal.symbol.startswith("^") or not signal.symbol.endswith(".NS"):
            raise UpstoxSandboxError(
                "Sandbox orders require a matching NSE cash-equity symbol such as RELIANCE.NS."
            )
        if signal.direction != "LONG":
            raise UpstoxSandboxError("Only BUY cash-equity sandbox orders are supported.")
        if quantity < 1:
            raise UpstoxSandboxError("Sandbox order quantity must be at least one.")
        if not math.isfinite(signal.entry_price) or signal.entry_price <= 0:
            raise UpstoxSandboxError("Signal entry price must be positive and finite.")

        payload = {
            "quantity": quantity,
            "product": "D",
            "validity": "DAY",
            "price": 0,
            "instrument_token": instrument_token,
            "order_type": "MARKET",
            "transaction_type": "BUY",
            "disclosed_quantity": 0,
            "trigger_price": 0,
        }
        request = Request(
            SANDBOX_ORDER_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise UpstoxSandboxError(
                f"Upstox sandbox rejected the request with HTTP {exc.code}."
            ) from exc
        except URLError as exc:
            raise UpstoxSandboxError(
                f"Could not reach the Upstox sandbox: {exc.reason}"
            ) from exc

        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise UpstoxSandboxError("Upstox sandbox returned invalid JSON.") from exc
        if not isinstance(result, dict) or result.get("status") not in {"success", "SUCCESS"}:
            raise UpstoxSandboxError(
                "Upstox sandbox did not confirm the order submission."
            )
        return {
            "status": "SANDBOX_SUBMITTED",
            "broker": "upstox",
            "environment": "sandbox",
            "symbol": signal.symbol,
            "instrument_token": instrument_token,
            "quantity": quantity,
            "order_type": "MARKET",
            "response": result,
            "note": (
                "Sandbox entry order submitted only. No stop/target order or automated "
                "position management was sent."
            ),
        }
