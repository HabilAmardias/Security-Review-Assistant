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


@dataclass
class FiredRule:
    id: str
    name: str
    test_level: TestLevel
    priority: str
    reasoning: str
    cap: TestLevel | None = None


@dataclass
class Conflict:
    field: str
    rules_value: Any
    llm_value: Any
    explanation: str = ""


@dataclass
class FormField:
    label: str = ""
    options: list[str] = field(default_factory=list)
    selected: list[str] = field(default_factory=list)
    source_line: str = ""
    page: int = 1


@dataclass
class Review:
    id: str
    status: ReviewStatus
    frd_name: str
    nfrd_name: str
    frd_text: str = ""
    nfrd_text: str = ""
    facts: dict[str, Any] | None = None
    rule_engine_enabled: bool = True
    # pipeline (threat-model) used for this review
    pipeline: str = "threat"
    # current pipeline stage label (for progress)
    current_stage: str = ""
    # staged analysis artifacts: diagrams, requirement, architecture, assets, threat_model
    analysis: dict[str, Any] | None = None
    # paths to rasterized diagram images (cleaned up on delete)
    diagram_paths: list[str] = field(default_factory=list)
    # app exposure derived from the PDF form fields
    detected_exposure: str | None = None
    # human-confirmed exposure override (internal | internet-facing | partner)
    exposure_override: str | None = None
    # human-confirmed change-scope override (limited_change | feature_change | full_new_app | other)
    change_scope_override: str | None = None
    # deterministic form selections extracted from the FRD/NFRD PDFs
    form_fields: list[FormField] = field(default_factory=list)
    retrieved_sources: list[str] = field(default_factory=list)
    rules_fired: list[FiredRule] = field(default_factory=list)
    llm_decision: SecurityDecision | None = None
    rule_test_level: TestLevel | None = None
    conflicts: list[Conflict] = field(default_factory=list)
    final_decision: SecurityDecision | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
