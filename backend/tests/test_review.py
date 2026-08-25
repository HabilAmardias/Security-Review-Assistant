"""Unit tests for the review pipeline (facts -> rules -> LLM decision -> conflicts)."""

from __future__ import annotations

from ase_security_review.domain.enums import ReviewStatus, TestLevel
from ase_security_review.domain.models import SecurityDecision
from ase_security_review.usecase.retrieval import RetrievalService
from tests.fakes import DEFAULT_FACTS, DEFAULT_DECISION, FakeLlm

FRD = """Functional Requirements
1. Users can register and login with OAuth2.
2. Payment checkout processes credit card payments via payment gateway.
3. Admin dashboard allows managing users and transactions.
4. Export transaction history as PDF.
"""

NFRD = """Non-Functional Requirements
- Internet-facing, public customer portal.
- Must store personal data (PII) in encrypted database.
- Availability target 99.9%.
- Compliant with PCI DSS and UU PDP.
"""


def seed_knowledge(container) -> None:
    from ase_security_review.domain.enums import DocType
    from ase_security_review.domain.models import Chunk

    chunks = [
        Chunk(
            id="sop:0",
            document_id="sop",
            doc_type=DocType.SOP,
            doc_name="SOP_PentestSelection.pdf",
            text="Aplikasi yang memproses data pembayaran wajib penetration test sesuai OWASP ASVS Level 2. Aplikasi internal tanpa data sensitif cukup DAST.",
            chunk_index=0,
            embedding=[1.0, 0.0],
        ),
        Chunk(
            id="prev:0",
            document_id="prev",
            doc_type=DocType.PREVIOUS_REVIEW,
            doc_name="PREV_Review_PaymentPortal.pdf",
            text="Verdict: PENTEST. Alasan: aplikasi memproses data kartu pembayaran. Scope: web app, REST API pembayaran, auth flows.",
            chunk_index=0,
            embedding=[0.9, 0.1],
        ),
    ]
    container.vectors.upsert_chunks(chunks)


def test_rule_engine_disabled(container):
    seed_knowledge(container)
    container.config.enable_rule_engine = False

    review = container.review_usecase.create_review("frd.pdf", FRD, "nfrd.pdf", NFRD)
    review = container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert review.rule_engine_enabled is False
    assert review.rules_fired == []
    assert review.rule_test_level is None
    assert review.conflicts == []
    assert review.llm_decision is not None  # LLM still decides on its own
    # the rules block in the prompt should mention the engine is disabled
    assert any("DISABLED" in call for call in container.review_usecase._llm.generate_calls)


def test_full_review_pipeline(container):
    seed_knowledge(container)
    review = container.review_usecase.create_review("frd.pdf", FRD, "nfrd.pdf", NFRD)
    review = container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert review.facts["data_classes"] == DEFAULT_FACTS["data_classes"]
    assert review.rules_fired, "internet-facing facts should fire a rule"
    assert any(r.id == "R-06" for r in review.rules_fired)
    # only the exposure rules remain: internet -> dast floor (no pentest mandate)
    assert review.rule_test_level == TestLevel.DAST
    assert review.llm_decision is not None
    assert review.llm_decision.requires_pentest is True
    assert review.llm_decision.test_level == TestLevel.PENTEST
    assert review.retrieved_sources, "should reference retrieved SOP/previous docs"
    assert "SOP_PentestSelection.pdf" in review.retrieved_sources or "PREV_Review_PaymentPortal.pdf" in review.retrieved_sources
    assert review.final_decision is not None
    assert review.llm_decision.scope.in_scope
    # rules say dast but the LLM recommends pentest -> conflict flagged for a human
    assert review.conflicts
    assert any(c.field == "requires_pentest" for c in review.conflicts)


def test_intranet_cap_enforced_on_final_decision(container):
    # intranet facts + LLM recommends pentest -> the cap clamps the FINAL verdict
    from ase_security_review.domain.models import FormField

    seed_knowledge(container)
    review = container.review_usecase.create_review(
        "frd.md",
        "Payment checkout with SSO.",
        "nfrd.md",
        "Internal corporate tool.",
        detected_exposure="internal",
        form_fields=[FormField(label="Aplikasi diakses secara", options=["Internet", "Intranet", "Lainnya"], selected=["Intranet"])],
    )
    review = container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert review.facts["exposure"] == "internal"  # detected exposure wins over the LLM
    assert any(r.id == "R-11" for r in review.rules_fired)
    assert review.rule_test_level == TestLevel.DAST
    # the LLM says pentest, but the intranet cap clamps the final decision to dast
    assert review.llm_decision.test_level == TestLevel.PENTEST
    assert review.final_decision.test_level == TestLevel.DAST
    assert any(c.field == "requires_pentest" for c in review.conflicts)


