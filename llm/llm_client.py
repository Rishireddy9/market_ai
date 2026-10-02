"""Optional LLM market explanation; model output never becomes an order."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agents.market_agent import MarketState
from llm.prompts import build_market_explanation_prompt


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.endpoint = (endpoint or os.getenv("LLM_API_ENDPOINT", "")).rstrip("/")
        self.model = model or os.getenv("LLM_MODEL", "")

    def explain(self, state: MarketState) -> str:
        if not self.api_key or not self.endpoint or not self.model:
            raise RuntimeError(
                "LLM explanation is not configured. Set LLM_API_KEY, "
                "LLM_API_ENDPOINT, and LLM_MODEL."
            )
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": build_market_explanation_prompt(state)}
                ],
                "temperature": 0,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.endpoint}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"LLM provider returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach the configured LLM provider: {exc.reason}") from exc

        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM provider returned an unexpected response shape.") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM provider returned an empty explanation.")
        return content.strip()
