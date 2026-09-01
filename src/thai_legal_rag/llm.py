import os
from typing import Any

import httpx
from dotenv import load_dotenv

DEFAULT_ENDPOINT = "https://apimsdbxcandidate01.azure-api.net/llm/responses"
DEFAULT_MODEL = "gpt-5-mini"


class BBLClient:
    def __init__(self, endpoint: str, api_key: str, model: str) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_environment(cls) -> "BBLClient":
        load_dotenv()
        api_key = os.getenv("BBL_LLM_API_KEY")
        if not api_key:
            raise RuntimeError("BBL_LLM_API_KEY is missing. Copy .env.example to .env first.")
        return cls(
            endpoint=os.getenv("BBL_LLM_ENDPOINT", DEFAULT_ENDPOINT),
            api_key=api_key,
            model=os.getenv("BBL_LLM_MODEL", DEFAULT_MODEL),
        )

    def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> str:
        response = httpx.post(
            self.endpoint,
            headers={"api-key": self.api_key},
            json={
                "model": self.model,
                "input": messages,
                "max_output_tokens": max_output_tokens,
                "reasoning": {"effort": "minimal"},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return _response_text(response.json())


def _response_text(payload: Any) -> str:
    if not isinstance(payload, dict) or payload.get("status") != "completed":
        raise RuntimeError("BBL endpoint did not return a completed response")

    texts = [
        item["text"]
        for output_item in payload.get("output", [])
        if isinstance(output_item, dict)
        for item in output_item.get("content", [])
        if isinstance(item, dict)
        and item.get("type") == "output_text"
        and isinstance(item.get("text"), str)
    ]
    if not texts:
        raise RuntimeError("BBL endpoint returned no text")
    return "\n".join(texts).strip()
