"""Ollama HTTP client (embedding + chat). Local only, on-premise."""

from __future__ import annotations

import httpx

from ..config.settings import LlmConfig
from ..repository.base import LlmPort


class OllamaClient(LlmPort):
    def __init__(self, config: LlmConfig):
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.request_timeout_sec,
        )

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        format: str | None = None,
        temperature: float | None = None,
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self._config.reasoning_model,
            "messages": messages,
            "stream": False,
        }
        if format:
            payload["format"] = format
        payload["options"] = {
            "temperature": temperature if temperature is not None else self._config.temperature,
            "num_predict": self._config.max_tokens,
        }
        resp = self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.post(
            "/api/embed",
            json={"model": self._config.embedding_model, "input": texts},
        )
        resp.raise_for_status()
        return resp.json().get("embeddings", [])

    def list_models(self) -> list[str]:
        try:
            resp = self._client.get("/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def ping(self) -> bool:
        try:
            resp = self._client.get("/api/version")
            return resp.status_code == 200
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()
