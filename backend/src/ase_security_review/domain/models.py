from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .enums import DocStatus, DocType, ExtractionMode, ReviewStatus, TestLevel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Document:
    id: str
    name: str
    doc_type: DocType
    status: DocStatus
    path: str
    content_hash: str
    is_locked: bool = False
    pages: int | None = None
    plaintext_path: str | None = None
    extraction_mode: ExtractionMode | None = None
    chunk_count: int | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class Chunk:
    id: str
    document_id: str
    doc_type: DocType
    doc_name: str
    text: str
    chunk_index: int = 0
    source: str = ""
    embedding: list[float] | None = None


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float
    source: str = ""
    doc_type: DocType | None = None
    doc_name: str = ""


@dataclass
class Scope:
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    test_methods: list[str] = field(default_factory=list)
    environments: list[str] = field(default_factory=list)
    effort_estimate: str = ""


@dataclass
class SecurityDecision:
    requires_pentest: bool
    test_level: TestLevel
    classification_reason: str
    risk_factors: list[str] = field(default_factory=list)
    scope: Scope = field(default_factory=Scope)
    recommended_frameworks: list[str] = field(default_factory=list)


@dataclass
class FiredRule:
    id: str
    name: str
    test_level: TestLevel
    priority: str
    reasoning: str
    frameworks: list[str] = field(default_factory=list)


@dataclass
class Conflict:
    field: str
    rules_value: Any
    llm_value: Any
    explanation: str = ""


@dataclass
class Review:
    id: str
    status: ReviewStatus
    frd_name: str
    nfrd_name: str
    frd_text: str = ""
    nfrd_text: str = ""
    facts: dict[str, Any] | None = None
    retrieved_sources: list[str] = field(default_factory=list)
    rules_fired: list[FiredRule] = field(default_factory=list)
    llm_decision: SecurityDecision | None = None
    rule_test_level: TestLevel | None = None
    conflicts: list[Conflict] = field(default_factory=list)
    final_decision: SecurityDecision | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
