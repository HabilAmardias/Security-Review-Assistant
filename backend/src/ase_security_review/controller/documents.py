"""Document (knowledge base) HTTP routes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from ..domain.enums import DocStatus, DocType, ExtractionMode
from .deps import get_container, run_backend
from .schemas import document_to_dict

router = APIRouter(prefix="/api/documents", tags=["documents"])


class UnlockRequest(BaseModel):
    password: str


class OcrRequest(BaseModel):
    password: Optional[str] = None


def _resolve_doc_type(value: str) -> DocType:
    try:
        return DocType(value)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid doc_type: {value}. Must be one of sop, policy, previous") from exc


@router.get("")
def list_documents(request: Request, doc_type: Optional[str] = Query(None)):
    c = get_container(request)
    dt = _resolve_doc_type(doc_type) if doc_type else None
    return [document_to_dict(d) for d in c.documents.list(dt)]


@router.post("")
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    mode: Optional[str] = Form(None),
):
    c = get_container(request)
    dt = _resolve_doc_type(doc_type)
    ext = Path(file.filename or "doc.pdf").suffix.lower()
    if ext != ".pdf":
        raise HTTPException(400, "Knowledge base documents must be PDF files")

    dest = c.config.documents_dir / f"{file.filename or 'upload.pdf'}"
    if dest.exists():
        dest = c.config.documents_dir / f"{file.filename}.{dest.stat().st_size}"
    dest.write_bytes(file.file.read())

    doc = c.ingestion.register_file(dest, dt)
    if mode:
        try:
            doc.extraction_mode = ExtractionMode(mode)
        except ValueError as exc:
            raise HTTPException(400, f"Invalid mode: {mode}") from exc
        c.documents.update(doc)

    run_backend(c.ingestion.index_document, doc.id)
    return document_to_dict(doc)


@router.post("/rescan")
def rescan_dropbox(request: Request):
    c = get_container(request)
    count = c.watcher.scan_now()
    return {"enqueued": count}


@router.post("/reindex")
def reindex_documents(request: Request):
    c = get_container(request)
    run_backend(c.ingestion.reindex_all)
    return {"started": True}


@router.post("/{doc_id}/unlock")
def unlock_document(doc_id: str, body: UnlockRequest, request: Request):
    c = get_container(request)
    doc = c.documents.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.is_locked:
        raise HTTPException(400, "Document is not password-protected")
    run_backend(c.ingestion.unlock_and_index, doc_id, body.password)
    return document_to_dict(doc)


@router.post("/{doc_id}/ocr")
def run_ocr(doc_id: str, body: OcrRequest, request: Request):
    c = get_container(request)
    doc = c.documents.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    run_backend(c.ingestion.run_ocr, doc_id, body.password)
    return document_to_dict(doc)


@router.get("/{doc_id}/progress")
def doc_progress(doc_id: str, request: Request):
    c = get_container(request)
    doc = c.documents.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return document_to_dict(doc)


@router.delete("/{doc_id}")
def delete_document(doc_id: str, request: Request):
    c = get_container(request)
    c.ingestion.delete(doc_id)
    return {"deleted": doc_id}
