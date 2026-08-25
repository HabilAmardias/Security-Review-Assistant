"""Unit tests for the deterministic rule engine."""

from __future__ import annotations

import pytest

from ase_security_review.config.settings import RuleActionConfig, RuleConfig, RuleTriggerConfig
from ase_security_review.domain.enums import TestLevel
from ase_security_review.domain.models import SecurityDecision
from ase_security_review.domain.rules import aggregate_test_level, evaluate_facts, pentest_required


def make_rule(
    rule_id: str,
    data_classes=None,
    keywords=None,
    features=None,
    exposure=None,
    test_level: str = "pentest",
    priority: str = "medium",
    cap: str | None = None,
) -> RuleConfig:
    return RuleConfig(
        id=rule_id,
        name=rule_id,
        triggers=RuleTriggerConfig(
            data_classes=data_classes or [],
            keywords=keywords or [],
            features=features or [],
            exposure=exposure or [],
        ),
        action=RuleActionConfig(test_level=test_level, priority=priority, cap=cap),
        reasoning=f"reasoning for {rule_id}",
    )


RULES = [
    make_rule("R1", data_classes=["payment"], test_level="pentest", priority="high"),
    make_rule("R2", data_classes=["phi"], test_level="pentest", priority="high"),
    make_rule("R3", keywords=["credit card", "pembayaran"], test_level="dast"),
    make_rule("R4", features=["authentication", "sso"], test_level="pentest", priority="high"),
    make_rule("R5", data_classes=["none"], features=["internal"], test_level="dast", priority="low"),
    make_rule("R6", exposure=["internet-facing", "partner"], test_level="dast", priority="medium"),
    make_rule("R7", exposure=["internal"], test_level="dast", priority="medium", cap="dast"),
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
    assert aggregate_test_level(fired) == TestLevel.PENTEST
    fired = evaluate_facts({"data_classes": [], "features": ["internal"]}, RULES)
    assert aggregate_test_level(fired) == TestLevel.DAST


def test_aggregate_none_when_no_rules():
    assert aggregate_test_level([]) is None


def test_exposure_trigger_internet():
    fired = evaluate_facts({"exposure": "internet-facing"}, RULES)
    assert "R6" in fired_ids(fired)
    fired = evaluate_facts({"exposure": "partner"}, RULES)
    assert "R6" in fired_ids(fired)


def test_exposure_trigger_internal():
    fired = evaluate_facts({"exposure": "internal"}, RULES)
    assert "R7" in fired_ids(fired)
    assert "R6" not in fired_ids(fired)


def test_intranet_caps_aggregate_at_dast():
    # intranet + payment: payment wants pentest, but the intranet cap clamps to dast
    fired = evaluate_facts({"exposure": "internal", "data_classes": ["payment"]}, RULES)
    assert "R1" in fired_ids(fired) and "R7" in fired_ids(fired)
    assert aggregate_test_level(fired) == TestLevel.DAST


def test_internet_not_capped():
    # internet + payment: no cap, strongest wins -> pentest
    fired = evaluate_facts({"exposure": "internet-facing", "data_classes": ["payment"]}, RULES)
    assert aggregate_test_level(fired) == TestLevel.PENTEST


def test_internet_no_data_is_dast():
    # internet alone is only a DAST floor; nothing forces pentest
    fired = evaluate_facts({"exposure": "internet-facing"}, RULES)
    assert aggregate_test_level(fired) == TestLevel.DAST


def test_intranet_no_data_is_dast():
    fired = evaluate_facts({"exposure": "internal"}, RULES)
    assert aggregate_test_level(fired) == TestLevel.DAST


def test_cap_exposed_on_fired_rule():
    fired = evaluate_facts({"exposure": "internal"}, RULES)
    rule = next(r for r in fired if r.id == "R7")
    assert rule.cap == TestLevel.DAST


def test_pentest_required():
    assert pentest_required(TestLevel.PENTEST) is True
    assert pentest_required(TestLevel.DAST) is False
    assert pentest_required(TestLevel.NONE) is False
    assert pentest_required(None) is False


def _decision(test_level: str) -> SecurityDecision:
    return SecurityDecision(
        requires_pentest=pentest_required(TestLevel(test_level)),
        test_level=TestLevel(test_level),
        classification_reason="reason",
    )


def test_apply_cap_clamps_intranet_pentest_to_dast():
    from ase_security_review.domain.rules import apply_cap

    fired = [r for r in evaluate_facts({"exposure": "internal"}, RULES) if r.id == "R7"]
    clamped = apply_cap(_decision("pentest"), fired)
    assert clamped.test_level == TestLevel.DAST
    assert clamped.requires_pentest is False
    assert "caps this application at dast" in clamped.classification_reason


def test_apply_cap_noop_without_cap():
    from ase_security_review.domain.rules import apply_cap

    fired = [r for r in evaluate_facts({"exposure": "internet-facing"}, RULES) if r.id == "R6"]
    d = _decision("pentest")
    assert apply_cap(d, fired) is d  # internet rule has no cap


def test_apply_cap_noop_when_already_below_cap():
    from ase_security_review.domain.rules import apply_cap

    fired = [r for r in evaluate_facts({"exposure": "internal"}, RULES) if r.id == "R7"]
    d = _decision("dast")
    assert apply_cap(d, fired) is d


def fired_ids(fired):
    return {r.id for r in fired}
