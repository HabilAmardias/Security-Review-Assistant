from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LlmConfig(BaseModel):
    base_url: str = "http://127.0.0.1:11434"
    reasoning_model: str = "qwen2.5:7b-instruct-q4_K_M"
    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_dim: int = 1024
    temperature: float = 0.1
    max_tokens: int = 4096
    request_timeout_sec: int = 300


class ExtractionConfig(BaseModel):
    default_mode: str = "auto"  # auto | text | ocr
    auto_detect_threshold: int = Field(50, description="chars/page below which a doc is flagged NEEDS_OCR")
    ocr_language: str = "eng"  # tesseract language(s), e.g. "eng", "ind", "eng+ind"


class FrameworkConfig(BaseModel):
    name: str
    description: str = ""
    test_level: str = "both"  # hint: pentest | dast | both


class RuleTriggerConfig(BaseModel):
    data_classes: list[str] = []
    keywords: list[str] = []
    features: list[str] = []


class RuleActionConfig(BaseModel):
    test_level: str  # pentest | dast | both | none
    priority: str = "medium"  # high | medium | low


class RuleConfig(BaseModel):
    id: str
    name: str
    triggers: RuleTriggerConfig
    action: RuleActionConfig
    reasoning: str
    frameworks: list[str] = []


class ComplianceConfig(BaseModel):
    enabled: list[str] = []
    frameworks: dict[str, FrameworkConfig] = {}
    rules: list[RuleConfig] = []


class AppConfig(BaseModel):
    llm: LlmConfig = Field(default_factory=LlmConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)

    data_dir: Path = Path("data")
    poll_interval_sec: int = 10
    chunk_size: int = 900
    chunk_overlap: int = 120
    embed_batch_size: int = 64
    retrieval_top_k: int = 6
    review_max_input_chars: int = 60000
    asyncio_debug: bool = False

    @property
    def dropbox_dir(self) -> Path:
        return self.data_dir / "dropbox"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def extracted_dir(self) -> Path:
        return self.data_dir / "extracted"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def dropbox_folders(self) -> dict[str, Path]:
        return {
            "sop": self.dropbox_dir / "sop",
            "policy": self.dropbox_dir / "policy",
            "previous": self.dropbox_dir / "previous",
        }


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(config_path: Path | None = None, compliance_path: Path | None = None) -> AppConfig:
    config_path = config_path or Path(__file__).resolve().parent.parent.parent.parent / "config" / "config.yaml"
    compliance_path = compliance_path or Path(__file__).resolve().parent.parent.parent.parent / "config" / "compliance.yaml"

    raw = load_yaml(config_path)
    compliance_raw = load_yaml(compliance_path)

    if not raw:
        return AppConfig()

    llm_raw = raw.get("llm", {})
    extraction_raw = raw.get("extraction", {})

    # derive data_dir from config file location if not overridden
    data_dir = Path(raw["data_dir"]) if raw.get("data_dir") else Path(__file__).resolve().parent.parent.parent.parent / "data"

    # top-level knobs
    def knobs() -> dict[str, Any]:
        keys = [
            "poll_interval_sec", "chunk_size", "chunk_overlap", "embed_batch_size",
            "retrieval_top_k", "review_max_input_chars", "asyncio_debug",
        ]
        return {k: raw[k] for k in keys if k in raw}

    compliance = ComplianceConfig(**compliance_raw.get("compliance", {})) if compliance_raw.get("compliance") else ComplianceConfig()

    return AppConfig(
        llm=LlmConfig(**llm_raw),
        extraction=ExtractionConfig(**extraction_raw),
        compliance=compliance,
        data_dir=data_dir,
        **knobs(),
    )
