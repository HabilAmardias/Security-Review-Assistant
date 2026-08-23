"""JSON (de)serialization helpers for domain objects stored in the audit DB."""

from __future__ import annotations

from ..domain.enums import TestLevel
from ..domain.models import Conflict, FiredRule, Review, Scope, SecurityDecision


def scope_to_dict(scope: Scope) -> dict:
    return {
        "in_scope": scope.in_scope,
        "out_of_scope": scope.out_of_scope,
        "test_methods": scope.test_methods,
        "environments": scope.environments,
        "effort_estimate": scope.effort_estimate,
    }


def scope_from_dict(data: dict | None) -> Scope:
    data = data or {}
    return Scope(
        in_scope=list(data.get("in_scope") or []),
        out_of_scope=list(data.get("out_of_scope") or []),
        test_methods=list(data.get("test_methods") or []),
        environments=list(data.get("environments") or []),
        effort_estimate=data.get("effort_estimate") or "",
    )


def decision_to_dict(d: SecurityDecision) -> dict:
    return {
        "requires_pentest": d.requires_pentest,
        "test_level": d.test_level.value,
        "classification_reason": d.classification_reason,
        "risk_factors": d.risk_factors,
        "scope": scope_to_dict(d.scope),
        "recommended_frameworks": d.recommended_frameworks,
    }


def decision_from_dict(data: dict | None) -> SecurityDecision | None:
    if not data:
        return None
    try:
        level = TestLevel(data.get("test_level", "dast"))
    except ValueError:
        level = TestLevel.DAST
    return SecurityDecision(
        requires_pentest=bool(data.get("requires_pentest", False)),
        test_level=level,
        classification_reason=data.get("classification_reason") or "",
        risk_factors=list(data.get("risk_factors") or []),
        scope=scope_from_dict(data.get("scope")),
        recommended_frameworks=list(data.get("recommended_frameworks") or []),
    )


def fired_rule_to_dict(r: FiredRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "test_level": r.test_level.value,
        "priority": r.priority,
        "reasoning": r.reasoning,
        "frameworks": r.frameworks,
    }


def fired_rule_from_dict(data: dict) -> FiredRule:
    return FiredRule(
        id=data.get("id", ""),
        name=data.get("name", ""),
        test_level=TestLevel(data.get("test_level", "dast")),
        priority=data.get("priority", "medium"),
        reasoning=data.get("reasoning", ""),
        frameworks=list(data.get("frameworks") or []),
    )


def conflict_to_dict(c: Conflict) -> dict:
    return {"field": c.field, "rules_value": c.rules_value, "llm_value": c.llm_value, "explanation": c.explanation}


def conflict_from_dict(data: dict) -> Conflict:
    return Conflict(
        field=data.get("field", ""),
        rules_value=data.get("rules_value"),
        llm_value=data.get("llm_value"),
        explanation=data.get("explanation", ""),
    )
