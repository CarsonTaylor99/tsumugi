"""Minimal local-LLM client over Ollama's HTTP API.

Rules from docs/04 baked in rather than remembered:
- every call passes an explicit num_ctx (Ollama silently truncates past its
  small default otherwise);
- output is schema-constrained via the `format` field — the decoder, not
  politeness, guarantees shape;
- prompts are [stable system][volatile user] so the server's KV prefix
  cache is reused across calls.
"""

from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, Field


class LlmBinding(BaseModel):
    """One task's model binding — never hardcoded in a stage (docs/04)."""

    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str
    num_ctx: int = 8192
    temperature: float = 0.3
    options: dict[str, float | int | str] = Field(
        default_factory=dict[str, float | int | str]
    )


def discover_default_model(base_url: str = "http://127.0.0.1:11434") -> str | None:
    """First locally installed model, for bootstrapping a bindings file."""
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=5)
        r.raise_for_status()
        models = r.json().get("models", [])
        return str(models[0]["name"]) if models else None
    except (httpx.HTTPError, KeyError, IndexError):
        return None


class OllamaClient:
    def __init__(self, binding: LlmBinding) -> None:
        self.binding = binding
        self._http = httpx.Client(base_url=binding.base_url, timeout=600)

    def close(self) -> None:
        self._http.close()

    def chat_json(
        self, system: str, user: str, schema: dict[str, object]
    ) -> dict[str, object]:
        """One schema-constrained call. Returns the parsed JSON object.
        Raises ValueError with the raw payload on a malformed response
        (constraints reduce failures; they don't eliminate them)."""
        b = self.binding
        payload: dict[str, object] = {
            "model": b.model,
            "stream": False,
            "format": schema,
            "options": {
                "num_ctx": b.num_ctx,
                "temperature": b.temperature,
                **b.options,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        r = self._http.post("/api/chat", json=payload)
        r.raise_for_status()
        content = r.json().get("message", {}).get("content", "")
        text = str(content).strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        try:
            parsed: object = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed model output: {text[:200]!r}") from e
        if not isinstance(parsed, dict):
            raise ValueError(f"expected JSON object, got {type(parsed).__name__}")
        return {str(k): v for k, v in parsed.items()}  # type: ignore[misc]
