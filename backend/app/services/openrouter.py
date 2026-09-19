"""Minimal synchronous client for OpenRouter's OpenAI-compatible chat completions API."""

from dataclasses import dataclass

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class OpenRouterChat:
    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        self.model = model
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Title": "sql_agent",
            },
        )

    def complete(self, prompt: str) -> Completion:
        """Sends one user message and returns the reply text with token usage."""
        response = self._client.post(
            OPENROUTER_URL,
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenRouter returned {response.status_code}: {response.text[:300]}")
        data = response.json()
        if data.get("error"):
            raise RuntimeError(f"OpenRouter error: {data['error']}")
        choices = data.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if not content:
            raise RuntimeError(f"OpenRouter returned no content: {str(data)[:300]}")
        usage = data.get("usage") or {}
        return Completion(
            text=content,
            model=data.get("model") or self.model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
