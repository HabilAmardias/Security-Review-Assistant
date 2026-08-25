from enum import Enum


class DocType(str, Enum):
    SOP = "sop"
    POLICY = "policy"
    PREVIOUS_REVIEW = "previous"


class DocStatus(str, Enum):
    PENDING = "pending"
    NEEDS_PASSWORD = "needs_password"
    NEEDS_OCR = "needs_ocr"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class ExtractionMode(str, Enum):
    AUTO = "auto"
    TEXT = "text"
    OCR = "ocr"


class TestLevel(str, Enum):
    PENTEST = "pentest"
    DAST = "dast"
    NONE = "none"


class Exposure(str, Enum):
    INTERNAL = "internal"
    INTERNET_FACING = "internet-facing"
    PARTNER = "partner"
    UNCLEAR = "unclear"


def parse_test_level(value: str | None) -> TestLevel:
    """Tolerant parser for stored/LLM test levels. The legacy `both` value
    (pentest + DAST) was removed; the strongest remaining level is pentest."""
    if value == "both":
        return TestLevel.PENTEST
    try:
        return TestLevel(value)
    except (TypeError, ValueError):
        return TestLevel.DAST


class ReviewStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
