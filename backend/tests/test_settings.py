"""Unit tests for the runtime business-settings service."""

from __future__ import annotations


def test_settings_current_and_defaults(container):
    current = container.settings_service.current()
    assert "llm" in current and "extraction" in current and "retrieval" in current
    defaults = container.settings_service.defaults()
    assert current["retrieval"]["chunk_size"] == defaults["retrieval"]["chunk_size"]


def test_settings_update_applies_and_persists(container):
    result = container.settings_service.update(
        {"llm": {"temperature": 0.42, "thinking": {"decision": True}}, "retrieval": {"chunk_size": 1234}}
    )
    # applied in place -> running components see the new values
    assert container.config.llm.temperature == 0.42
    assert container.config.llm.thinking == {"decision": True}
    assert container.config.chunk_size == 1234
    assert result["reindex_required"] is False
    # persisted
    stored = container._settings_repo.get()
    assert stored["llm"]["temperature"] == 0.42


def test_settings_invalid_rejected(container):
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        container.settings_service.update({"llm": {"temperature": "not-a-number"}})
    # config unchanged after a rejected update
    assert isinstance(container.config.llm.temperature, float)


def test_embedding_change_flags_reindex(container):
    result = container.settings_service.update({"llm": {"embedding_model": "different-model"}})
    assert result["reindex_required"] is True
    assert container.config.llm.embedding_model == "different-model"


def test_settings_reset(container):
    container.settings_service.update({"llm": {"temperature": 0.9}})
    container.settings_service.reset()
    assert container.config.llm.temperature == container.settings_service.defaults()["llm"]["temperature"]
