"""Composition root / dependency injection container."""

from __future__ import annotations

from pathlib import Path

from .config.settings import AppConfig, load_config
from .data.chroma_store import ChromaVectorRepository
from .data.db import create_db_engine, init_db, make_session_factory
from .data.ollama_client import OllamaClient
from .repository.sqlite_repository import SqliteDocumentRepository, SqliteReviewRepository
from .usecase.extraction import PdfExtractionService
from .usecase.fact_extraction import FactExtractionService
from .usecase.folder_watcher import FolderWatcher
from .usecase.ingestion import IngestionUseCase
from .usecase.retrieval import RetrievalService
from .usecase.review import ReviewUseCase


class Container:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()
        self._ensure_dirs(self.config)

        self.engine = create_db_engine(self.config.db_path)
        init_db(self.engine)
        self.session_factory = make_session_factory(self.engine)

        self.documents = SqliteDocumentRepository(self.session_factory)
        self.reviews = SqliteReviewRepository(self.session_factory)
        self.reviews.mark_stale_running_failed()
        self.vectors = ChromaVectorRepository(self.config.chroma_dir, self.config.llm.embedding_dim)
        self.llm = OllamaClient(self.config.llm)

        self.extraction = PdfExtractionService(self.config.extraction)
        self.ingestion = IngestionUseCase(self.config, self.documents, self.vectors, self.llm, self.extraction)
        self.retrieval = RetrievalService(self.config, self.vectors, self.llm)
        self.fact_extraction = FactExtractionService(self.config, self.llm)
        self.review_usecase = ReviewUseCase(self.config, self.reviews, self.retrieval, self.fact_extraction, self.llm)
        self.watcher = FolderWatcher(self.config, self.ingestion)

    @staticmethod
    def _ensure_dirs(config: AppConfig) -> None:
        for path in (
            config.data_dir,
            config.documents_dir,
            config.extracted_dir,
            config.chroma_dir,
            config.dropbox_dir,
            *config.dropbox_folders.values(),
        ):
            Path(path).mkdir(parents=True, exist_ok=True)

    def start_background(self) -> None:
        # If the embedding model (vector dimension) changed, rebuild the index
        # from the plaintext cache before the watcher starts so no concurrent
        # Chroma writes race with the reset.
        if not self.vectors.dimension_matches(self.config.llm.embedding_dim):
            self.ingestion.reindex_all()
        self.watcher.start()

    def shutdown(self) -> None:
        self.watcher.stop()
        self.llm.close()
