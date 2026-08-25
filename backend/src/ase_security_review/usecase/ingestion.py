"""Ingestion use case: register files, extract text (with one-time in-memory
password decryption), chunk, embed in batches, and index into the vector store.

Security: a PDF password is used only in-memory during decryption and is never
persisted, logged, or sent to the LLM. Decrypted *content* is cached as plaintext
so re-indexing never requires the password again.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from ..config.settings import AppConfig
from ..domain.enums import DocStatus, DocType, ExtractionMode
from ..domain.models import Chunk, Document
from ..repository.base import DocumentRepository, LlmPort, VectorRepository
from ..data.file_store import load_plaintext, save_plaintext, sha256_of_file
from .chunking import chunk_text
from .extraction import InvalidPasswordError, LockedPdfError, PdfExtractionService, PdfTextResult


def _new_id() -> str:
    return uuid.uuid4().hex


class IngestionUseCase:
    def __init__(
        self,
        config: AppConfig,
        docs: DocumentRepository,
        vectors: VectorRepository,
        llm: LlmPort,
        extraction: PdfExtractionService,
    ):
        self._config = config
        self._docs = docs
        self._vectors = vectors
        self._llm = llm
        self._extraction = extraction

    # ---- registration -----------------------------------------------------

    def register_file(self, path: Path, doc_type: DocType) -> Document:
        """Register a PDF found in the drop folder / upload. Idempotent by content hash.

        A file with the same path but a new hash replaces the previous version
        (old chunks are deleted, a fresh document is indexed).
        """
        path = Path(path)
        content_hash = sha256_of_file(path)
        existing = self._docs.get_by_path(str(path))
        if existing and existing.content_hash == content_hash:
            return existing
        if existing:
            self._vectors.delete_document(existing.id)
            self._docs.delete(existing.id)

        try:
            is_locked, pages = self._extraction.inspect(path)
        except Exception:
            is_locked, pages = False, None

        doc = Document(
            id=_new_id(),
            name=path.name,
            doc_type=doc_type,
            status=DocStatus.PENDING,
            path=str(path),
            content_hash=content_hash,
            is_locked=is_locked,
            pages=pages,
        )
        return self._docs.create(doc)

    # ---- indexing ---------------------------------------------------------

    def index_document(self, doc_id: str, password: str | None = None) -> Document:
        """Run the full pipeline for a document. ``password`` is only ever held in
        memory for the duration of decryption."""
        doc = self._docs.get(doc_id)
        if not doc:
            raise KeyError(f"Document {doc_id} not found")
        path = Path(doc.path)

        # Reuse cached plaintext if present (no password needed again).
        if doc.plaintext_path and Path(doc.plaintext_path).exists():
            return self._index_text(doc, load_plaintext(Path(doc.plaintext_path)))

        mode = doc.extraction_mode or ExtractionMode(self._config.extraction.default_mode)

        # Decrypt + extract text.
        if doc.is_locked or self._is_locked(path):
            if not password:
                self._set_status(doc, DocStatus.NEEDS_PASSWORD)
                return doc
            try:
                result = self._extraction.extract_text(path, password=password)
            except InvalidPasswordError:
                self._set_status(doc, DocStatus.FAILED, error="Incorrect password for PDF")
                return doc
            except LockedPdfError:
                self._set_status(doc, DocStatus.NEEDS_PASSWORD)
                return doc
            doc.is_locked = False
        else:
            result = self._extraction.extract_text(path)

        # Decide whether OCR is needed.
        if mode == ExtractionMode.AUTO and self._extraction.density_low(result):
            return self._prepare_ocr(doc, result, password)
        if mode == ExtractionMode.OCR:
            result = self._ocr(doc, result, password)
            doc.is_locked = False

        doc.extraction_mode = mode
        doc.pages = result.pages
        return self._index_text(doc, result.text)

    def unlock_and_index(self, doc_id: str, password: str) -> Document:
        return self.index_document(doc_id, password=password)

    def run_ocr(self, doc_id: str, password: str | None = None) -> Document:
        doc = self._docs.get(doc_id)
        if not doc:
            raise KeyError(f"Document {doc_id} not found")
        doc.extraction_mode = ExtractionMode.OCR
        self._docs.update(doc)
        return self.index_document(doc_id, password=password)

    def delete(self, doc_id: str) -> None:
        self._vectors.delete_document(doc_id)
        doc = self._docs.get(doc_id)
        if doc and doc.plaintext_path:
            Path(doc.plaintext_path).unlink(missing_ok=True)
        self._docs.delete(doc_id)

    def reindex_all(self) -> dict:
        """Rebuild the whole vector index from the plaintext cache. Used when the
        embedding model (and thus the vector dimension) changes: the old index is
        reset, then every document with a cached plaintext is re-chunked and
        re-embedded with the current model. No PDFs or passwords are needed."""
        self._vectors.reset_collection()
        docs = self._docs.list()
        ok = 0
        skipped: list[dict] = []
        for doc in docs:
            if doc.plaintext_path and Path(doc.plaintext_path).exists():
                self._index_text(doc, load_plaintext(Path(doc.plaintext_path)))
                ok += 1
            else:
                skipped.append({"id": doc.id, "name": doc.name, "status": doc.status.value})
        return {"reindexed": ok, "skipped": skipped}

    # ---- internals --------------------------------------------------------

    def _is_locked(self, path: Path) -> bool:
        try:
            locked, _ = self._extraction.inspect(path)
            return locked
        except Exception:
            return False

    def _prepare_ocr(self, doc: Document, result: PdfTextResult, password: str | None = None) -> Document:
        """Auto mode with low text density: persist a decrypted copy (if locked) so
        OCR can run later without asking for the password again."""
        if self._is_locked(Path(doc.path)):
            if not password:
                self._set_status(doc, DocStatus.NEEDS_PASSWORD)
                return doc
            self._write_decrypted_copy(doc, password)
            doc.is_locked = False
        doc.pages = result.pages
        self._set_status(doc, DocStatus.NEEDS_OCR)
        return doc

    def _write_decrypted_copy(self, doc: Document, password: str) -> None:
        """Write a decrypted PDF copy for OCR use. Same trust level as the plaintext
        cache; the password itself is still discarded."""
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(Path(doc.path)))
        reader.decrypt(password)
        dest = self._config.extracted_dir / f"{doc.id}_decrypted.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with dest.open("wb") as fh:
            writer.write(fh)

    def _ocr(self, doc: Document, result: PdfTextResult, password: str | None) -> PdfTextResult:
        src = Path(doc.path)
        decrypted = self._config.extracted_dir / f"{doc.id}_decrypted.pdf"
        if decrypted.exists():
            src = decrypted
        elif self._is_locked(src):
            self._write_decrypted_copy(doc, password or "")
            src = decrypted
        try:
            out = self._config.extracted_dir / f"{doc.id}_ocr.pdf"
            return self._extraction.run_ocr(src, out)
        finally:
            if decrypted.exists():
                decrypted.unlink(missing_ok=True)

    def _index_text(self, doc: Document, text: str) -> Document:
        self._set_status(doc, DocStatus.EXTRACTING)
        try:
            plaintext_path = save_plaintext(self._config.extracted_dir, doc.id, text)
            doc.plaintext_path = str(plaintext_path)

            self._set_status(doc, DocStatus.CHUNKING)
            pieces = chunk_text(text, self._config.chunk_size, self._config.chunk_overlap)
            chunks = [
                Chunk(
                    id=f"{doc.id}:{i}",
                    document_id=doc.id,
                    doc_type=doc.doc_type,
                    doc_name=doc.name,
                    text=piece,
                    chunk_index=i,
                    source=str(Path(doc.path)),
                )
                for i, piece in enumerate(pieces)
            ]

            self._set_status(doc, DocStatus.EMBEDDING)
            batch = self._config.embed_batch_size
            for start in range(0, len(chunks), batch):
                group = chunks[start : start + batch]
                embeddings = self._llm.embed([c.text for c in group])
                for chunk, emb in zip(group, embeddings):
                    chunk.embedding = emb
                self._vectors.upsert_chunks(group)

            doc.chunk_count = len(chunks)
            self._set_status(doc, DocStatus.READY)
            return doc
        except Exception as exc:
            self._set_status(doc, DocStatus.FAILED, error=str(exc))
            raise

    def _set_status(self, doc: Document, status: DocStatus, error: str | None = None) -> Document:
        from datetime import datetime, timezone

        doc.status = status
        doc.error = error
        doc.updated_at = datetime.now(timezone.utc)
        return self._docs.update(doc)
