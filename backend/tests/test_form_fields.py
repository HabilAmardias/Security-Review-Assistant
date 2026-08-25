"""Unit tests for deterministic form-field extraction (colour-outlier)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ase_security_review.config.settings import ExtractionConfig
from ase_security_review.usecase.extraction import PdfExtractionService
from tests.fixtures.make_pdf import make_form_pdf


@pytest.fixture()
def svc() -> PdfExtractionService:
    return PdfExtractionService(ExtractionConfig())


def test_extract_form_fields_detects_selected_options(svc: PdfExtractionService, tmp_path: Path):
    pdf = make_form_pdf(tmp_path / "form.pdf")
    fields = svc.extract_form_fields(pdf)

    by_label = {f.label: f for f in fields}
    assert "Aplikasi diakses secara" in by_label
    exposure_field = by_label["Aplikasi diakses secara"]
    assert exposure_field.selected == ["Intranet"]

    karakter = by_label["Karakteristik Aplikasi"]
    assert set(karakter.selected) == {"Financial Transaction", "Non-Financial Transaction"}


def test_exposure_from_form_fields(svc: PdfExtractionService, tmp_path: Path):
    pdf = make_form_pdf(tmp_path / "form.pdf")
    fields = svc.extract_form_fields(pdf)
    assert svc.exposure_from_form_fields(fields) == "internal"


def test_no_form_fields_when_all_same_colour(svc: PdfExtractionService, tmp_path: Path):
    from tests.fixtures.make_pdf import make_text_pdf

    pdf = make_text_pdf(tmp_path / "plain.pdf", "Some plain text without form grids.\nAnother line.")
    assert svc.extract_form_fields(pdf) == []
