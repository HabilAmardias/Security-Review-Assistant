"""Unit tests for the deterministic rule engine."""

from __future__ import annotations

import pytest

from ase_security_review.config.settings import RuleActionConfig, RuleConfig, RuleTriggerConfig
from ase_security_review.domain.enums import TestLevel
from ase_security_review.domain.rules import aggregate_test_level, evaluate_facts, pentest_required


def make_rule(
    rule_id: str,
    data_classes=None,
    keywords=None,
    features=None,
    test_level: str = "both",
    priority: str = "medium",
) -> RuleConfig:
    return RuleConfig(
        id=rule_id,
        name=rule_id,
        triggers=RuleTriggerConfig(data_classes=data_classes or [], keywords=keywords or [], features=features or []),
        action=RuleActionConfig(test_level=test_level, priority=priority),
        reasoning=f"reasoning for {rule_id}",
        frameworks=["owasp_asvs"],
    )


RULES = [
    make_rule("R1", data_classes=["payment"], test_level="both", priority="high"),
    make_rule("R2", data_classes=["phi"], test_level="both", priority="high"),
    make_rule("R3", keywords=["credit card", "pembayaran"], test_level="dast"),
    make_rule("R4", features=["authentication", "sso"], test_level="pentest", priority="high"),
    make_rule("R5", data_classes=["none"], features=["internal"], test_level="dast", priority="low"),
]


def test_payment_data_class_fires_rule():
    fired = evaluate_facts({"data_classes": ["payment"]}, RULES)
    ids = {r.id for r in fired}
    assert "R1" in ids
    assert "R5" not in ids


def test_keyword_trigger():
    fired = evaluate_facts({"summary": "App allows pembayaran via e-wallet"}, RULES)
    assert "R3" in fired_ids(fired)


def test_feature_trigger():
    fired = evaluate_facts({"features": ["sso", "authentication"]}, RULES)
    assert "R4" in fired_ids(fired)


def test_none_data_class_matches_empty():
    fired = evaluate_facts({"data_classes": [], "features": ["internal"]}, RULES)
    assert "R5" in fired_ids(fired)
    assert "R1" not in fired_ids(fired)


def test_aggregate_returns_strongest():
    fired = evaluate_facts({"data_classes": ["payment"]}, RULES)
    assert aggregate_test_level(fired) == TestLevel.BOTH
    fired = evaluate_facts({"data_classes": [], "features": ["internal"]}, RULES)
    assert aggregate_test_level(fired) == TestLevel.DAST


def test_aggregate_none_when_no_rules():
    assert aggregate_test_level([]) is None


def test_pentest_required():
    assert pentest_required(TestLevel.BOTH) is True
    assert pentest_required(TestLevel.PENTEST) is True
    assert pentest_required(TestLevel.DAST) is False
    assert pentest_required(None) is False


def fired_ids(fired):
    return {r.id for r in fired}
