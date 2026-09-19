"""Repository port interfaces. Use cases depend on these ABCs so tests can
inject in-memory fakes without touching SQLite, Chroma, or Ollama."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config.settings import RuleConfig
from ..domain.enums import DocType
from ..domain.models import Chunk, Document, RetrievedChunk, Review


class DocumentRepository(ABC):
    @abstractmethod
    def create(self, doc: Document) -> Document: ...

    @abstractmethod
    def get(self, doc_id: str) -> Document | None: ...

    @abstractmethod
    def get_by_path(self, path: str) -> Document | None: ...

    @abstractmethod
    def list(self, doc_type: DocType | None = None) -> list[Document]: ...

    @abstractmethod
    def update(self, doc: Document) -> Document: ...

    @abstractmethod
    def delete(self, doc_id: str) -> None: ...


class VectorRepository(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        doc_types: list[DocType] | None = None,
    ) -> list[RetrievedChunk]: ...

    @abstractmethod
    def all_chunks(self, doc_types: list[DocType] | None = None) -> list[Chunk]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def reset_collection(self) -> None: ...

    @abstractmethod
    def dimension_matches(self, embedding_dim: int) -> bool: ...


class ReviewRepository(ABC):
    @abstractmethod
    def create(self, review: Review) -> Review: ...

    @abstractmethod
    def get(self, review_id: str) -> Review | None: ...

    @abstractmethod
    def update(self, review: Review) -> Review: ...

    @abstractmethod
    def list(self) -> list[Review]: ...

    @abstractmethod
    def delete(self, review_id: str) -> None: ...

    @abstractmethod
    def mark_stale_running_failed(self) -> int: ...


class SettingsRepository(ABC):
    @abstractmethod
    def get(self) -> dict | None: ...

    @abstractmethod
    def save(self, data: dict) -> None: ...


class RulesRepository(ABC):
    @abstractmethod
    def list(self) -> list[RuleConfig]: ...

    @abstractmethod
    def get(self, rule_id: str) -> RuleConfig | None: ...

    @abstractmethod
    def create(self, rule: RuleConfig) -> RuleConfig: ...

    @abstractmethod
    def update(self, rule: RuleConfig) -> RuleConfig: ...

    @abstractmethod
    def delete(self, rule_id: str) -> None: ...

    @abstractmethod
    def replace_all(self, rules: list[RuleConfig]) -> None: ...


class LlmPort(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        format: str | None = None,
        temperature: float | None = None,
        images: list[bytes] | None = None,
        step: str | None = None,
    ) -> str: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def list_models(self) -> list[str]: ...

    @abstractmethod
    def ping(self) -> bool: ...
