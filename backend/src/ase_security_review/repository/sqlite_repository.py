"""SQLite implementations of the document and review repositories."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..data.models import DocumentRow, ReviewRow
from ..domain.enums import DocStatus, DocType, ExtractionMode, ReviewStatus, TestLevel
from ..domain.models import Document, Review
from .base import DocumentRepository, ReviewRepository
from .serialization import (
    conflict_from_dict,
    conflict_to_dict,
    decision_from_dict,
    decision_to_dict,
    fired_rule_from_dict,
    fired_rule_to_dict,
)


def _doc_to_row(doc: Document) -> dict:
    return {
        "id": doc.id,
        "name": doc.name,
        "doc_type": doc.doc_type.value,
        "status": doc.status.value,
        "path": doc.path,
        "content_hash": doc.content_hash,
        "is_locked": int(doc.is_locked),
        "pages": doc.pages,
        "plaintext_path": doc.plaintext_path,
        "extraction_mode": doc.extraction_mode.value if doc.extraction_mode else None,
        "chunk_count": doc.chunk_count,
        "error": doc.error,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


def _row_to_doc(row) -> Document:
    return Document(
        id=row.id,
        name=row.name,
        doc_type=DocType(row.doc_type),
        status=DocStatus(row.status),
        path=row.path,
        content_hash=row.content_hash,
        is_locked=bool(row.is_locked),
        pages=row.pages,
        plaintext_path=row.plaintext_path,
        extraction_mode=ExtractionMode(row.extraction_mode) if row.extraction_mode else None,
        chunk_count=row.chunk_count,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqliteDocumentRepository(DocumentRepository):
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sf = session_factory

    def _upsert(self, doc: Document) -> Document:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        data = _doc_to_row(doc)
        with self._sf() as session:
            stmt = sqlite_insert(DocumentRow).values(**data)
            stmt = stmt.on_conflict_do_update(index_elements=[DocumentRow.id], set_={k: v for k, v in data.items() if k != "id"})
            session.execute(stmt)
            session.commit()
        return doc

    def create(self, doc: Document) -> Document:
        return self._upsert(doc)

    def get(self, doc_id: str) -> Document | None:
        with self._sf() as session:
            row = session.get(DocumentRow, doc_id)
            return _row_to_doc(row) if row else None

    def get_by_path(self, path: str) -> Document | None:
        with self._sf() as session:
            row = session.execute(select(DocumentRow).where(DocumentRow.path == path)).scalar_one_or_none()
            return _row_to_doc(row) if row else None

    def list(self, doc_type: DocType | None = None) -> list[Document]:
        with self._sf() as session:
            stmt = select(DocumentRow).order_by(DocumentRow.updated_at.desc())
            if doc_type:
                stmt = stmt.where(DocumentRow.doc_type == doc_type.value)
            rows = session.execute(stmt).scalars().all()
            return [_row_to_doc(r) for r in rows]

    def update(self, doc: Document) -> Document:
        return self._upsert(doc)

    def delete(self, doc_id: str) -> None:
        with self._sf() as session:
            row = session.get(DocumentRow, doc_id)
            if row:
                session.delete(row)
                session.commit()


def _review_to_row(review: Review) -> dict:
    return {
        "id": review.id,
        "status": review.status.value,
        "frd_name": review.frd_name,
        "nfrd_name": review.nfrd_name,
        "frd_text": review.frd_text or None,
        "nfrd_text": review.nfrd_text or None,
        "facts_json": json.dumps(review.facts) if review.facts else None,
        "sources_json": json.dumps(review.retrieved_sources) if review.retrieved_sources else None,
        "rules_json": json.dumps([fired_rule_to_dict(r) for r in review.rules_fired]) if review.rules_fired else None,
        "rule_test_level": review.rule_test_level.value if review.rule_test_level else None,
        "decision_json": json.dumps(decision_to_dict(review.llm_decision)) if review.llm_decision else None,
        "final_json": json.dumps(decision_to_dict(review.final_decision)) if review.final_decision else None,
        "conflicts_json": json.dumps([conflict_to_dict(c) for c in review.conflicts]) if review.conflicts else None,
        "error": review.error,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def _row_to_review(row) -> Review:
    def _load(raw: str | None):
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    return Review(
        id=row.id,
        status=ReviewStatus(row.status),
        frd_name=row.frd_name,
        nfrd_name=row.nfrd_name,
        frd_text=row.frd_text or "",
        nfrd_text=row.nfrd_text or "",
        facts=_load(row.facts_json),
        retrieved_sources=list(_load(row.sources_json) or []),
        rules_fired=[fired_rule_from_dict(d) for d in (_load(row.rules_json) or [])],
        rule_test_level=TestLevel(row.rule_test_level) if row.rule_test_level else None,
        llm_decision=decision_from_dict(_load(row.decision_json)),
        final_decision=decision_from_dict(_load(row.final_json)),
        conflicts=[conflict_from_dict(d) for d in (_load(row.conflicts_json) or [])],
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqliteReviewRepository(ReviewRepository):
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sf = session_factory

    def _upsert(self, review: Review) -> Review:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        data = _review_to_row(review)
        with self._sf() as session:
            stmt = sqlite_insert(ReviewRow).values(**data)
            stmt = stmt.on_conflict_do_update(index_elements=[ReviewRow.id], set_={k: v for k, v in data.items() if k != "id"})
            session.execute(stmt)
            session.commit()
        return review

    def create(self, review: Review) -> Review:
        return self._upsert(review)

    def get(self, review_id: str) -> Review | None:
        with self._sf() as session:
            row = session.get(ReviewRow, review_id)
            return _row_to_review(row) if row else None

    def update(self, review: Review) -> Review:
        return self._upsert(review)

    def list(self) -> list[Review]:
        with self._sf() as session:
            rows = session.execute(select(ReviewRow).order_by(ReviewRow.created_at.desc())).scalars().all()
            return [_row_to_review(r) for r in rows]
