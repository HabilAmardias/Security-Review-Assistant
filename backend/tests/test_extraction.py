"""Unit tests for PDF extraction incl. in-memory password handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from ase_security_review.config.settings import ExtractionConfig
from ase_security_review.usecase.extraction import (
    InvalidPasswordError,
    LockedPdfError,
    PdfExtractionService,
)
from tests.fixtures.make_pdf import encrypt_pdf, make_text_pdf


@pytest.fixture()
def svc() -> PdfExtractionService:
    return PdfExtractionService(ExtractionConfig(default_mode="auto", auto_detect_threshold=50))


def test_extract_text(tmp_path: Path, svc: PdfExtractionService):
    pdf = make_text_pdf(tmp_path / "a.pdf", "Hello security world.\nDAST rules.")
    result = svc.extract_text(pdf)
    assert "Hello security world" in result.text
    assert result.pages >= 1


def test_detect_locked(tmp_path: Path, svc: PdfExtractionService):
    plain = make_text_pdf(tmp_path / "p.pdf", "some content")
    locked = encrypt_pdf(plain, tmp_path / "locked.pdf", "pw123")
    is_locked, pages = svc.inspect(locked)
    assert is_locked is True
    assert pages is None


def test_locked_requires_password(tmp_path: Path, svc: PdfExtractionService):
    plain = make_text_pdf(tmp_path / "p.pdf", "secret content")
    locked = encrypt_pdf(plain, tmp_path / "locked.pdf", "pw123")
    with pytest.raises(LockedPdfError):
        svc.extract_text(locked)


def test_wrong_password_rejected(tmp_path: Path, svc: PdfExtractionService):
    plain = make_text_pdf(tmp_path / "p.pdf", "secret content")
    locked = encrypt_pdf(plain, tmp_path / "locked.pdf", "pw123")
    with pytest.raises(InvalidPasswordError):
        svc.extract_text(locked, password="nope")


def test_correct_password_decrypts(tmp_path: Path, svc: PdfExtractionService):
    plain = make_text_pdf(tmp_path / "p.pdf", "secret content")
    locked = encrypt_pdf(plain, tmp_path / "locked.pdf", "pw123")
    result = svc.extract_text(locked, password="pw123")
    assert "secret content" in result.text


def test_density_low():
    svc = PdfExtractionService(ExtractionConfig(auto_detect_threshold=50))
    assert svc.density_low(result_of("tiny", 10)) is True


def result_of(text, pages):
    from ase_security_review.usecase.extraction import PdfTextResult

    return PdfTextResult(text=text, pages=pages)
