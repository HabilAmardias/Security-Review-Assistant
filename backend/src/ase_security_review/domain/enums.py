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
    BOTH = "both"
    NONE = "none"


class ReviewStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
