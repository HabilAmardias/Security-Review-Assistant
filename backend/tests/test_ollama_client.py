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


def test_payload_embeds_images_as_base64(client: OllamaClient):
    import base64

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    payload = client._build_payload("what is this?", images=[png])
    user_msg = payload["messages"][-1]
    assert user_msg["images"] == [base64.b64encode(png).decode("ascii")]
    assert user_msg["content"] == "what is this?"


def test_think_defaults_to_false_for_unlisted_step(client: OllamaClient):
    assert client._build_payload("hello", step="unknown_step")["think"] is False


def test_think_comes_from_per_step_map():
    c = OllamaClient(
        LlmConfig(
            reasoning_model="m",
            embedding_model="e",
            thinking={"decision": True, "requirement": False},
        )
    )
    assert c._build_payload("hi", step="decision")["think"] is True
    assert c._build_payload("hi", step="requirement")["think"] is False
    assert c._build_payload("hi", step="assets")["think"] is False  # unlisted -> false


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
    with pytest.raises(RuntimeError, match="thinking"):
        c.generate("x")

    # no tokens at all
    c._client.post = lambda *a, **k: FakeResp({"done_reason": "stop", "message": {"content": ""}})
    with pytest.raises(RuntimeError, match="empty response"):
        c.generate("x")
