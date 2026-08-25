"""Unit tests for the Ollama client request payload (no network)."""

from __future__ import annotations

import pytest

from ase_security_review.config.settings import LlmConfig
from ase_security_review.data.ollama_client import OllamaClient


@pytest.fixture()
def client() -> OllamaClient:
    return OllamaClient(LlmConfig(reasoning_model="test-model", embedding_model="emb"))


def test_payload_has_messages_and_options(client: OllamaClient):
    payload = client._build_payload("hello", system="sys", format="json", temperature=0.3)
    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    assert payload["format"] == "json"
    assert payload["options"]["num_ctx"] == 16384
    assert payload["options"]["num_predict"] == 4096
    assert payload["options"]["temperature"] == 0.3


def test_think_disabled_by_default(client: OllamaClient):
    payload = client._build_payload("hello")
    assert payload["think"] is False


def test_think_can_be_enabled():
    c = OllamaClient(LlmConfig(reasoning_model="m", embedding_model="e", enable_thinking=True))
    assert c._build_payload("hi")["think"] is True


def test_empty_content_raises_helpful_error():
    c = OllamaClient(LlmConfig(reasoning_model="m", embedding_model="e", max_tokens=128))

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    # budget consumed by reasoning
    c._client.post = lambda *a, **k: FakeResp(
        {
            "done_reason": "length",
            "message": {"role": "assistant", "content": "", "thinking": "hmm..."},
        }
    )
    with pytest.raises(RuntimeError, match="enable_thinking"):
        c.generate("x")

    # no tokens at all
    c._client.post = lambda *a, **k: FakeResp({"done_reason": "stop", "message": {"content": ""}})
    with pytest.raises(RuntimeError, match="empty response"):
        c.generate("x")
