"""Local driver — talks to an OpenAI-compatible HTTP endpoint (vLLM, llama.cpp server, etc).

Usage:
    driver = LocalDriver(base_url="http://localhost:8000/v1", model="Llama-3-8B")

Requires: pip install uos[local]
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LocalDriver:
    base_url: str = "http://localhost:8000/v1"
    model: str = "local"
    api_key: str = "local"
    temperature: float = 0.0
    name: str = "local"

    def think(self, prompt: str, tools=None, max_tokens: int = 256):
        try:
            import httpx  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("httpx not installed. pip install uos[local]") from e
        r = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        data = r.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {"total_tokens": max_tokens})
        usage.setdefault("total_tokens", max_tokens)
        return text, usage
