"""Unit tests for the ingestion use case (uses in-memory fakes)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ase_security_review.domain.enums import DocStatus, DocType
from tests.fixtures.make_pdf import encrypt_pdf, make_text_pdf


def test_index_text_pdf(container, sample_pdf: Path):
    doc = container.ingestion.register_file(sample_pdf, DocType.SOP)
    doc = container.ingestion.index_document(doc.id)
    assert doc.status == DocStatus.READY
    assert doc.chunk_count and doc.chunk_count > 0
    assert container.vectors.count() == doc.chunk_count
    assert Path(doc.plaintext_path).exists()


def test_idempotent_register(container, sample_pdf: Path):
    d1 = container.ingestion.register_file(sample_pdf, DocType.SOP)
    d2 = container.ingestion.register_file(sample_pdf, DocType.SOP)
    assert d1.id == d2.id


def test_replace_on_content_change(container, sample_pdf: Path):
    d1 = container.ingestion.register_file(sample_pdf, DocType.SOP)
    container.ingestion.index_document(d1.id)
    sample_pdf.write_bytes(sample_pdf.read_bytes() + b"\nnew appended content to change the hash")
    d2 = container.ingestion.register_file(sample_pdf, DocType.SOP)
    assert d2.id != d1.id
    container.ingestion.index_document(d2.id)
    assert container.documents.get(d1.id) is None
    assert container.documents.get(d2.id).status == DocStatus.READY


def test_locked_doc_needs_password(container, sample_pdf: Path):
    locked = encrypt_pdf(sample_pdf, sample_pdf.parent / "locked.pdf", "sekret")
    doc = container.ingestion.register_file(locked, DocType.SOP)
    doc = container.ingestion.index_document(doc.id)
    assert doc.status == DocStatus.NEEDS_PASSWORD


def test_unlock_wrong_password(container, sample_pdf: Path):
    locked = encrypt_pdf(sample_pdf, sample_pdf.parent / "locked.pdf", "sekret")
    doc = container.ingestion.register_file(locked, DocType.SOP)
    doc = container.ingestion.unlock_and_index(doc.id, "wrong")
    assert doc.status == DocStatus.FAILED
    assert "Incorrect password" in doc.error


def test_unlock_and_reindex_without_password(container, sample_pdf: Path):
    locked = encrypt_pdf(sample_pdf, sample_pdf.parent / "locked.pdf", "sekret")
    doc = container.ingestion.register_file(locked, DocType.SOP)
    doc = container.ingestion.unlock_and_index(doc.id, "sekret")
    assert doc.status == DocStatus.READY
    # re-index should reuse cached plaintext, no password required
    again = container.ingestion.index_document(doc.id)
    assert again.status == DocStatus.READY


def test_auto_mode_flags_needs_ocr_for_image_like_pdf(container, tmp_path: Path):
    # a PDF with almost no text should be flagged NEEDS_OCR in auto mode
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = tmp_path / "scan.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFillColorRGB(1, 1, 1)
    c.drawString(0, 0, " ")  # essentially empty text layer
    c.showPage()
    c.save()

    doc = container.ingestion.register_file(pdf, DocType.SOP)
    doc = container.ingestion.index_document(doc.id)
    assert doc.status == DocStatus.NEEDS_OCR
