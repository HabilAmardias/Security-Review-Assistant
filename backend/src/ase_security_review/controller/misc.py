"""Health and models routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from .deps import get_container

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health")
def health(request: Request):
    c = get_container(request)
    return {
        "status": "ok",
        "ollama": c.llm.ping(),
        "models": c.llm.list_models(),
        "reasoning_model": c.config.llm.reasoning_model,
        "embedding_model": c.config.llm.embedding_model,
        "enable_rule_engine": c.config.enable_rule_engine,
        "documents_indexed": c.vectors.count(),
    }


@router.get("/models")
def models(request: Request):
    c = get_container(request)
    available = c.llm.list_models()
    return {
        "available": available,
        "reasoning_model": c.config.llm.reasoning_model,
        "embedding_model": c.config.llm.embedding_model,
    }
