"""Deterministic rule engine. Pure functions, no I/O - fully unit-testable."""

from __future__ import annotations

from typing import Any

from ..config.settings import RuleConfig
from .enums import TestLevel
from .models import FiredRule

_LEVEL_RANK = {"none": 0, "dast": 1, "pentest": 2, "both": 3}
_PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}

_TEST_LEVEL_BY_NAME = {
    "pentest": TestLevel.PENTEST,
    "dast": TestLevel.DAST,
    "both": TestLevel.BOTH,
    "none": TestLevel.NONE,
}


def facts_text(facts: dict[str, Any]) -> str:
    """Flatten all free-text fact fields into a lowercase searchable blob."""
    parts: list[str] = []
    for key in ("summary", "app_name", "app_type"):
        val = facts.get(key)
        if isinstance(val, str):
            parts.append(val)
    for key in (
        "key_features", "integrations", "compliance_refs",
        "nfr_highlights", "technologies", "roles",
    ):
        val = facts.get(key)
        if isinstance(val, list):
            parts.extend(str(item) for item in val)
    return " ".join(parts).lower()


def evaluate_facts(facts: dict[str, Any], rules: list[RuleConfig]) -> list[FiredRule]:
    """Return the rules that fire for the given extracted facts."""
    fired: list[FiredRule] = []
    data_classes = {str(d).lower() for d in (facts.get("data_classes") or [])}
    features = [str(f).lower() for f in (facts.get("features") or [])]
    text = facts_text(facts)

    for rule in rules:
        tr = rule.triggers
        matched = False

        if tr.data_classes:
            triggers = {d.lower() for d in tr.data_classes}
            if "none" in triggers:
                matched = not data_classes
            else:
                matched = bool(data_classes.intersection(tr.data_classes))

        if not matched and tr.keywords:
            matched = any(k.lower() in text for k in tr.keywords)

        if not matched and tr.features:
            matched = any(
                any(tok in feat for tok in tr.features) for feat in features
            )

        if matched:
            fired.append(
                FiredRule(
                    id=rule.id,
                    name=rule.name,
                    test_level=_TEST_LEVEL_BY_NAME.get(rule.action.test_level, TestLevel.DAST),
                    priority=rule.action.priority,
                    reasoning=rule.reasoning,
                    frameworks=list(rule.frameworks),
                )
            )

    return fired


def aggregate_test_level(fired: list[FiredRule]) -> TestLevel | None:
    """Return the strongest required test level from fired rules."""
    if not fired:
        return None
    best = max(fired, key=lambda r: (_LEVEL_RANK[r.test_level.value], _PRIORITY_RANK.get(r.priority, 0)))
    return best.test_level


def pentest_required(test_level: TestLevel | None) -> bool:
    return test_level in (TestLevel.PENTEST, TestLevel.BOTH)
