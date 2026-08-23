"""PDF text extraction with in-memory password decryption (password never persisted)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PasswordType, PdfReader

from ..config.settings import ExtractionConfig


class LockedPdfError(Exception):
    pass


class InvalidPasswordError(Exception):
    pass


class OcrUnavailableError(Exception):
    pass


@dataclass
class PdfTextResult:
    text: str
    pages: int


class PdfExtractionService:
    def __init__(self, config: ExtractionConfig):
        self._config = config

    def inspect(self, path: Path) -> tuple[bool, int | None]:
        """Return (is_locked, page_count). Page count is None while locked."""
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            return True, None
        try:
            return False, len(reader.pages)
        except Exception:
            return False, None

    def extract_text(self, path: Path, password: str | None = None) -> PdfTextResult:
        """Extract the text layer of a PDF.

        If the PDF is locked, ``password`` is used only in-memory to decrypt and is
        never written to disk, the DB, or logs.
        """
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            if reader.decrypt(password or "") is PasswordType.NOT_DECRYPTED:
                if not password:
                    raise LockedPdfError("PDF is password-protected")
                raise InvalidPasswordError("Incorrect password for PDF")
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        return PdfTextResult(text="\n".join(parts), pages=len(reader.pages))

    def density_low(self, result: PdfTextResult) -> bool:
        if result.pages <= 0:
            return True
        return (len(result.text.strip()) / result.pages) < self._config.auto_detect_threshold

    def run_ocr(self, path: Path, out_path: Path) -> PdfTextResult:
        """Run OCR via ocrmypdf (requires tesseract installed) and return extracted text."""
        try:
            import ocrmypdf
        except ImportError as exc:
            raise OcrUnavailableError(
                "ocrmypdf is not installed. Install it with: pip install ocrmypdf "
                "(and 'brew install tesseract tesseract-lang')"
            ) from exc

        try:
            ocrmypdf.ocr(
                str(path),
                str(out_path),
                language=self._config.ocr_language,
                deskew=True,
                force_ocr=True,
            )
        except Exception as exc:
            if "tesseract" in str(exc).lower() or "not found" in str(exc).lower():
                raise OcrUnavailableError(
                    "Tesseract OCR binary not found. Install it with: brew install tesseract tesseract-lang"
                ) from exc
            raise
        return self.extract_text(out_path)
