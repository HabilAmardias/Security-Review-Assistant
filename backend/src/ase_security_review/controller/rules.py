"""Compliance-rule CRUD routes (managed via the Rules page)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from ..usecase.rules import RuleExistsError, RuleNotFoundError
from .deps import get_container

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
def list_rules(request: Request):
    return get_container(request).rules_service.list()


@router.get("/defaults")
def rule_defaults(request: Request):
    return get_container(request).rules_service.defaults()


@router.post("", status_code=201)
def create_rule(body: dict, request: Request):
    c = get_container(request)
    try:
        return c.rules_service.create(body)
    except RuleExistsError as exc:
        raise HTTPException(409, f"Rule '{exc}' already exists") from exc
    except ValidationError as exc:
        raise HTTPException(400, f"Invalid rule: {exc}") from exc


@router.post("/reset")
def reset_rules(request: Request):
    return get_container(request).rules_service.reset()


@router.get("/{rule_id}")
def get_rule(rule_id: str, request: Request):
    rule = get_container(request).rules_service.get(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    return rule


@router.put("/{rule_id}")
def update_rule(rule_id: str, body: dict, request: Request):
    c = get_container(request)
    try:
        return c.rules_service.update(rule_id, body)
    except RuleNotFoundError as exc:
        raise HTTPException(404, "Rule not found") from exc
    except ValidationError as exc:
        raise HTTPException(400, f"Invalid rule: {exc}") from exc


@router.patch("/{rule_id}")
def patch_rule(rule_id: str, body: dict, request: Request):
    c = get_container(request)
    try:
        return c.rules_service.patch(rule_id, body)
    except RuleNotFoundError as exc:
        raise HTTPException(404, "Rule not found") from exc
    except ValidationError as exc:
        raise HTTPException(400, f"Invalid rule: {exc}") from exc


@router.delete("/{rule_id}")
def delete_rule(rule_id: str, request: Request):
    c = get_container(request)
    try:
        c.rules_service.delete(rule_id)
    except RuleNotFoundError as exc:
        raise HTTPException(404, "Rule not found") from exc
    return {"deleted": rule_id}
