"""Fact extraction: LLM reads the FRD + NFRD and returns a structured JSON profile
used for retrieval queries and rule evaluation."""

from __future__ import annotations

import json

from pydantic import ValidationError

from ..config.settings import AppConfig
from ..repository.base import LlmPort
from .llm_schemas import FactsModel

_FACT_SYSTEM = """You are a security requirements analyst. You read a Functional Requirements Document (FRD) and a Non-Functional Requirements Document (NFRD) for a software application and extract a structured security-relevant profile.

Respond ONLY with valid JSON matching this exact schema:
{
  "app_name": string,
  "app_type": "web" | "mobile" | "api" | "desktop" | "internal" | "other",
  "exposure": "internet-facing" | "internal" | "partner",
  "technologies": [string],          // frameworks, languages, DBs mentioned
  "data_classes": [string],          // subset of: payment, pii, phi, financial, credentials, none
  "features": [string],              // semantic tags, subset of: authentication, authorization, sso, mfa, integration, webhook, internet-facing, internal, compliance, admin, audit, file-upload
  "auth_model": string,              // e.g. session, oauth2, sso, basic, none
  "roles": [string],                 // user roles mentioned
  "key_features": [string],          // important functional features (up to 12)
  "integrations": [string],          // third-party / external integrations
  "compliance_refs": [string],       // compliance or regulation references mentioned
  "nfr_highlights": [string],        // important non-functional requirements (security, performance, availability, up to 8)
  "summary": string                  // 2-4 sentence security-relevant summary
}

The documents may be in English, Indonesian, or mixed. Analyze them regardless of language. Omit no fields; use empty arrays or empty strings where unknown.
"""


class FactExtractionService:
    def __init__(self, config: AppConfig, llm: LlmPort):
        self._config = config
        self._llm = llm

    @staticmethod
    def _truncate(text: str, budget: int) -> str:
        text = text or ""
        if len(text) <= budget:
            return text
        half = budget // 2
        return text[:half] + "\n...[truncated]...\n" + text[-half:]

    def extract(self, frd_text: str, nfrd_text: str) -> FactsModel:
        budget = self._config.review_max_input_chars // 2
        prompt = (
            "=== FUNCTIONAL REQUIREMENTS DOCUMENT (FRD) ===\n"
            f"{self._truncate(frd_text, budget)}\n\n"
            "=== NON-FUNCTIONAL REQUIREMENTS DOCUMENT (NFRD) ===\n"
            f"{self._truncate(nfrd_text, budget)}"
        )
        raw = self._llm.generate(prompt, system=_FACT_SYSTEM, format="json")
        last_error: Exception | None = None
        for _ in range(2):
            try:
                return FactsModel.model_validate(json.loads(raw))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                raw = self._llm.generate(
                    "Your previous response was not valid. Respond ONLY with valid JSON "
                    "matching the schema.\n\n" + prompt,
                    system=_FACT_SYSTEM,
                    format="json",
                )
        raise ValueError(f"Fact extraction produced invalid JSON: {last_error}") from last_error
