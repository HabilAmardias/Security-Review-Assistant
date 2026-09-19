"""Settings service: read/update the business-logic configuration at runtime.

Business settings are validated, persisted in the database, and applied in place
so running components pick up changes without a restart. Changing the embedding
model/dimension requires a knowledge-base re-index, which the caller triggers.
"""

from __future__ import annotations

from ..config.settings import AppConfig, BusinessSettings, deep_merge
from ..repository.base import LlmPort, SettingsRepository


def _copy_into(target, source) -> None:
    for key, value in source.model_dump().items():
        setattr(target, key, value)


class SettingsService:
    def __init__(self, config: AppConfig, repository: SettingsRepository, llm: LlmPort):
        self._config = config
        self._repository = repository
        self._llm = llm

    def defaults(self) -> dict:
        return BusinessSettings().model_dump()

    def current(self) -> dict:
        return BusinessSettings(
            llm=self._config.llm,
            extraction=self._config.extraction,
            retrieval=self._config.retrieval,
        ).model_dump()

    def update(self, payload: dict) -> dict:
        merged = deep_merge(self.current(), payload or {})
        settings = BusinessSettings.model_validate(merged)

        before = self.current()
        embedding_changed = (
            settings.llm.embedding_model != before["llm"]["embedding_model"]
            or settings.llm.embedding_dim != before["llm"]["embedding_dim"]
        )

        # auto-detect the embedding dimension when the model changes and the dim
        # was not explicitly provided
        if settings.llm.embedding_model != before["llm"]["embedding_model"] and "embedding_dim" not in (payload.get("llm") or {}):
            probed = getattr(self._llm, "probe_embedding_dim", lambda m: None)(settings.llm.embedding_model)
            if probed:
                settings.llm.embedding_dim = probed
                embedding_changed = True

        self._apply(settings)
        self._repository.save(settings.model_dump())
        return {"settings": self.current(), "reindex_required": embedding_changed}

    def reset(self) -> dict:
        settings = BusinessSettings()
        before = self.current()
        embedding_changed = settings.llm.embedding_model != before["llm"]["embedding_model"] or settings.llm.embedding_dim != before["llm"]["embedding_dim"]
        self._apply(settings)
        self._repository.save(settings.model_dump())
        return {"settings": self.current(), "reindex_required": embedding_changed}

    def _apply(self, settings: BusinessSettings) -> None:
        _copy_into(self._config.llm, settings.llm)
        _copy_into(self._config.extraction, settings.extraction)
        _copy_into(self._config.retrieval, settings.retrieval)
