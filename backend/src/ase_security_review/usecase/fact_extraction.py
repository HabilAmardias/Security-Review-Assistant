"""Fact extraction: LLM reads the FRD + NFRD and returns a structured JSON profile
used for retrieval queries and rule evaluation."""

from __future__ import annotations

from pydantic import ValidationError

from ..config.settings import AppConfig
from ..repository.base import LlmPort
from .llm_schemas import FactsModel, parse_json_object

_FACT_SYSTEM = """You are a security requirements analyst. You read a Functional Requirements Document (FRD) and a Non-Functional Requirements Document (NFRD) for a software application and extract a structured security-relevant profile.

Respond ONLY with valid JSON matching this exact schema:
{
  "app_name": string,
  "app_type": "web" | "mobile" | "api" | "desktop" | "internal" | "other",
  "exposure": "internet-facing" | "internal" | "partner" | "unclear",
  "exposure_evidence": string,        // the exact sentence/field that states the exposure; "" if not stated
  "change_scope": "full_new_app" | "feature_change" | "limited_change" | "other",
  "change_scope_evidence": string,    // quote the FRD sentence describing the scope of this change; "" if none
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

Rules:
- For "exposure", base it ONLY on an explicit statement in the documents (e.g. "the app is on the intranet", "internet-facing", "only accessible from the corporate network"). Quote it in "exposure_evidence".
- If the documents only LIST exposure options (e.g. a form that shows "Internet / External / Intranet / Lainnya") without making the selected value clear in text, set "exposure" to "unclear" and "exposure_evidence" to the option list. NEVER guess which option was selected.
- For "change_scope", decide whether the FRD describes building a brand-new application ("full_new_app"), adding a feature/change to an existing application ("feature_change"), or only a limited change that does NOT affect business logic or sensitive data processing ("limited_change"). A change is "limited_change" only if the FRD explicitly states that business logic / business process / sensitive data processing is unaffected (e.g. front-end-only or infrastructure/configuration-only changes such as load balancing, routing, TLS, or UI presentation). Do NOT classify as "limited_change" if the change touches business logic, authentication/authorization, API contracts, input validation, encryption, or sensitive-data storage/transmission. Quote the exact FRD sentence in "change_scope_evidence". If the scope is ambiguous or the FRD does not clearly state that logic/data processing is unaffected, use "other".
- The documents may be in English, Indonesian, or mixed. Analyze them regardless of language. Omit no fields; use empty arrays or empty strings where unknown.
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

    def extract(
        self,
        frd_text: str,
        nfrd_text: str,
        form_fields: list | None = None,
    ) -> FactsModel:
        budget = self._config.review_max_input_chars // 2
        prompt = (
            "=== FUNCTIONAL REQUIREMENTS DOCUMENT (FRD) ===\n"
            f"{self._truncate(frd_text, budget)}\n\n"
            "=== NON-FUNCTIONAL REQUIREMENTS DOCUMENT (NFRD) ===\n"
            f"{self._truncate(nfrd_text, budget)}"
        )
        if form_fields:
            block = "\n".join(
                f"- {f.label or '(field)'}: selected = {', '.join(f.selected) or '(none)'}"
                for f in form_fields
            )
            prompt = (
                "=== SELECTED FORM FIELDS DETECTED FROM THE PDF (authoritative) ===\n"
                f"{block}\n\n{prompt}"
            )
        last_error: Exception | None = None
        for attempt in range(3):
            use_format = "json" if attempt < 2 else None
            raw = self._llm.generate(
                prompt if attempt == 0 else "Respond ONLY with valid JSON matching the schema.\n\n" + prompt,
                system=_FACT_SYSTEM,
                format=use_format,
                step="fact_extraction",
            )
            try:
                return FactsModel.model_validate(parse_json_object(raw))
            except (ValueError, ValidationError) as exc:
                last_error = exc
        raise ValueError(f"Fact extraction produced invalid JSON: {last_error}") from last_error
