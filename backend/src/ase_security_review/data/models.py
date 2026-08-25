"""SQLAlchemy ORM models for the SQLite metadata/audit database."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    path: Mapped[str] = mapped_column(String(1024), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    is_locked: Mapped[bool] = mapped_column(Integer, default=False)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plaintext_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extraction_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewRow(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    frd_name: Mapped[str] = mapped_column(String(512))
    nfrd_name: Mapped[str] = mapped_column(String(512))
    frd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    nfrd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    facts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_engine_enabled: Mapped[bool] = mapped_column(Integer, default=True)
    detected_exposure: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exposure_override: Mapped[str | None] = mapped_column(String(32), nullable=True)
    form_fields_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_test_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
