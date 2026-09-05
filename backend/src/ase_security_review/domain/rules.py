"""Deterministic rule engine. Pure functions, no I/O - fully unit-testable."""

from __future__ import annotations

from typing import Any

from ..config.settings import RuleConfig
from .enums import TestLevel
from .models import Conflict, FiredRule, SecurityDecision

_LEVEL_RANK = {"none": 0, "dast": 1, "pentest": 2}
_PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}

_TEST_LEVEL_BY_NAME = {
    "pentest": TestLevel.PENTEST,
    "dast": TestLevel.DAST,
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
    exposure = str(facts.get("exposure") or "").lower()
    change_scope = str(facts.get("change_scope") or "").lower()
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

        if not matched and tr.exposure:
            matched = exposure in {e.lower() for e in tr.exposure}

        if not matched and tr.change_scope:
            matched = change_scope in {c.lower() for c in tr.change_scope}

        if matched:
            fired.append(
                FiredRule(
                    id=rule.id,
                    name=rule.name,
                    test_level=_TEST_LEVEL_BY_NAME.get(rule.action.test_level, TestLevel.DAST),
                    priority=rule.action.priority,
                    reasoning=rule.reasoning,
                    cap=_TEST_LEVEL_BY_NAME.get(rule.action.cap) if rule.action.cap else None,
                )
            )

    return fired


def aggregate_test_level(fired: list[FiredRule]) -> TestLevel | None:
    """Return the strongest required test level from fired rules, clamped by any
    caps declared on the fired rules (e.g. intranet apps cap at DAST)."""
    if not fired:
        return None
    best = max(fired, key=lambda r: (_LEVEL_RANK[r.test_level.value], _PRIORITY_RANK.get(r.priority, 0)))
    level = best.test_level

    caps = [r.cap for r in fired if r.cap is not None]
    if caps:
        most_restrictive = min(caps, key=lambda c: _LEVEL_RANK[c.value])
        if _LEVEL_RANK[most_restrictive.value] < _LEVEL_RANK[level.value]:
            level = most_restrictive
    return level


def pentest_required(test_level: TestLevel | None) -> bool:
    return test_level == TestLevel.PENTEST


def apply_cap(decision: SecurityDecision, fired: list[FiredRule]) -> SecurityDecision:
    """Clamp a decision to the most restrictive cap declared by the fired rules
    (e.g. the intranet rule caps the overall requirement at DAST)."""
    caps = [r.cap for r in fired if r.cap is not None]
    if not caps:
        return decision
    cap = min(caps, key=lambda c: _LEVEL_RANK[c.value])
    if _LEVEL_RANK[decision.test_level.value] <= _LEVEL_RANK[cap.value]:
        return decision
    note = (
        f" [NOTE: the LLM recommended {decision.test_level.value}, but the deterministic "
        f"rule engine caps this application at {cap.value}; final decision clamped.]"
    )
    return SecurityDecision(
        requires_pentest=pentest_required(cap),
        test_level=cap,
        classification_reason=(decision.classification_reason + note).strip(),
        risk_factors=list(decision.risk_factors),
        scope=decision.scope,
    )


def rule_conflicts(rule_level: TestLevel | None, fired: list[FiredRule], llm: SecurityDecision) -> list[Conflict]:
    """Flag LLM decisions that violate a deterministic rule bound: below the rule
    floor, or above a declared cap. (Rules are hard bounds in the threat pipeline.)"""
    if rule_level is None or llm is None:
        return []
    conflicts: list[Conflict] = []
    caps = [r.cap for r in fired if r.cap is not None]
    cap = min(caps, key=lambda c: _LEVEL_RANK[c.value]) if caps else None

    if _LEVEL_RANK[llm.test_level.value] < _LEVEL_RANK[rule_level.value]:
        conflicts.append(
            Conflict(
                field="test_level",
                rules_value=rule_level.value,
                llm_value=llm.test_level.value,
                explanation=(
                    f"The rule engine requires at least {rule_level.value}, but the agent "
                    f"recommended {llm.test_level.value}."
                ),
            )
        )
    if cap is not None and _LEVEL_RANK[llm.test_level.value] > _LEVEL_RANK[cap.value]:
        conflicts.append(
            Conflict(
                field="test_level",
                rules_value=cap.value,
                llm_value=llm.test_level.value,
                explanation=(
                    f"The rule engine caps this application at {cap.value}, but the agent "
                    f"recommended {llm.test_level.value}."
                ),
            )
        )
    return conflicts
