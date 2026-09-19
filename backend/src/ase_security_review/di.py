"""Composition root / dependency injection container."""

from __future__ import annotations

from pathlib import Path

from .config.settings import AppConfig, InfraSettings, build_config
from .data.chroma_store import ChromaVectorRepository
from .data.db import create_db_engine, init_db, make_session_factory
from .data.ollama_client import OllamaClient
from .repository.sqlite_repository import (
    SqliteDocumentRepository,
    SqliteReviewRepository,
    SqliteSettingsRepository,
)
from .usecase.extraction import PdfExtractionService
from .usecase.fact_extraction import FactExtractionService
from .usecase.ingestion import IngestionUseCase
from .usecase.retrieval import RetrievalService
from .usecase.review import ReviewUseCase
from .usecase.settings import SettingsService


class Container:
    def __init__(self, config: AppConfig | None = None):
        if config is None:
            infra = InfraSettings()
            self._ensure_dirs(infra.data_dir)
            engine = create_db_engine(infra.data_dir / "app.db")
            init_db(engine)
            session_factory = make_session_factory(engine)
            settings_repo = SqliteSettingsRepository(session_factory)
            config = build_config(infra=infra, business=settings_repo.get())
            self._settings_repo = settings_repo
            self.engine = engine
            self.session_factory = session_factory
        else:
            self._ensure_dirs(config.data_dir)
            self.engine = create_db_engine(config.db_path)
            init_db(self.engine)
            self.session_factory = make_session_factory(self.engine)
            self._settings_repo = SqliteSettingsRepository(self.session_factory)

        self.config = config

        self.documents = SqliteDocumentRepository(self.session_factory)
        self.reviews = SqliteReviewRepository(self.session_factory)
        self.reviews.mark_stale_running_failed()
        self.vectors = ChromaVectorRepository(self.config.chroma_dir, self.config.llm.embedding_dim)
        self.llm = OllamaClient(
            self.config.llm,
            base_url=self.config.infra.ollama_base_url,
            request_timeout_sec=self.config.infra.request_timeout_sec,
        )

        self.extraction = PdfExtractionService(self.config.extraction)
        self.ingestion = IngestionUseCase(self.config, self.documents, self.vectors, self.llm, self.extraction)
        self.retrieval = RetrievalService(self.config, self.vectors, self.llm)
        self.fact_extraction = FactExtractionService(self.config, self.llm)
        self.review_usecase = ReviewUseCase(self.config, self.reviews, self.retrieval, self.fact_extraction, self.llm)
        self.settings_service = SettingsService(self.config, self._settings_repo, self.llm)

    @staticmethod
    def _ensure_dirs(data_dir: Path) -> None:
        for path in (
            data_dir,
            data_dir / "documents",
            data_dir / "extracted",
            data_dir / "diagrams",
            data_dir / "chroma",
        ):
            Path(path).mkdir(parents=True, exist_ok=True)

    def start_background(self) -> None:
        # If the embedding model (vector dimension) changed, rebuild the index from
        # the plaintext cache so the store matches the configured dimension.
        if not self.vectors.dimension_matches(self.config.llm.embedding_dim):
            self.ingestion.reindex_all()

    def shutdown(self) -> None:
        self.llm.close()
