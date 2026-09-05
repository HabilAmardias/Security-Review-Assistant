"""Threat-pipeline behaviour tests: rules act as hard bounds on the final decision,
and human exposure / change-scope overrides re-run the pipeline."""

from __future__ import annotations

from ase_security_review.domain.enums import ReviewStatus, TestLevel
from ase_security_review.domain.models import FormField
from tests.fakes import DEFAULT_FACTS, DEFAULT_DECISION

FRD = """Functional Requirements
1. Users can register and login with OAuth2.
2. Payment checkout processes credit card payments via payment gateway.
3. Admin dashboard allows managing users and transactions.
"""

NFRD = """Non-Functional Requirements
- Internet-facing, public customer portal.
- Must store personal data (PII) in encrypted database.
- Availability target 99.9%.
"""


def seed_knowledge(container) -> None:
    from ase_security_review.domain.enums import DocType
    from ase_security_review.domain.models import Chunk

    container.vectors.upsert_chunks(
        [
            Chunk(
                id="sop:0",
                document_id="sop",
                doc_type=DocType.SOP,
                doc_name="SOP_PentestSelection.pdf",
                text="Aplikasi yang memproses data pembayaran wajib penetration test. Aplikasi internal tanpa data sensitif cukup DAST.",
                chunk_index=0,
                embedding=[1.0, 0.0],
            )
        ]
    )


def _run(container, frd: str = FRD, nfrd: str = NFRD, **kw):
    review = container.review_usecase.create_review("frd.md", frd, "nfrd.md", nfrd, **kw)
    return container.review_usecase.run_review(review.id)


def test_intranet_cap_is_a_hard_bound(container):
    review = _run(container, detected_exposure="internal")
    assert review.status == ReviewStatus.COMPLETED
    assert any(r.id == "R-11" for r in review.rules_fired)
    assert review.rule_test_level == TestLevel.DAST
    # STRIDE LLM says pentest, but the intranet cap clamps the final verdict to dast
    assert review.llm_decision.test_level == TestLevel.PENTEST
    assert review.final_decision.test_level == TestLevel.DAST
    assert review.conflicts  # above the cap -> flagged


def test_internet_floor_raises_none_to_dast(container):
    container.review_usecase._threat._llm.decision = dict(DEFAULT_DECISION, requires_pentest=False, test_level="none")
    review = _run(container, detected_exposure="internet-facing")
    assert review.status == ReviewStatus.COMPLETED
    assert any(r.id == "R-06" for r in review.rules_fired)
    assert review.llm_decision.test_level == TestLevel.NONE
    assert review.final_decision.test_level == TestLevel.DAST  # raised to the floor
    assert review.conflicts  # below the floor -> flagged


def test_internet_pentest_allowed_no_conflict(container):
    review = _run(container, detected_exposure="internet-facing")
    assert review.status == ReviewStatus.COMPLETED
    assert review.final_decision.test_level == TestLevel.PENTEST  # STRIDE escalates, no cap
    assert review.conflicts == []


def test_data_classes_grounded_from_form_field(container):
    review = _run(
        container,
        frd="Payment checkout.",
        nfrd="Internal portal.",
        detected_exposure="internal",
        form_fields=[
            FormField(
                label="Karakteristik Aplikasi",
                options=["Financial Transaction", "Non-Financial Transaction", "PII", "Lainnya"],
                selected=["Financial Transaction"],
            )
        ],
    )
    assert review.facts["data_classes"] == ["financial"]
    assert "data_classes_llm" in review.facts


def test_human_exposure_override_recomputes(container):
    review = _run(container, detected_exposure="internet-facing")
    assert review.final_decision.test_level == TestLevel.PENTEST

    review = container.review_usecase.apply_override(review.id, exposure="internal")
    assert review.status == ReviewStatus.COMPLETED
    assert review.exposure_override == "internal"
    assert review.facts["exposure"] == "internal"
    assert any(r.id == "R-11" for r in review.rules_fired)
    assert review.final_decision.test_level == TestLevel.DAST


def test_change_scope_override_recomputes(container):
    review = _run(container, detected_exposure="internet-facing")
    review = container.review_usecase.apply_override(review.id, change_scope="limited_change")
    assert review.status == ReviewStatus.COMPLETED
    assert review.change_scope_override == "limited_change"
    assert review.facts["change_scope"] == "limited_change"
    assert review.analysis and "threats" in review.analysis


def test_change_scope_comes_from_llm(container):
    # the LLM's classification is used as-is; a human override still wins
    container.review_usecase._facts._llm.facts["change_scope"] = "feature_change"
    review = _run(container, frd="This change is FRONT-END ONLY. No change to business logic.")
    assert review.facts["change_scope"] == "feature_change"

    review = container.review_usecase.apply_override(review.id, change_scope="limited_change")
    assert review.facts["change_scope"] == "limited_change"


def test_rule_engine_dormant_flag(container):
    container.config.enable_rule_engine = False
    review = _run(container, detected_exposure="internal")
    assert review.status == ReviewStatus.COMPLETED
    assert review.rules_fired == []
    assert review.rule_test_level is None
    assert review.final_decision == review.llm_decision  # no cap/floor applied


def test_facts_change_scope_default(container):
    review = _run(container, frd="Payment checkout.", nfrd="Portal.")
    assert review.facts["change_scope"] == DEFAULT_FACTS["change_scope"]
