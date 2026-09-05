"""Shared fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ase_security_review.config.settings import AppConfig, ExtractionConfig, LlmConfig, load_config
from ase_security_review.di import Container
from tests.fakes import FakeLlm, InMemoryVectorRepository


@pytest.fixture()
def app_config() -> AppConfig:
    real = load_config()
    return AppConfig(
        llm=LlmConfig(reasoning_model="fake", embedding_model="fake", embedding_dim=32),
        extraction=ExtractionConfig(default_mode="auto", auto_detect_threshold=50),
        compliance=real.compliance,
        data_dir=Path(tempfile.mkdtemp(prefix="ase-test-")),
    )


def _wire_fakes(c: Container) -> FakeLlm:
    fake = FakeLlm()
    c.llm = fake
    c.ingestion._llm = fake
    c.retrieval._llm = fake
    c.fact_extraction._llm = fake
    c.review_usecase._llm = fake
    c.review_usecase._threat._llm = fake
    in_mem = InMemoryVectorRepository()
    c.vectors = in_mem
    c.ingestion._vectors = in_mem
    c.retrieval._vectors = in_mem
    return fake


@pytest.fixture()
def container(app_config) -> Container:
    c = Container(app_config)
    _wire_fakes(c)
    return c


@pytest.fixture()
def sample_pdf(app_config) -> Path:
    from tests.fixtures.make_pdf import make_text_pdf

    path = app_config.data_dir / "SOP_Sample.pdf"
    make_text_pdf(path, "Pentest Selection SOP\nBAB 2: Kriteria Penetration Test\nAplikasi dengan data pembayaran wajib penetration test.\nDAST untuk aplikasi internal tanpa data sensitif.")
    return path
