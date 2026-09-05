"""Ground deterministic facts (exposure, data classes, change scope) in the
PDF form fields and human overrides so the LLM stages see stable inputs."""

from __future__ import annotations

from ..domain.models import FormField, Review


def ground_change_scope(facts: dict, review: Review) -> dict:
    """Resolve change_scope: human override > LLM value."""
    original = facts.get("change_scope") or "other"
    if original == "infra_config_change":  # legacy value
        original = "limited_change"
    facts["change_scope_llm"] = original
    facts["change_scope"] = review.change_scope_override or original
    return facts


def apply_exposure(facts: dict, review: Review) -> dict:
    """Resolve the effective exposure: human override > PDF form field > LLM."""
    original = facts.get("exposure") or "unclear"
    facts["exposure_llm"] = original
    if review.exposure_override:
        facts["exposure"] = review.exposure_override
    elif review.detected_exposure:
        facts["exposure"] = review.detected_exposure
    else:
        facts["exposure"] = original
    return facts


def ground_data_classes(facts: dict, form_fields: list[FormField]) -> dict:
    """Ground data_classes in the application-characteristics form selection so
    the value is deterministic; keep the LLM's original for audit."""
    for field in form_fields:
        hay = (field.label + " " + " ".join(field.options)).lower()
        if "karakteristik" not in hay and "characteristic" not in hay:
            continue
        mapped = []
        for sel in field.selected:
            s = sel.lower()
            if "financial" in s:
                mapped.append("financial")
            elif "pii" in s or "personally identifiable" in s:
                mapped.append("pii")
            elif "payment" in s or "cardholder" in s:
                mapped.append("payment")
        if mapped:
            facts["data_classes_llm"] = facts.get("data_classes") or []
            facts["data_classes"] = sorted(set(mapped))
        break
    return facts


def ground_facts(facts: dict, review: Review, form_fields: list[FormField]) -> dict:
    return ground_data_classes(apply_exposure(ground_change_scope(facts, review), review), form_fields)
