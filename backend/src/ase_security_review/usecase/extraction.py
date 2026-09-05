"""PDF text extraction with in-memory password decryption (password never persisted)."""

from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path

from pypdf import PasswordType, PdfReader

from ..config.settings import ExtractionConfig
from ..domain.models import FormField


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


@dataclass
class PdfImage:
    page: int
    data: bytes
    width: int = 0
    height: int = 0


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

    def extract_images(self, path: Path, password: str | None = None) -> list[PdfImage]:
        """Rasterize pages that contain embedded images (e.g. diagrams) into PNGs.
        Used to feed diagrams to a vision-capable model."""
        import pymupdf

        doc = pymupdf.open(str(path))
        try:
            if doc.needs_pass:
                doc.authenticate(password or "")
            images: list[PdfImage] = []
            for pno in range(min(len(doc), self._config.max_diagram_pages + 1)):
                page = doc[pno]
                if not page.get_images(full=True):
                    continue
                zoom = self._config.diagram_dpi / 72.0
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
                if pix.width > 1600 or pix.height > 1600:
                    scale = min(1600 / pix.width, 1600 / pix.height)
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom * scale, zoom * scale))
                images.append(PdfImage(page=pno + 1, data=pix.tobytes("png"), width=pix.width, height=pix.height))
                if len(images) >= self._config.max_diagram_pages:
                    break
            return images
        finally:
            doc.close()

    # ---- deterministic form-field extraction (colour-outlier selection) ----

    _LINK_BLUE = 0x579DDF
    _CLUSTER_GAP = 25.0  # vertical pt gap between stacked options of the same field

    def extract_form_fields(self, path: Path, password: str | None = None) -> list[FormField]:
        """Detect form fields where a label line is followed by stacked option lines
        and the selected option(s) are rendered in a distinct accent colour.
        Returns one FormField per field that has a selection."""
        import pymupdf

        doc = pymupdf.open(str(path))
        try:
            if doc.needs_pass:
                doc.authenticate(password or "")
            lines = self._collect_lines(doc)
            sel_color = self._detect_selection_color(lines)
            if sel_color is None:
                return []
            return self._build_fields(lines, sel_color)
        finally:
            doc.close()

    @staticmethod
    def _collect_lines(doc) -> list[dict]:
        lines: list[dict] = []
        for pno in range(len(doc)):
            for block in doc[pno].get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    text = "".join(s["text"] for s in line.get("spans", [])).strip()
                    if not text:
                        continue
                    spans = line.get("spans", [])
                    color = spans[0]["color"] if len({s["color"] for s in spans}) <= 1 else min(s["color"] for s in spans)
                    lines.append(
                        {
                            "page": pno + 1,
                            "y0": line["bbox"][1],
                            "color": color,
                            "text": text,
                            "words": len(text.split()),
                        }
                    )
        lines.sort(key=lambda l: (l["page"], l["y0"]))
        return lines

    @classmethod
    def _detect_selection_color(cls, lines: list[dict]) -> int | None:
        """The accent colour used for selected options: a colour that appears on at
        least two 'clean short lines' (option values), is not a body-text colour
        (the two most common colours on the page) nor a hyperlink colour."""
        import collections

        def clean(l: dict) -> bool:
            return 1 <= l["words"] <= 5 and not l["text"].rstrip().endswith(":")

        overall = collections.Counter(l["color"] for l in lines)
        body_colors = {c for c, _ in overall.most_common(2)}
        cand: collections.Counter = collections.Counter()
        for l in lines:
            if not clean(l) or l["color"] == cls._LINK_BLUE or l["color"] in body_colors:
                continue
            cand[l["color"]] += 1
        if not cand:
            return None
        color, n = cand.most_common(1)[0]
        return color if n >= 2 else None

    @classmethod
    def _is_label_line(cls, l: dict) -> bool:
        t = l["text"].rstrip()
        return (
            t.endswith(":")
            and not t.startswith("Lainnya")
            and l["words"] <= 12
        )

    @classmethod
    def _is_option_line(cls, l: dict) -> bool:
        if not (1 <= l["words"] <= 5) or l["color"] == cls._LINK_BLUE:
            return False
        if "http" in l["text"].lower() or "=" in l["text"]:
            return False
        return not cls._is_label_line(l)

    @classmethod
    def _build_fields(cls, lines: list[dict], sel_color: int) -> list[FormField]:
        fields: list[FormField] = []
        cur_label = ""
        label_hint = ""
        cluster: list[dict] = []

        def flush() -> None:
            nonlocal cluster, cur_label
            if not cluster:
                return
            # only keep lines in the unselected options' dominant colour + the
            # selection colour (drops interleaved muted-note fragments)
            non_sel = [l for l in cluster if l["color"] != sel_color]
            if non_sel:
                dominant = collections.Counter(l["color"] for l in non_sel).most_common(1)[0][0]
                cluster = [l for l in cluster if l["color"] in (dominant, sel_color)]
            selected = [l["text"] for l in cluster if l["color"] == sel_color]
            # keep only fields with several options and a proper (non-all) selection
            if selected and 2 <= len(cluster) <= 12 and len(selected) < len(cluster):
                fields.append(
                    FormField(
                        label=(cur_label or label_hint or "").rstrip(":").strip(),
                        options=[l["text"] for l in cluster],
                        selected=selected,
                        source_line=" | ".join(l["text"] for l in cluster),
                        page=cluster[0]["page"],
                    )
                )
            cluster = []

        for l in lines:
            if cls._is_label_line(l):
                flush()
                cur_label = l["text"]
                label_hint = l["text"]
                continue
            if cls._is_option_line(l):
                if cluster and abs(l["y0"] - cluster[-1]["y0"]) > cls._CLUSTER_GAP:
                    flush()
                cluster.append(l)
                continue
            # prose / header line: remember it as a possible label hint
            t = l["text"].rstrip()
            if (t.endswith(":") or t.endswith("?")) and l["words"] <= 15 and not t.startswith("Lainnya"):
                label_hint = t
            if cluster and abs(l["y0"] - cluster[-1]["y0"]) > cls._CLUSTER_GAP * 3:
                flush()
        flush()
        return fields

    @staticmethod
    def exposure_from_form_fields(fields: list[FormField]) -> str | None:
        """Derive the app exposure from the detected form fields."""
        from ..domain.enums import Exposure

        for f in fields:
            hay = (f.label + " " + " ".join(f.options)).lower()
            if not any(k in hay for k in ("diakses", "akses", "exposure")):
                continue
            sel = " ".join(s.lower() for s in f.selected)
            if not sel:
                continue
            if "intranet" in sel or "internal" in sel:
                return Exposure.INTERNAL.value
            if "internet" in sel or "public" in sel:
                return Exposure.INTERNET_FACING.value
            if "partner" in sel or "external" in sel:
                return Exposure.PARTNER.value
        return None
