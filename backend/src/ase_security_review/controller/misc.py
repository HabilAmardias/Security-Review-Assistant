"""Health, models, and compliance framework routes."""

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


@router.get("/frameworks")
def frameworks(request: Request):
    c = get_container(request)
    enabled = c.config.compliance.enabled
    return [
        {
            "key": key,
            "name": fw.name,
            "description": fw.description,
            "test_level": fw.test_level,
        }
        for key, fw in c.config.compliance.frameworks.items()
        if key in enabled
    ]
