"""Unit tests for compliance-rule management (CRUD, validation, application)."""

from __future__ import annotations

import pytest

from ase_security_review.domain.rules import evaluate_facts
from ase_security_review.usecase.rules import RuleExistsError, RuleNotFoundError

NEW_RULE = {
    "id": "R-TEST",
    "name": "Test rule",
    "enabled": True,
    "triggers": {"exposure": ["partner"]},
    "action": {"test_level": "pentest", "priority": "high", "cap": None},
    "reasoning": "test",
}


def test_defaults_are_seeded(container):
    ids = {r["id"] for r in container.rules_service.list()}
    assert {"R-06", "R-11"} <= ids


def test_create_and_get(container):
    created = container.rules_service.create(NEW_RULE)
    assert created["id"] == "R-TEST"
    assert container.rules_service.get("R-TEST")["name"] == "Test rule"
    # applied in place so the pipeline sees it
    assert any(r.id == "R-TEST" for r in container.config.compliance.rules)


def test_create_duplicate_raises(container):
    container.rules_service.create(NEW_RULE)
    with pytest.raises(RuleExistsError):
        container.rules_service.create(NEW_RULE)


def test_update_full_and_id_immutable(container):
    container.rules_service.create(NEW_RULE)
    updated = container.rules_service.update("R-TEST", {**NEW_RULE, "name": "Renamed", "id": "IGNORED"})
    assert updated["id"] == "R-TEST"
    assert updated["name"] == "Renamed"


def test_patch_partial_toggles_enabled(container):
    container.rules_service.create(NEW_RULE)
    patched = container.rules_service.patch("R-TEST", {"enabled": False})
    assert patched["enabled"] is False
    assert patched["name"] == "Test rule"  # untouched


def test_patch_missing_raises(container):
    with pytest.raises(RuleNotFoundError):
        container.rules_service.patch("nope", {"enabled": False})


def test_delete(container):
    container.rules_service.create(NEW_RULE)
    container.rules_service.delete("R-TEST")
    assert container.rules_service.get("R-TEST") is None
    with pytest.raises(RuleNotFoundError):
        container.rules_service.delete("R-TEST")


def test_reset_restores_defaults(container):
    container.rules_service.delete("R-11")
    container.rules_service.create(NEW_RULE)
    container.rules_service.reset()
    ids = {r["id"] for r in container.rules_service.list()}
    assert ids == {"R-06", "R-11"}


def test_validation_rejects_bad_action(container):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        container.rules_service.create({**NEW_RULE, "action": {"test_level": "bogus", "priority": "high"}})


def test_disabled_rule_not_fired(container):
    container.rules_service.patch("R-11", {"enabled": False})
    fired = evaluate_facts({"exposure": "internal"}, container.config.compliance.rules)
    assert not any(r.id == "R-11" for r in fired)
