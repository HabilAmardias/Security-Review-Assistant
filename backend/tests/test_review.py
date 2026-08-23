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
            text="Verdict: BOTH (pentest + DAST). Alasan: aplikasi memproses data kartu pembayaran. Scope: web app, REST API pembayaran, auth flows.",
            chunk_index=0,
            embedding=[0.9, 0.1],
        ),
    ]
    container.vectors.upsert_chunks(chunks)


def test_full_review_pipeline(container):
    seed_knowledge(container)
    review = container.review_usecase.create_review("frd.pdf", FRD, "nfrd.pdf", NFRD)
    review = container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert review.facts["data_classes"] == DEFAULT_FACTS["data_classes"]
    assert review.rules_fired, "payment data should fire rules"
    assert any(r.id == "R-01" for r in review.rules_fired)
    assert review.rule_test_level == TestLevel.BOTH
    assert review.llm_decision is not None
    assert review.llm_decision.requires_pentest is True
    assert review.llm_decision.test_level == TestLevel.BOTH
    assert review.retrieved_sources, "should reference retrieved SOP/previous docs"
    assert "SOP_PentestSelection.pdf" in review.retrieved_sources or "PREV_Review_PaymentPortal.pdf" in review.retrieved_sources
    assert review.final_decision is not None
    assert review.llm_decision.scope.in_scope
    assert not review.conflicts  # rule engine and LLM agree here


def test_conflict_detected_when_llm_disagrees(container):
    seed_knowledge(container)
    fake: FakeLlm = container.review_usecase._llm
    fake.decision = dict(DEFAULT_DECISION, requires_pentest=False, test_level="dast")

    review = container.review_usecase.create_review("frd.pdf", FRD, "nfrd.pdf", NFRD)
    review = container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert review.conflicts, "LLM lighter than rules should flag a conflict"
    assert any(c.field == "requires_pentest" for c in review.conflicts)


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
        recommended_frameworks=decision.recommended_frameworks,
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
