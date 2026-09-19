"""Configuration.

Infrastructure settings come from the environment (`.env`). Business-logic
settings and compliance rules are mutable, persisted in the database, and edited
via the UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# --------------------------------------------------------------------------- #
# Infrastructure (.env)
# --------------------------------------------------------------------------- #

class InfraSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASE_", extra="ignore")

    ollama_base_url: str = "http://127.0.0.1:11434"
    request_timeout_sec: Optional[int] = None
    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    asyncio_debug: bool = False
    log_level: str = "INFO"


# --------------------------------------------------------------------------- #
# Business logic (defaults in code, editable via UI, persisted in DB)
# --------------------------------------------------------------------------- #

class LlmConfig(BaseModel):
    reasoning_model: str = "qwen2.5:7b-instruct-q4_K_M"
    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_dim: int = 1024
    temperature: float = 0.1
    max_tokens: int = 4096
    num_ctx: int = 16384
    # Per-step reasoning toggle for every LLM call, keyed by step name
    # (fact_extraction, diagrams, requirement, architecture, assets, threats,
    # decision). An unlisted step defaults to false (safe for JSON output).
    thinking: dict[str, bool] = {}


class ExtractionConfig(BaseModel):
    default_mode: str = "auto"  # auto | text | ocr
    auto_detect_threshold: int = Field(50, description="chars/page below which a doc is flagged NEEDS_OCR")
    ocr_language: str = "eng"  # tesseract language(s), e.g. "eng", "ind", "eng+ind"
    diagram_dpi: int = Field(150, description="DPI used to rasterize image-bearing PDF pages")
    max_diagram_pages: int = Field(8, description="max image-bearing pages sent to the vision model")


class RetrievalConfig(BaseModel):
    chunk_size: int = 900
    chunk_overlap: int = 120
    embed_batch_size: int = 64
    retrieval_top_k: int = 6
    review_max_input_chars: int = 60000
    # Rules (intranet DAST cap, internet DAST floor) act as hard bounds inside the
    # threat-model pipeline. Set to false to keep the rule engine dormant.
    enable_rule_engine: bool = True


class BusinessSettings(BaseModel):
    llm: LlmConfig = Field(default_factory=LlmConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)


# --------------------------------------------------------------------------- #
# Compliance rules (persisted in the DB, managed via the Rules page)
# --------------------------------------------------------------------------- #

class RuleTriggerConfig(BaseModel):
    data_classes: list[str] = []
    keywords: list[str] = []
    features: list[str] = []
    # Matches the structured `exposure` fact: internal | internet-facing | partner
    exposure: list[str] = []


class RuleActionConfig(BaseModel):
    test_level: str  # pentest | dast | none
    priority: str = "medium"  # high | medium | low
    cap: str | None = None

    @field_validator("test_level")
    @classmethod
    def _check_test_level(cls, v: str) -> str:
        if v not in ("pentest", "dast", "none"):
            raise ValueError("test_level must be one of: pentest, dast, none")
        return v

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, v: str) -> str:
        if v not in ("high", "medium", "low"):
            raise ValueError("priority must be one of: high, medium, low")
        return v

    @field_validator("cap")
    @classmethod
    def _check_cap(cls, v: str | None) -> str | None:
        if v is not None and v not in ("pentest", "dast", "none"):
            raise ValueError("cap must be one of: pentest, dast, none")
        return v


class RuleConfig(BaseModel):
    id: str
    name: str
    enabled: bool = True
    triggers: RuleTriggerConfig
    action: RuleActionConfig
    reasoning: str


class ComplianceConfig(BaseModel):
    rules: list[RuleConfig] = []


# --------------------------------------------------------------------------- #
# App config
# --------------------------------------------------------------------------- #

class AppConfig(BaseModel):
    infra: InfraSettings = Field(default_factory=InfraSettings)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)

    # ---- infra shortcuts ----
    @property
    def data_dir(self) -> Path:
        return self.infra.data_dir

    @property
    def diagrams_dir(self) -> Path:
        return self.infra.data_dir / "diagrams"

    @property
    def documents_dir(self) -> Path:
        return self.infra.data_dir / "documents"

    @property
    def extracted_dir(self) -> Path:
        return self.infra.data_dir / "extracted"

    @property
    def chroma_dir(self) -> Path:
        return self.infra.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.infra.data_dir / "app.db"

    @property
    def asyncio_debug(self) -> bool:
        return self.infra.asyncio_debug

    # ---- business shortcuts ----
    @property
    def chunk_size(self) -> int:
        return self.retrieval.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self.retrieval.chunk_overlap

    @property
    def embed_batch_size(self) -> int:
        return self.retrieval.embed_batch_size

    @property
    def retrieval_top_k(self) -> int:
        return self.retrieval.retrieval_top_k

    @property
    def review_max_input_chars(self) -> int:
        return self.retrieval.review_max_input_chars

    @property
    def enable_rule_engine(self) -> bool:
        return self.retrieval.enable_rule_engine


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge `override` into a copy of `base` (dicts only)."""
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def business_from_dict(data: dict | None) -> BusinessSettings:
    """Build business settings from code defaults overlaid with stored values."""
    return BusinessSettings.model_validate(deep_merge(BusinessSettings().model_dump(), data or {}))


def build_config(
    infra: InfraSettings | None = None,
    business: dict | None = None,
    rules: list[RuleConfig] | None = None,
) -> AppConfig:
    infra = infra or InfraSettings()
    settings = business_from_dict(business)
    return AppConfig(
        infra=infra,
        llm=settings.llm,
        extraction=settings.extraction,
        retrieval=settings.retrieval,
        compliance=ComplianceConfig(rules=rules or []),
    )
