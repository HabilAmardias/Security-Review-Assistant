"""Review use case: orchestrate fact extraction -> retrieval -> rules -> LLM
decision -> conflict check, and persist everything to the audit log."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from ..config.settings import AppConfig
from ..domain.enums import ReviewStatus, TestLevel
from ..domain.models import Conflict, FiredRule, Review, SecurityDecision, Scope
from ..domain.rules import aggregate_test_level, evaluate_facts, pentest_required
from ..repository.base import LlmPort, ReviewRepository
from .fact_extraction import FactExtractionService
from .llm_schemas import DecisionModel
from .retrieval import RetrievalService

_DECISION_SYSTEM = """You are a senior application security reviewer. Based on:
(a) structured facts about the application,
(b) deterministic rules that fired from the org's review SOP,
(c) relevant excerpts retrieved from the org's SOP, policies, and previous security reviews,
decide whether the application needs a full penetration test or only automated DAST.

Guidance:
- Payment, health (PHI), financial, or credential data, or significant auth/authz logic -> pentest.
- Internal tool with no sensitive data -> DAST is usually sufficient.
- Retrieved SOP/policy/precedent text is authoritative context; prefer it over general advice.
- The deterministic rules are baseline mandates; only deviate from them with strong, documented justification.
- Enabled compliance frameworks to cite: {frameworks}
- Consider the retrieved sources as precedent: what did similar past reviews require?

Respond ONLY with valid JSON matching this exact schema:
{{
  "requires_pentest": boolean,
  "test_level": "pentest" | "dast" | "both" | "none",
  "classification_reason": string,     // 2-5 sentences; cite specific data classes, fired rules, and retrieved sources
  "risk_factors": [string],
  "scope": {{
    "in_scope": [string],              // modules, components, APIs to test
    "out_of_scope": [string],
    "test_methods": [string],          // e.g. OWASP ASVS L2, API scanning, authz testing, code review
    "environments": [string],          // e.g. staging pre-release
    "effort_estimate": string          // e.g. 3-5 person-days
  }},
  "recommended_frameworks": [string]
}}
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

    def create_review(self, frd_name: str, frd_text: str, nfrd_name: str, nfrd_text: str) -> Review:
        review = Review(
            id=uuid.uuid4().hex,
            status=ReviewStatus.RUNNING,
            frd_name=frd_name,
            nfrd_name=nfrd_name,
            frd_text=frd_text,
            nfrd_text=nfrd_text,
        )
        return self._reviews.create(review)

    def run_review(self, review_id: str) -> Review:
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"Review {review_id} not found")
        try:
            # 1) fact extraction
            facts = self._facts.extract(review.frd_text, review.nfrd_text)
            review.facts = facts.model_dump()
            self._save(review)

            # 2) retrieval
            queries = self._build_queries(facts.model_dump(), review)
            hits = self._retrieval.query(queries)
            review.retrieved_sources = self._sources(hits)
            self._save(review)

            # 3) rule engine
            fired = evaluate_facts(review.facts, self._config.compliance.rules)
            review.rules_fired = fired
            review.rule_test_level = aggregate_test_level(fired)
            self._save(review)

            # 4) LLM decision
            review.llm_decision = self._llm_decision(facts.model_dump(), fired, hits)
            self._save(review)

            # 5) conflict check + final
            review.conflicts = self._conflicts(review)
            review.final_decision = review.llm_decision
            review.status = ReviewStatus.COMPLETED
            return self._save(review)
        except Exception as exc:
            review.status = ReviewStatus.FAILED
            review.error = str(exc)
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
        frameworks = self._framework_list()
        rules_block = "\n".join(
            f"- [{r.id}] {r.name} -> requires {r.test_level.value} (priority {r.priority}). "
            f"{r.reasoning}" for r in fired
        ) or "- none fired"
        context_block = "\n\n".join(
            f"--- Source: {hit.doc_name} [{hit.doc_type.value}] ---\n{hit.chunk.text[:2500]}"
            for hit in hits[:8]
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

        raw = self._llm.generate(prompt, system=_DECISION_SYSTEM.format(frameworks=frameworks), format="json")
        last_error: Exception | None = None
        for _ in range(2):
            try:
                model = DecisionModel.model_validate(json.loads(raw))
                return self._to_domain(model)
            except (json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
                last_error = exc
                raw = self._llm.generate(
                    "Your previous response was invalid. Return ONLY the JSON object.\n\n" + prompt,
                    system=_DECISION_SYSTEM.format(frameworks=frameworks),
                    format="json",
                )
        raise ValueError(f"Decision LLM produced invalid output: {last_error}") from last_error

    def _framework_list(self) -> str:
        enabled = self._config.compliance.enabled
        frameworks = self._config.compliance.frameworks
        return "; ".join(
            f"{k}: {frameworks[k].name} ({frameworks[k].description})"
            for k in enabled if k in frameworks
        ) or "(none enabled)"

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
            if rule_level in (TestLevel.PENTEST, TestLevel.BOTH) and llm.test_level not in (
                TestLevel.PENTEST,
                TestLevel.BOTH,
            ):
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
            test_level=TestLevel(model.test_level),
            classification_reason=model.classification_reason,
            risk_factors=list(model.risk_factors),
            scope=Scope(
                in_scope=list(model.scope.in_scope),
                out_of_scope=list(model.scope.out_of_scope),
                test_methods=list(model.scope.test_methods),
                environments=list(model.scope.environments),
                effort_estimate=model.scope.effort_estimate,
            ),
            recommended_frameworks=list(model.recommended_frameworks),
        )
