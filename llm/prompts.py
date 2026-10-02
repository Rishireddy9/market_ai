"""Prompts for non-executable market explanations."""

import json
from dataclasses import asdict
from typing import Any

from agents.market_agent import MarketState


def build_market_explanation_prompt(state: MarketState) -> str:
    facts: dict[str, Any] = asdict(state)
    return (
        "Explain these supplied market indicators in plain language. Treat them as "
        "historical/unverified data. Do not recommend a trade, invent prices, forecast "
        "returns, choose quantity, or issue instructions. Mention uncertainty and that "
        "the rule-based strategy and separate risk checks—not this explanation—control "
        "any paper-trading decision.\n\n"
        f"Observed indicators:\n{json.dumps(facts, allow_nan=False)}"
    )
