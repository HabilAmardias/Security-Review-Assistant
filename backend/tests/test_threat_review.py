"""Unit tests for the staged threat-model review pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ase_security_review.config.settings import AppConfig, ExtractionConfig, LlmConfig, load_config
from ase_security_review.di import Container
from ase_security_review.domain.enums import ReviewStatus
from tests.fakes import FakeLlm, InMemoryVectorRepository


@pytest.fixture()
def threat_container():
    real = load_config()
    cfg = AppConfig(
        llm=LlmConfig(reasoning_model="fake", embedding_model="fake", embedding_dim=32),
        extraction=ExtractionConfig(default_mode="auto", auto_detect_threshold=50),
        compliance=real.compliance,
        data_dir=Path(tempfile.mkdtemp(prefix="ase-threat-")),
        pipeline="threat",
    )
    c = Container(cfg)
    fake = FakeLlm()
    c.llm = fake
    c.retrieval._llm = fake
    c.fact_extraction._llm = fake
    c.review_usecase._llm = fake
    c.review_usecase._threat._llm = fake
    in_mem = InMemoryVectorRepository()
    c.vectors = in_mem
    c.retrieval._vectors = in_mem
    return c


def test_threat_pipeline_chains_stages(threat_container):
    review = threat_container.review_usecase.create_review(
        "frd.md",
        "Loan origination with OAuth2 login and admin approval. Submits KTP and salary to core.",
        "nfrd.md",
        "Internet-facing portal storing PII and financial data.",
        detected_exposure="internet-facing",
    )
    review = threat_container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert review.pipeline == "threat"
    assert review.current_stage == "done"
    assert review.facts["exposure"] == "internet-facing"
    assert review.analysis is not None
    assert "requirement" in review.analysis
    assert "architecture" in review.analysis
    assert "assets" in review.analysis
    assert "threats" in review.analysis
    assert "diagrams" in review.analysis
    assert review.analysis["assets"]["assets"][0]["name"] == "customer data"
    assert review.analysis["threats"]["threats"][0]["severity"] == "high"
    assert review.llm_decision is not None
    assert review.final_decision == review.llm_decision
    assert review.conflicts == []


def test_threat_pipeline_degrades_without_vision(threat_container, tmp_path: Path):
    # a diagram image exists but the model cannot read images -> graceful note
    review = threat_container.review_usecase.create_review(
        "frd.md", "Some feature text.", "nfrd.md", "Portal.",
        detected_exposure="internal",
        diagram_paths=[str(tmp_path / "diagram.png")],
    )
    (tmp_path / "diagram.png").write_bytes(b"fake png")
    threat_container.review_usecase._threat._llm.fail_on_images = True
    review = threat_container.review_usecase.run_review(review.id)

    assert review.status == ReviewStatus.COMPLETED
    assert "diagram understanding unavailable" in review.analysis["diagrams"]["note"]
    assert "requirement" in review.analysis


def test_threat_override_reruns(threat_container):
    review = threat_container.review_usecase.create_review(
        "frd.md", "Payment checkout.", "nfrd.md", "Portal.", detected_exposure="internet-facing"
    )
    review = threat_container.review_usecase.run_review(review.id)
    assert review.status == ReviewStatus.COMPLETED

    review = threat_container.review_usecase.apply_override(review.id, exposure="internal")
    assert review.status == ReviewStatus.COMPLETED
    assert review.exposure_override == "internal"
    assert review.facts["exposure"] == "internal"
    assert review.analysis and "threats" in review.analysis


def test_stage_prompts_are_change_scoped(threat_container):
    # FRD describes a narrow change; facts carry the quoted change scope
    threat_container.review_usecase._facts._llm.facts["change_scope_evidence"] = (
        "Only load balancer configuration; no change to business logic."
    )
    threat_container.review_usecase._facts._llm.facts["change_scope"] = "feature_change"
    review = threat_container.review_usecase.create_review(
        "frd.md",
        "Change load balancer config for the checkout service. No change to checkout logic or data flows.",
        "nfrd.md",
        "Internet-facing payment portal handling card and PII data.",
        detected_exposure="internet-facing",
    )
    threat_container.review_usecase.run_review(review.id)

    joined = "\n".join(threat_container.review_usecase._threat._llm.generate_calls)
    assert "CHANGE TARGET" in joined
    assert "Change scope: feature_change" in joined
    assert "Only load balancer configuration" in joined
    assert "CHANGE — FRD (review subject)" in joined
    assert "APPLICATION BACKGROUND — NFRD (context only, not the subject)" in joined
    assert "CHANGE SUMMARY (derived from the requirement stage)" in joined


def test_extract_images_from_pdf_with_embedded_image(tmp_path: Path):
    import pymupdf
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from ase_security_review.usecase.extraction import PdfExtractionService
    from ase_security_review.config.settings import ExtractionConfig

    png = tmp_path / "diagram.png"
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 120), 0)
    pix.save(str(png))

    pdf = tmp_path / "with_img.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.drawImage(str(png), 100, 600, width=200, height=120)
    c.drawString(100, 500, "some text")
    c.showPage()
    c.save()

    svc = PdfExtractionService(ExtractionConfig())
    images = svc.extract_images(pdf)
    assert images
    assert images[0].data.startswith(b"\x89PNG")
