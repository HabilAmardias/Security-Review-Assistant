"""Review use case: orchestrate fact extraction -> retrieval -> rules -> LLM
decision -> conflict check, and persist everything to the audit log."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from ..config.settings import AppConfig
from ..domain.enums import ReviewStatus, TestLevel, parse_test_level
from ..domain.models import Conflict, FiredRule, FormField, Review, SecurityDecision, Scope
from ..domain.rules import aggregate_test_level, apply_cap, evaluate_facts, pentest_required
from ..repository.base import LlmPort, ReviewRepository
from .fact_extraction import FactExtractionService
from .llm_schemas import DecisionModel, parse_json_object
from .retrieval import RetrievalService

_DECISION_SYSTEM = """You are a senior application security reviewer. Based on:
(a) structured facts about the application,
(b) deterministic rules that fired from the org's review SOP,
(c) relevant excerpts retrieved from the org's SOP, policies, and previous security reviews,
decide whether the application needs a full penetration test or only automated DAST.

Guidance:
- Payment, health (PHI), financial, or credential data, or significant auth/authz logic -> pentest.
- Internal tool with no sensitive data -> DAST is usually sufficient.
- A deterministic rule cap is a hard policy bound: never recommend a test level stronger than the cap (e.g. intranet apps are capped at DAST).
- If the FRD states the change does not affect business logic or data processing (change_scope = infra_config_change), that strongly favors DAST even when the surrounding application handles sensitive data.
- Retrieved SOP/policy/precedent text is authoritative context; prefer it over general advice.
- The deterministic rules are baseline mandates; only deviate from them with strong, documented justification.
- Consider the retrieved sources as precedent: what did similar past reviews require?

