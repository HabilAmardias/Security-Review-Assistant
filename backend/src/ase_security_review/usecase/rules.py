"""Compliance-rule management: per-rule CRUD, validation, and in-place application
so the review pipeline picks up changes on the next run."""

from __future__ import annotations

from ..config.settings import AppConfig, RuleConfig, deep_merge
from ..repository.base import RulesRepository


class RuleNotFoundError(Exception):
    pass


class RuleExistsError(Exception):
    pass


class RulesService:
    def __init__(self, config: AppConfig, repository: RulesRepository):
        self._config = config
        self._repository = repository

    def list(self) -> list[dict]:
        return [rule.model_dump() for rule in self._repository.list()]

    def defaults(self) -> list[dict]:
        from ..data.migrations import DEFAULT_RULES

        return [RuleConfig.model_validate(rule).model_dump() for rule in DEFAULT_RULES]

    def get(self, rule_id: str) -> dict | None:
        rule = self._repository.get(rule_id)
        return rule.model_dump() if rule else None

    def create(self, payload: dict) -> dict:
        rule = RuleConfig.model_validate(payload)
        if self._repository.get(rule.id):
            raise RuleExistsError(rule.id)
        self._repository.create(rule)
        self._apply()
        return rule.model_dump()

    def update(self, rule_id: str, payload: dict) -> dict:
        existing = self._repository.get(rule_id)
        if not existing:
            raise RuleNotFoundError(rule_id)
        merged = {**existing.model_dump(), **(payload or {}), "id": rule_id}
        rule = RuleConfig.model_validate(merged)
        self._repository.update(rule)
        self._apply()
        return rule.model_dump()

    def patch(self, rule_id: str, payload: dict) -> dict:
        existing = self._repository.get(rule_id)
        if not existing:
            raise RuleNotFoundError(rule_id)
        merged = deep_merge(existing.model_dump(), payload or {})
        merged["id"] = rule_id
        rule = RuleConfig.model_validate(merged)
        self._repository.update(rule)
        self._apply()
        return rule.model_dump()

    def delete(self, rule_id: str) -> None:
        if not self._repository.get(rule_id):
            raise RuleNotFoundError(rule_id)
        self._repository.delete(rule_id)
        self._apply()

    def reset(self) -> list[dict]:
        from ..data.migrations import DEFAULT_RULES

        rules = [RuleConfig.model_validate(rule) for rule in DEFAULT_RULES]
        self._repository.replace_all(rules)
        self._apply()
        return [rule.model_dump() for rule in rules]

    def _apply(self) -> None:
        self._config.compliance.rules[:] = self._repository.list()
