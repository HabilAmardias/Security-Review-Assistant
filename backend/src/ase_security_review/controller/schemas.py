"""API response serializers (domain objects -> plain dicts)."""

from __future__ import annotations

from ..domain.models import Document, Review
from ..repository.serialization import form_field_to_dict


def document_to_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "name": doc.name,
        "doc_type": doc.doc_type.value,
        "status": doc.status.value,
        "path": doc.path,
        "is_locked": doc.is_locked,
        "pages": doc.pages,
        "extraction_mode": doc.extraction_mode.value if doc.extraction_mode else None,
        "chunk_count": doc.chunk_count,
        "error": doc.error,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


def review_to_dict(review: Review, include_texts: bool = False) -> dict:
    data: dict = {
        "id": review.id,
        "status": review.status.value,
        "frd_name": review.frd_name,
        "nfrd_name": review.nfrd_name,
        "facts": review.facts,
        "rule_engine_enabled": review.rule_engine_enabled,
        "pipeline": review.pipeline,
        "current_stage": review.current_stage,
        "diagram_count": len(review.diagram_paths),
        "analysis": review.analysis,
        "detected_exposure": review.detected_exposure,
        "exposure_override": review.exposure_override,
        "change_scope_override": review.change_scope_override,
        "form_fields": [form_field_to_dict(f) for f in review.form_fields],
        "retrieved_sources": review.retrieved_sources,
        "rules_fired": [r.__dict__ for r in review.rules_fired],
        "rule_test_level": review.rule_test_level.value if review.rule_test_level else None,
        "llm_decision": decision_to_dict(review.llm_decision),
        "conflicts": [c.__dict__ for c in review.conflicts],
        "final_decision": decision_to_dict(review.final_decision),
        "error": review.error,
        "created_at": review.created_at.isoformat(),
        "updated_at": review.updated_at.isoformat(),
    }
    if include_texts:
        data["frd_text"] = review.frd_text[:2000]
        data["nfrd_text"] = review.nfrd_text[:2000]
    return data


def decision_to_dict(decision) -> dict | None:
    if decision is None:
        return None
    return {
        "requires_pentest": decision.requires_pentest,
        "test_level": decision.test_level.value,
        "classification_reason": decision.classification_reason,
        "risk_factors": decision.risk_factors,
        "scope": {
            "in_scope": decision.scope.in_scope,
            "out_of_scope": decision.scope.out_of_scope,
            "test_methods": decision.scope.test_methods,
            "environments": decision.scope.environments,
            "effort_estimate": decision.scope.effort_estimate,
        },
    }