Respond ONLY with valid JSON matching this exact schema:
{
  "requires_pentest": boolean,
  "test_level": "pentest" | "dast" | "none",
  "classification_reason": string,     // 2-5 sentences; cite specific data classes, fired rules, and retrieved sources
  "risk_factors": [string],
  "scope": {
    "in_scope": [string],              // modules, components, APIs to test
    "out_of_scope": [string],
    "test_methods": [string],          // e.g. ASVS L2, API scanning, authz testing, code review
    "environments": [string],          // e.g. staging pre-release
    "effort_estimate": string          // e.g. 3-5 person-days
  }
}
"""


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

    def create_review(
        self,
        frd_name: str,
        frd_text: str,
        nfrd_name: str,
        nfrd_text: str,
        *,
        detected_exposure: str | None = None,
        exposure_override: str | None = None,
        form_fields: list[FormField] | None = None,
    ) -> Review:
        review = Review(
            id=uuid.uuid4().hex,
            status=ReviewStatus.RUNNING,
            frd_name=frd_name,
            nfrd_name=nfrd_name,
            frd_text=frd_text,
            nfrd_text=nfrd_text,
            detected_exposure=detected_exposure,
            exposure_override=exposure_override,
            form_fields=form_fields or [],
        )
        return self._reviews.create(review)

    def run_review(self, review_id: str) -> Review:
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"Review {review_id} not found")
        try:
            # 1) fact extraction (form selections from the PDF are authoritative evidence)
            facts = self._facts.extract(review.frd_text, review.nfrd_text, form_fields=review.form_fields)
            review.facts = self._ground_data_classes(self._apply_exposure(facts.model_dump(), review), review.form_fields)
            self._save(review)

            # 2) retrieval
            queries = self._build_queries(review.facts, review)
            hits = self._retrieval.query(queries)
            review.retrieved_sources = self._sources(hits)
            self._save(review)

            # 3) rule engine (optional)
            review.rule_engine_enabled = self._config.enable_rule_engine
            if self._config.enable_rule_engine:
                fired = evaluate_facts(review.facts, self._config.compliance.rules)
            else:
                fired = []
            review.rules_fired = fired
            review.rule_test_level = aggregate_test_level(fired)
            self._save(review)

            # 4) LLM decision
            review.llm_decision = self._llm_decision(review.facts, fired, hits)
            self._save(review)

            # 5) conflict check + final (cap is enforced on the final verdict)
            review.conflicts = self._conflicts(review)
            review.final_decision = review.llm_decision
            if self._config.enable_rule_engine and review.final_decision:
                review.final_decision = apply_cap(review.final_decision, review.rules_fired)
            review.status = ReviewStatus.COMPLETED
            return self._save(review)
        except Exception as exc:
            review.status = ReviewStatus.FAILED
            review.error = str(exc)
            return self._save(review)

    @staticmethod
    def _apply_exposure(facts: dict, review: Review) -> dict:
        """Resolve the effective exposure: human override > PDF form field > LLM."""
        original = facts.get("exposure") or "unclear"
        facts["exposure_llm"] = original
        if review.exposure_override:
            facts["exposure"] = review.exposure_override
        elif review.detected_exposure:
            facts["exposure"] = review.detected_exposure
        else:
            facts["exposure"] = original
        return facts

    @staticmethod
    def _ground_data_classes(facts: dict, form_fields: list[FormField]) -> dict:
        """Ground data_classes in the application-characteristics form selection so
        the value is deterministic; keep the LLM's original for audit."""
        for field in form_fields:
            hay = (field.label + " " + " ".join(field.options)).lower()
            if "karakteristik" not in hay and "characteristic" not in hay:
                continue
            mapped = []
            for sel in field.selected:
                s = sel.lower()
                if "financial" in s:
                    mapped.append("financial")
                elif "pii" in s or "personally identifiable" in s:
                    mapped.append("pii")
                elif "payment" in s or "cardholder" in s:
                    mapped.append("payment")
            if mapped:
                facts["data_classes_llm"] = facts.get("data_classes") or []
                facts["data_classes"] = sorted(set(mapped))
            break
        return facts

    def update_exposure(self, review_id: str, exposure: str | None) -> Review:
        """Set the human-confirmed exposure and recompute rules/conflicts/final
        from the stored facts + LLM decision (no LLM re-run)."""
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"Review {review_id} not found")
        review.exposure_override = exposure or None
        if review.facts:
            review.facts = self._apply_exposure(dict(review.facts), review)
        review.rule_engine_enabled = self._config.enable_rule_engine
        if self._config.enable_rule_engine:
            review.rules_fired = evaluate_facts(review.facts or {}, self._config.compliance.rules)
        else:
            review.rules_fired = []
        review.rule_test_level = aggregate_test_level(review.rules_fired)
        review.conflicts = self._conflicts(review)
        review.final_decision = review.llm_decision
        if self._config.enable_rule_engine and review.final_decision:
            review.final_decision = apply_cap(review.final_decision, review.rules_fired)
        return self._save(review)

    def set_final_decision(self, review_id: str, decision: SecurityDecision) -> Review:
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"Review {review_id} not found")
        review.final_decision = decision
        return self._save(review)

    # ---- internals --------------------------------------------------------

    def _save(self, review: Review) -> Review:
        review.updated_at = datetime.now(timezone.utc)
        return self._reviews.update(review)

    @staticmethod
    def _build_queries(facts: dict, review: Review) -> list[str]:
        queries = [
            facts.get("summary", ""),
            " ".join(facts.get("key_features") or []),
            " ".join(facts.get("nfr_highlights") or []),
            " ".join(facts.get("data_classes") or []) + " " + facts.get("app_type", ""),
        ]
        for key in ("integrations", "compliance_refs"):
            queries.append(" ".join(facts.get(key) or []))
        queries.append(review.frd_text[:1500])
        queries.append(review.nfrd_text[:1500])
        return queries

    @staticmethod
    def _sources(hits) -> list[str]:
        seen: list[str] = []
        for hit in hits:
            label = hit.doc_name
            if label and label not in seen:
                seen.append(label)
        return seen

    def _llm_decision(self, facts: dict, fired: list[FiredRule], hits) -> SecurityDecision:
        if self._config.enable_rule_engine:
            lines = []
            for r in fired:
                line = f"- [{r.id}] {r.name} -> requires {r.test_level.value} (priority {r.priority})"
                if r.cap is not None:
                    line += f" [CAPS overall requirement at {r.cap.value}]"
                lines.append(line + f". {r.reasoning}")
            rules_block = "\n".join(lines) or "- none fired"
        else:
            rules_block = "- deterministic rule engine is DISABLED; decide based on facts and retrieved context only"
        context_block = "\n\n".join(
            f"--- Source: {hit.doc_name} [{hit.doc_type.value}] ---\n{hit.chunk.text[:1800]}"
            for hit in hits[:6]
        ) or "- no relevant knowledge base content retrieved"

        prompt = (
            "=== APP FACTS (JSON) ===\n"
            f"{json.dumps(facts, ensure_ascii=False)}\n\n"
            "=== DETERMINISTIC RULES FIRED (baseline mandates) ===\n"
            f"{rules_block}\n\n"
            "=== RETRIEVED KNOWLEDGE BASE CONTEXT (SOP / policies / previous reviews) ===\n"
            f"{context_block}\n\n"
            "Decide whether this application requires a full penetration test or only DAST. "
            "Return only the JSON object."
        )
        system = _DECISION_SYSTEM

        last_error: Exception | None = None
        for attempt in range(3):
            use_format = "json" if attempt < 2 else None
            raw = self._llm.generate(
                prompt if attempt == 0 else "Return ONLY the JSON object matching the schema.\n\n" + prompt,
                system=system,
                format=use_format,
            )
            try:
                model = DecisionModel.model_validate(parse_json_object(raw))
                return self._to_domain(model)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise ValueError(f"Decision LLM produced invalid output: {last_error}") from last_error

    def _conflicts(self, review: Review) -> list[Conflict]:
        llm = review.llm_decision
        if llm is None:
            return []
        conflicts: list[Conflict] = []
        rule_level = review.rule_test_level
        if rule_level is not None:
            if llm.requires_pentest != pentest_required(rule_level):
                conflicts.append(
                    Conflict(
                        field="requires_pentest",
                        rules_value=pentest_required(rule_level),
                        llm_value=llm.requires_pentest,
                        explanation=(
                            "Rule engine and LLM disagree on whether pentest is required. "
                            "Confirm with the human reviewer."
                        ),
                    )
                )
            if rule_level == TestLevel.PENTEST and llm.test_level != TestLevel.PENTEST:
                conflicts.append(
                    Conflict(
                        field="test_level",
                        rules_value=rule_level.value,
                        llm_value=llm.test_level.value,
                        explanation="LLM chose a lighter test level than the rule engine mandates.",
                    )
                )
        return conflicts

    @staticmethod
    def _to_domain(model: DecisionModel) -> SecurityDecision:
        return SecurityDecision(
            requires_pentest=model.requires_pentest,
            test_level=parse_test_level(model.test_level),
            classification_reason=model.classification_reason,
            risk_factors=list(model.risk_factors),
            scope=Scope(
                in_scope=list(model.scope.in_scope),
                out_of_scope=list(model.scope.out_of_scope),
                test_methods=list(model.scope.test_methods),
                environments=list(model.scope.environments),
                effort_estimate=model.scope.effort_estimate,
            ),
        )
