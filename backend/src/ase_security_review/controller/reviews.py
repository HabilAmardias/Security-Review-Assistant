"""Review HTTP routes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ..domain.models import Scope, SecurityDecision
from ..domain.enums import parse_test_level
from .deps import get_container, run_backend
from .schemas import review_to_dict

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class FinalDecisionRequest(BaseModel):
    requires_pentest: bool
    test_level: str = "dast"
    classification_reason: str = ""
    risk_factors: list[str] = []
    scope: dict | None = None


class ExposureRequest(BaseModel):
    exposure: str | None = None  # internal | internet-facing | partner | null (clear override)


_PDF_MAGIC = b"%PDF"


def _read_upload(request: Request, file: UploadFile, password: str | None):
    """Read an FRD/NFRD upload. PDFs are detected by content (magic bytes), not the
    filename extension. Returns (text, form_fields, detected_exposure)."""
    content = file.file.read()

    if content.startswith(_PDF_MAGIC):
        c = get_container(request)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "input.pdf"
            pdf_path.write_bytes(content)
            try:
                result = c.extraction.extract_text(pdf_path, password=password)
                form_fields = c.extraction.extract_form_fields(pdf_path, password=password)
                detected = c.extraction.exposure_from_form_fields(form_fields)
                return result.text, form_fields, detected
            except Exception as exc:
                raise HTTPException(400, f"Could not read PDF '{file.filename}': {exc}") from exc

    # Markdown / plain text: strip a UTF-8 BOM, then decode.
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    return content.decode("utf-8", errors="replace"), [], None


@router.post("")
async def create_review(
    request: Request,
    frd: UploadFile = File(...),
    nfrd: UploadFile = File(...),
    frd_password: Optional[str] = Form(None),
    nfrd_password: Optional[str] = Form(None),
    exposure: Optional[str] = Form(None),
):
    c = get_container(request)
    try:
        frd_text, frd_fields, frd_exposure = _read_upload(request, frd, frd_password)
        nfrd_text, nfrd_fields, nfrd_exposure = _read_upload(request, nfrd, nfrd_password)
    except Exception as exc:
        raise HTTPException(400, f"Could not read input documents: {exc}") from exc

    if not frd_text.strip() or not nfrd_text.strip():
        raise HTTPException(400, "Both FRD and NFRD must contain extractable text")

    form_fields = frd_fields + nfrd_fields
    detected_exposure = nfrd_exposure or frd_exposure
    review = c.review_usecase.create_review(
        frd.filename or "frd.pdf",
        frd_text,
        nfrd.filename or "nfrd.pdf",
        nfrd_text,
        detected_exposure=detected_exposure,
        exposure_override=exposure if exposure and exposure != "auto" else None,
        form_fields=form_fields,
    )
    run_backend(c.review_usecase.run_review, review.id)
    return review_to_dict(review)


@router.get("")
def list_reviews(request: Request):
    c = get_container(request)
    return [review_to_dict(r) for r in c.reviews.list()]


@router.get("/{review_id}")
def get_review(review_id: str, request: Request):
    c = get_container(request)
    review = c.reviews.get(review_id)
    if not review:
        raise HTTPException(404, "Review not found")
    return review_to_dict(review, include_texts=True)


@router.delete("/{review_id}")
def delete_review(review_id: str, request: Request):
    c = get_container(request)
    if not c.reviews.get(review_id):
        raise HTTPException(404, "Review not found")
    c.reviews.delete(review_id)
    return {"deleted": review_id}


@router.patch("/{review_id}/exposure")
def update_exposure(review_id: str, body: ExposureRequest, request: Request):
    c = get_container(request)
    if not c.reviews.get(review_id):
        raise HTTPException(404, "Review not found")
    review = c.review_usecase.update_exposure(review_id, body.exposure)
    return review_to_dict(review, include_texts=True)


@router.patch("/{review_id}/decision")
def set_final_decision(review_id: str, body: FinalDecisionRequest, request: Request):
    c = get_container(request)
    level = parse_test_level(body.test_level)

    scope = body.scope or {}
    decision = SecurityDecision(
        requires_pentest=body.requires_pentest,
        test_level=level,
        classification_reason=body.classification_reason,
        risk_factors=list(body.risk_factors),
        scope=Scope(
            in_scope=list(scope.get("in_scope") or []),
            out_of_scope=list(scope.get("out_of_scope") or []),
            test_methods=list(scope.get("test_methods") or []),
            environments=list(scope.get("environments") or []),
            effort_estimate=scope.get("effort_estimate") or "",
        ),
    )
    review = c.review_usecase.set_final_decision(review_id, decision)
    return review_to_dict(review, include_texts=True)
