"""JSON (de)serialization helpers for domain objects stored in the audit DB."""

from __future__ import annotations

from ..domain.enums import parse_test_level
from ..domain.models import Conflict, FiredRule, FormField, Review, Scope, SecurityDecision


def form_field_to_dict(f: FormField) -> dict:
    return {
        "label": f.label,
        "options": f.options,
        "selected": f.selected,
        "source_line": f.source_line,
        "page": f.page,
    }


def form_field_from_dict(data: dict) -> FormField:
    return FormField(
        label=data.get("label") or "",
        options=list(data.get("options") or []),
        selected=list(data.get("selected") or []),
        source_line=data.get("source_line") or "",
        page=int(data.get("page") or 1),
    )


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
    }


def decision_from_dict(data: dict | None) -> SecurityDecision | None:
    if not data:
        return None
    return SecurityDecision(
        requires_pentest=bool(data.get("requires_pentest", False)),
        test_level=parse_test_level(data.get("test_level")),
        classification_reason=data.get("classification_reason") or "",
        risk_factors=list(data.get("risk_factors") or []),
        scope=scope_from_dict(data.get("scope")),
    )


def fired_rule_to_dict(r: FiredRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "test_level": r.test_level.value,
        "priority": r.priority,
        "reasoning": r.reasoning,
    }


def fired_rule_from_dict(data: dict) -> FiredRule:
    return FiredRule(
        id=data.get("id", ""),
        name=data.get("name", ""),
        test_level=parse_test_level(data.get("test_level", "dast")),
        priority=data.get("priority", "medium"),
        reasoning=data.get("reasoning", ""),
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
