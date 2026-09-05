"""Review use case: create review records and delegate execution to the staged
threat-model pipeline. The deterministic rule engine acts as a HARD bound on the
final decision inside that pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..config.settings import AppConfig
from ..domain.enums import ReviewStatus
from ..domain.models import FormField, Review, SecurityDecision
from ..repository.base import LlmPort, ReviewRepository
from .fact_extraction import FactExtractionService
from .retrieval import RetrievalService

_UNSET = object()


class ReviewUseCase:
    def __init__(
        self,
        config: AppConfig,
        reviews: ReviewRepository,
        retrieval: RetrievalService,
        fact_extraction: FactExtractionService,
        llm: LlmPort,
    ):
        self._config = config
        self._reviews = reviews
        self._retrieval = retrieval
        self._facts = fact_extraction
        self._llm = llm
        from .threat_review import ThreatReviewPipeline

        self._threat = ThreatReviewPipeline(config, reviews, retrieval, fact_extraction, llm)

    def create_review(
        self,
        frd_name: str,
        frd_text: str,
        nfrd_name: str,
        nfrd_text: str,
        *,
        detected_exposure: str | None = None,
        exposure_override: str | None = None,
        change_scope_override: str | None = None,
        form_fields: list[FormField] | None = None,
        diagram_paths: list[str] | None = None,
    ) -> Review:
        review = Review(
            id=uuid.uuid4().hex,
            status=ReviewStatus.RUNNING,
            pipeline="threat",
            frd_name=frd_name,
            nfrd_name=nfrd_name,
            frd_text=frd_text,
            nfrd_text=nfrd_text,
            detected_exposure=detected_exposure,
            exposure_override=exposure_override,
            change_scope_override=change_scope_override,
            form_fields=form_fields or [],
            diagram_paths=diagram_paths or [],
        )
        return self._reviews.create(review)

    def run_review(self, review_id: str) -> Review:
        return self._threat.run(review_id)

    def apply_override(
        self,
        review_id: str,
        *,
        exposure: object = _UNSET,
        change_scope: object = _UNSET,
    ) -> Review:
        """Apply a human exposure / change-scope override and re-run the review
        pipeline with the corrected context. Passing None clears the override;
        omitting a parameter leaves it unchanged."""
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"Review {review_id} not found")
        if exposure is not _UNSET:
            review.exposure_override = exposure or None
        if change_scope is not _UNSET:
            review.change_scope_override = change_scope or None
        self._save(review)
        return self._threat.run(review_id)

    def set_final_decision(self, review_id: str, decision: SecurityDecision) -> Review:
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"Review {review_id} not found")
        review.final_decision = decision
        return self._save(review)

    def _save(self, review: Review) -> Review:
        review.updated_at = datetime.now(timezone.utc)
        return self._reviews.update(review)