def test_data_classes_grounded_from_form_field(container):
    from ase_security_review.domain.models import FormField

    seed_knowledge(container)
    review = container.review_usecase.create_review(
        "frd.md",
        "Payment checkout.",
        "nfrd.md",
        "Internal portal.",
        detected_exposure="internal",
        form_fields=[
            FormField(
                label="Karakteristik Aplikasi",
                options=["Financial Transaction", "Non-Financial Transaction", "PII", "Lainnya"],
                selected=["Financial Transaction"],
            )
        ],
    )
    review = container.review_usecase.run_review(review.id)
    assert review.facts["data_classes"] == ["financial"]
    assert "data_classes_llm" in review.facts


def test_change_scope_carried_into_facts(container):
    seed_knowledge(container)
    review = container.review_usecase.create_review("frd.md", "text", "nfrd.md", "text")
    review = container.review_usecase.run_review(review.id)
    assert review.facts["change_scope"] == DEFAULT_FACTS["change_scope"]
    assert review.facts["change_scope_evidence"] == DEFAULT_FACTS["change_scope_evidence"]


def test_human_exposure_override_recomputes(container):
    from ase_security_review.domain.models import FormField

    seed_knowledge(container)
    review = container.review_usecase.create_review(
        "frd.md", "Payment checkout.", "nfrd.md", "Customer portal.",
        detected_exposure="internet-facing",
        form_fields=[FormField(label="Aplikasi diakses secara", options=["Internet", "Intranet"], selected=["Internet"])],
    )
    review = container.review_usecase.run_review(review.id)
    assert review.facts["exposure"] == "internet-facing"
    assert review.final_decision.test_level == TestLevel.PENTEST  # LLM pentest, no cap

    # human corrects exposure to intranet -> rules recomputed, final clamped to dast
    review = container.review_usecase.update_exposure(review.id, "internal")
    assert review.exposure_override == "internal"
    assert review.facts["exposure"] == "internal"
    assert any(r.id == "R-11" for r in review.rules_fired)
    assert review.final_decision.test_level == TestLevel.DAST


def test_llm_matching_rules_no_conflict(container):
    seed_knowledge(container)
    fake: FakeLlm = container.review_usecase._llm
    fake.decision = dict(DEFAULT_DECISION, requires_pentest=False, test_level="dast")

    review = container.review_usecase.create_review("frd.pdf", FRD, "nfrd.pdf", NFRD)
    review = container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert review.rule_test_level == TestLevel.DAST
    assert review.conflicts == []  # LLM agrees with the rules


def test_set_final_decision(container):
    seed_knowledge(container)
    review = container.review_usecase.create_review("frd.pdf", FRD, "nfrd.pdf", NFRD)
    review = container.review_usecase.run_review(review.id)

    decision = review.llm_decision
    override = SecurityDecision(
        requires_pentest=False,
        test_level=TestLevel.DAST,
        classification_reason=decision.classification_reason,
        risk_factors=decision.risk_factors,
        scope=decision.scope,
    )
    review = container.review_usecase.set_final_decision(review.id, override)
    assert review.final_decision.requires_pentest is False
    assert review.final_decision.test_level == TestLevel.DAST


def test_failed_review_records_error(container):
    fake: FakeLlm = container.review_usecase._llm
    fake.decision = "not json at all {{{"
    fake.facts = "also broken"

    review = container.review_usecase.create_review("frd.pdf", FRD, "nfrd.pdf", NFRD)
    review = container.review_usecase.run_review(review.id)
    assert review.status == ReviewStatus.FAILED
    assert review.error


def test_retrieval_hybrid_finds_relevant_chunks(container):
    seed_knowledge(container)
    svc = RetrievalService(container.config, container.vectors, container.llm)
    hits = svc.query(["payment cardholder data penetration test"])
    assert hits
    assert any("sop:0" == h.chunk.id for h in hits)
