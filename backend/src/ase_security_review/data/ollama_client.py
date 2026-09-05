"""Ollama HTTP client (embedding + chat). Local only, on-premise."""

from __future__ import annotations

import base64

import httpx

from ..config.settings import LlmConfig
from ..repository.base import LlmPort


class OllamaClient(LlmPort):
    def __init__(self, config: LlmConfig):
        self._config = config
        # httpx accepts None to disable timeouts entirely.
        timeout = config.request_timeout_sec if config.request_timeout_sec else None
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=timeout,
        )

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        format: str | None = None,
        temperature: float | None = None,
        images: list[bytes] | None = None,
        step: str | None = None,
    ) -> str:
        payload = self._build_payload(
            prompt, system=system, format=format, temperature=temperature, images=images, step=step
        )
        resp = self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Ollama error: {data['error']}")
        content = data.get("message", {}).get("content", "")
        if not content:
            msg = data.get("message", {}) or {}
            thinking = msg.get("thinking") or ""
            detail = (
                f"model consumed all {self._config.max_tokens} output tokens on reasoning "
                "without producing an answer — set llm.thinking.<step> to false (config.yaml)"
                if data.get("done_reason") == "length"
                else "no tokens generated"
            )
            raise RuntimeError(
                f"Ollama returned an empty response (model: {self._config.reasoning_model}; {detail})"
            )
        return content

    def _build_payload(
        self,
        prompt: str,
        system: str | None = None,
        format: str | None = None,
        temperature: float | None = None,
        images: list[bytes] | None = None,
        step: str | None = None,
    ) -> dict:
        user_content: dict = {"role": "user", "content": prompt}
        if images:
            user_content["images"] = [base64.b64encode(img).decode("ascii") for img in images]
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(user_content)

        payload: dict = {
            "model": self._config.reasoning_model,
            "messages": messages,
            "stream": False,
            "think": self._config.thinking.get(step, False),
        }
        if format:
            payload["format"] = format
        payload["options"] = {
            "temperature": temperature if temperature is not None else self._config.temperature,
            "num_predict": self._config.max_tokens,
            "num_ctx": self._config.num_ctx,
        }
        return payload

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
