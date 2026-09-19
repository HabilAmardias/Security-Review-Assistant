"""Business-logic settings routes (editable at runtime via the UI)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .deps import get_container, run_backend

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _payload(body: dict) -> dict:
    return {k: v for k, v in body.items() if k in ("llm", "extraction", "retrieval")}


@router.get("")
def get_settings(request: Request):
    c = get_container(request)
    return {
        "settings": c.settings_service.current(),
        "defaults": c.settings_service.defaults(),
        "models": c.llm.list_models(),
        "reasoning_model": c.config.llm.reasoning_model,
        "embedding_model": c.config.llm.embedding_model,
        "embedding_dim": c.config.llm.embedding_dim,
    }


@router.put("")
def update_settings(body: dict, request: Request):
    c = get_container(request)
    try:
        result = c.settings_service.update(_payload(body))
    except Exception as exc:
        raise HTTPException(400, f"Invalid settings: {exc}") from exc
    if result.get("reindex_required"):
        run_backend(c.ingestion.reindex_all)
    return result


@router.post("/reset")
def reset_settings(request: Request):
    c = get_container(request)
    result = c.settings_service.reset()
    if result.get("reindex_required"):
        run_backend(c.ingestion.reindex_all)
    return result
