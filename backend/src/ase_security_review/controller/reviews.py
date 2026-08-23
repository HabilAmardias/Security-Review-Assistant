"""Review HTTP routes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ..domain.models import Scope, SecurityDecision
from ..domain.enums import TestLevel
from .deps import get_container, run_backend
from .schemas import review_to_dict

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class FinalDecisionRequest(BaseModel):
    requires_pentest: bool
    test_level: str = "dast"
    classification_reason: str = ""
    risk_factors: list[str] = []
    scope: dict | None = None
    recommended_frameworks: list[str] = []


def _read_text(request: Request, file: UploadFile, password: str | None) -> str:
    content = file.file.read()
    ext = Path(file.filename or "input.pdf").suffix.lower()
    if ext != ".pdf":
        return content.decode("utf-8", errors="replace")

    c = get_container(request)
    from pathlib import Path as P

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = P(tmp) / "input.pdf"
        pdf_path.write_bytes(content)
        try:
            return c.extraction.extract_text(pdf_path, password=password).text
        except Exception as exc:
            raise HTTPException(400, f"Could not read PDF '{file.filename}': {exc}") from exc


@router.post("")
async def create_review(
    request: Request,
    frd: UploadFile = File(...),
    nfrd: UploadFile = File(...),
    frd_password: Optional[str] = Form(None),
    nfrd_password: Optional[str] = Form(None),
):
    c = get_container(request)
    try:
        frd_text = _read_text(request, frd, frd_password)
        nfrd_text = _read_text(request, nfrd, nfrd_password)
    except Exception as exc:
        raise HTTPException(400, f"Could not read input documents: {exc}") from exc

    if not frd_text.strip() or not nfrd_text.strip():
        raise HTTPException(400, "Both FRD and NFRD must contain extractable text")

    review = c.review_usecase.create_review(
        frd.filename or "frd.pdf", frd_text, nfrd.filename or "nfrd.pdf", nfrd_text
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


@router.patch("/{review_id}/decision")
def set_final_decision(review_id: str, body: FinalDecisionRequest, request: Request):
    c = get_container(request)
    try:
        level = TestLevel(body.test_level)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid test_level: {body.test_level}") from exc

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
        recommended_frameworks=list(body.recommended_frameworks),
    )
    review = c.review_usecase.set_final_decision(review_id, decision)
    return review_to_dict(review, include_texts=True)
