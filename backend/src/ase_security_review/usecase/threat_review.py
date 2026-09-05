"""Threat-model review pipeline: read diagrams -> understand requirement ->
architecture & trust boundaries -> identify assets -> STRIDE threat modelling ->
determine the security test. STRIDE findings drive the final decision (no
deterministic cap); stage artifacts are stored read-only for audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from ..config.settings import AppConfig
from ..domain.enums import ReviewStatus, TestLevel
from ..domain.models import Review, Scope, SecurityDecision
from ..domain.rules import aggregate_test_level, apply_cap, evaluate_facts, rule_conflicts
from ..repository.base import LlmPort, ReviewRepository
from .fact_extraction import FactExtractionService
from .fact_grounding import ground_facts
from .llm_schemas import (
    ArchitectureModel,
    AssetsModel,
    DecisionModel,
    DiagramsModel,
    RequirementModel,
    ThreatModel,
    parse_json_object,
)
from .retrieval import RetrievalService

_STAGE_LABELS = ("diagrams", "requirement", "architecture", "assets", "threats", "decision")

_TRUNC = 14000


def _truncate(text: str, budget: int = _TRUNC) -> str:
    text = text or ""
    if len(text) <= budget:
        return text
    half = budget // 2
    return text[:half] + "\n...[truncated]...\n" + text[-half:]


def _fmt(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


_SYSTEM = {
    "diagrams": (
        "You analyze architecture / use-case diagrams rendered from a requirements PDF. "
        "Identify the CHANGE described in the FRD and locate where it sits in the diagram "
        "(its actors, use cases, flows, and any external systems it touches). Treat the rest "
        "of the diagram as background only. "
        "Respond ONLY with valid JSON: {\"diagrams\":[{\"label\":string,\"actors\":[string],"
        "\"use_cases\":[string],\"flows\":[string],\"external_systems\":[string],\"notes\":string}],"
        "\"summary\":string}. Describe actors, use cases, data flows, and any external systems."
    ),
    "requirement": (
        "You are a security requirements analyst. The review subject is the CHANGE described in the "
        "FRD, NOT the whole application. From the FRD (and any diagrams) describe ONLY what this "
        "change introduces or modifies. Everything else in the documents is background context. "
        "Respond ONLY with valid JSON: "
        "{\"summary\":string,\"data_submitted\":[string],\"actors\":[string],\"destinations\":[string],"
        "\"approvers\":[string],\"triggers\":[string],\"affected_features\":[string]}. "
        "Be explicit about what information the change submits, who submits it, where it goes, and who can approve."
    ),
    "architecture": (
        "You are a security architect. The review subject is the CHANGE described in the FRD, NOT the "
        "whole application. Map ONLY the components, data flows, entry points, and integrations that "
        "the change introduces or modifies, and the specific TRUST BOUNDARY the change crosses. Do NOT "
        "enumerate the whole application stack. Respond ONLY with valid JSON: "
        "{\"summary\":string,\"components\":[{\"name\":string,\"role\":string,\"sensitive\":bool}],"
        "\"data_flows\":[{\"source\":string,\"destination\":string,\"data\":string,\"protocol\":string}],"
        "\"trust_boundaries\":[{\"between\":string,\"reason\":string}],\"entry_points\":[string],"
        "\"integrations\":[string]}"
    ),
    "assets": (
        "You are a security reviewer identifying the ASSETS to protect. The review subject is the CHANGE "
        "described in the FRD, NOT the whole application. List only the assets the change introduces or "
        "affects (e.g. data or configuration it touches); treat other application assets as background "
        "exposure context only. Use the retrieved knowledge-base context (SOP/policies/previous reviews) "
        "as the basis for sensitivity and protection. Respond ONLY with valid JSON: "
        "{\"assets\":[{\"name\":string,\"asset_type\":string,\"sensitivity\":string,\"location\":string,"
        "\"protection_basis\":string,\"kb_sources\":[string]}]}"
    ),
    "threats": (
        "Perform STRIDE threat modelling against the components, data flows, assets, and trust boundaries "
        "that the CHANGE introduces or modifies. Only model threats to the change's touchpoints and the "
        "trust boundaries it crosses; do not threat-model the whole application. List concrete, realistic "
        "threats. Respond ONLY with valid JSON: "
        "{\"threats\":[{\"id\":string,\"element\":string,\"stride_category\":string,"
        "\"scenario\":string,\"likelihood\":\"low\"|\"medium\"|\"high\","
        "\"impact\":\"low\"|\"medium\"|\"high\",\"severity\":\"low\"|\"medium\"|\"high\"|\"critical\"}]}"
    ),
    "decision": (
        "You are a senior application security reviewer. Decide the security testing this CHANGE "
        "requires. The review subject is the CHANGE described in the FRD, NOT the whole application. "
        "Base the decision on the change-scoped requirement, architecture & trust boundaries, assets, "
        "and STRIDE threats. Application flows NOT touched by the change are out of scope. Scope "
        "in_scope to the components the change introduces or modifies; put unchanged application "
        "modules and flows (including sensitive flows untouched by the change) in out_of_scope. "
        "Respond ONLY with valid JSON: "
        "{\"requires_pentest\":bool,\"test_level\":\"none\"|\"dast\"|\"pentest\","
        "\"classification_reason\":string,\"risk_factors\":[string],\"scope\":{\"in_scope\":[string],"
        "\"out_of_scope\":[string],\"test_methods\":[string],\"environments\":[string],"
        "\"effort_estimate\":string}}"
    ),
}


class ThreatReviewPipeline:
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

    # ---- entry ------------------------------------------------------------

    def run(self, review_id: str) -> Review:
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"Review {review_id} not found")
        review.status = ReviewStatus.RUNNING
        review.pipeline = "threat"
        review.current_stage = _STAGE_LABELS[0]
        self._seen_sources: list[str] = []
        self._save(review)
        try:
            facts = self._facts.extract(review.frd_text, review.nfrd_text, form_fields=review.form_fields)
            review.facts = ground_facts(facts.model_dump(), review, review.form_fields)

            # deterministic rules are HARD bounds on the final decision
            review.rule_engine_enabled = self._config.enable_rule_engine
            if self._config.enable_rule_engine:
                review.rules_fired = evaluate_facts(review.facts, self._config.compliance.rules)
            else:
                review.rules_fired = []
            review.rule_test_level = aggregate_test_level(review.rules_fired)
            self._save(review)

            analysis = dict(review.analysis or {})

            diagrams = self._stage_diagrams(review)
            analysis["diagrams"] = diagrams
            self._set_stage(review, analysis, _STAGE_LABELS[1])

            requirement = self._stage_requirement(review, analysis)
            analysis["requirement"] = requirement
            self._set_stage(review, analysis, _STAGE_LABELS[2])

            architecture = self._stage_architecture(review, analysis)
            analysis["architecture"] = architecture
            self._set_stage(review, analysis, _STAGE_LABELS[3])

            assets = self._stage_assets(review, analysis)
            analysis["assets"] = assets
            self._set_stage(review, analysis, _STAGE_LABELS[4])

            threats = self._stage_threats(review, analysis)
            analysis["threats"] = threats
            self._set_stage(review, analysis, _STAGE_LABELS[5])

            decision_model = self._stage_decision(review, analysis)
            review.analysis = analysis
            review.retrieved_sources = list(dict.fromkeys(getattr(self, "_seen_sources", [])))
            review.llm_decision = self._to_domain(decision_model)
            review.conflicts = rule_conflicts(review.rule_test_level, review.rules_fired, review.llm_decision)
            review.final_decision = self._apply_bounds(review.llm_decision, review)
            review.status = ReviewStatus.COMPLETED
            review.current_stage = "done"
            return self._save(review)
        except Exception as exc:
            review.status = ReviewStatus.FAILED
            review.error = str(exc)
            return self._save(review)

    def _apply_bounds(self, decision: SecurityDecision, review: Review) -> SecurityDecision:
        """Rules are hard bounds: apply any cap, then the DAST floor."""
        if not self._config.enable_rule_engine:
            return decision
        bounded = apply_cap(decision, review.rules_fired)
        if review.rule_test_level == TestLevel.DAST and bounded.test_level == TestLevel.NONE:
            reason = (bounded.classification_reason or "").strip()
            note = " [NOTE: the rule engine requires at least DAST; final decision raised from none.]"
            bounded = SecurityDecision(
                requires_pentest=False,
                test_level=TestLevel.DAST,
                classification_reason=(reason + note).strip(),
                risk_factors=list(bounded.risk_factors),
                scope=bounded.scope,
            )
        return bounded

    # ---- stages -----------------------------------------------------------

    def _stage_diagrams(self, review: Review) -> dict:
        paths = [Path(p) for p in review.diagram_paths if Path(p).exists()]
        if not paths:
            return {"diagrams": [], "summary": "", "note": "no diagram images found"}
        images = [p.read_bytes() for p in paths]
        try:
            change_scope = (review.facts or {}).get("change_scope") or "unknown"
            user = (
                "PDF pages containing diagrams for an application. "
                f"The review subject is the CHANGE described in the FRD (change scope: {change_scope}). "
                f"Locate where the change sits in the diagram for: {review.frd_name}."
            )
            model = self._run_stage(DiagramsModel, _SYSTEM["diagrams"], user, images=images, step="diagrams")
            return model.model_dump()
        except Exception as exc:  # noqa: BLE001  (e.g. model is not vision-capable)
            return {"diagrams": [], "summary": "", "note": f"diagram understanding unavailable ({exc})"}

    def _stage_requirement(self, review: Review, analysis: dict) -> dict:
        user = self._context(review, analysis)
        user += "\nUnderstand and describe the security-relevant requirement."
        return self._run_stage(RequirementModel, _SYSTEM["requirement"], user, step="requirement").model_dump()

    def _stage_architecture(self, review: Review, analysis: dict) -> dict:
        user = self._context(review, analysis)
        user += "\nMap the architecture and identify trust boundaries."
        return self._run_stage(ArchitectureModel, _SYSTEM["architecture"], user, step="architecture").model_dump()

    def _stage_assets(self, review: Review, analysis: dict) -> dict:
        user = self._context(review, analysis)
        hits = self._retrieve(review, analysis, ["asset", "data classification", "critical", "pii", "financial", "credential"])
        user += "\n=== RETRIEVED KNOWLEDGE BASE ===\n" + self._hits_text(hits)
        user += "\nIdentify the assets to protect."
        model = self._run_stage(AssetsModel, _SYSTEM["assets"], user, step="assets")
        # attach kb source names to each asset
        kb = list(dict.fromkeys(self._sources(hits)))
        for asset in model.assets:
            if not asset.kb_sources:
                asset.kb_sources = kb[:5]
        return model.model_dump()

    def _stage_threats(self, review: Review, analysis: dict) -> dict:
        user = self._context(review, analysis)
        user += "\nPerform STRIDE threat modelling."
        return self._run_stage(ThreatModel, _SYSTEM["threats"], user, step="threats").model_dump()

    def _stage_decision(self, review: Review, analysis: dict) -> DecisionModel:
        user = self._context(review, analysis)
        hits = self._retrieve(review, analysis, ["penetration test", "dast", "security test", "pentest"])
        user += "\n=== RETRIEVED PRECEDENT ===\n" + self._hits_text(hits)
        user += "\nDetermine the security test required for this change."
        return self._run_stage(DecisionModel, _SYSTEM["decision"], user, step="decision")

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _change_block(review: Review) -> str:
        facts = review.facts or {}
        scope = facts.get("change_scope") or "unknown"
        evidence = facts.get("change_scope_evidence") or ""
        lines = [
            "=== CHANGE TARGET ===",
            f"Change scope: {scope}",
        ]
        if evidence:
            lines.append(f'FRD statement: "{evidence}"')
        lines.append(
            "Directive: This review covers the CHANGE described in the FRD. Analyze only what the "
            "change introduces or modifies. The rest of the application is BACKGROUND context, used "
            "only to understand exposure and adjacent trust boundaries; never extend assets, threats, "
            "or scope to it."
        )
        return "\n".join(lines)

    def _context(self, review: Review, analysis: dict) -> str:
        parts = [self._change_block(review)]

        req = analysis.get("requirement")
        if req:
            summary = (req.get("summary") or "").strip()
            features = req.get("affected_features") or []
            anchor = "=== CHANGE SUMMARY (derived from the requirement stage) ===\n" + (summary or "(none)")
            if features:
                anchor += "\nAffected features: " + ", ".join(features)
            parts.append(anchor)

        parts.extend(
            [
                "=== CHANGE — FRD (review subject) ===",
                _truncate(review.frd_text),
                "=== APPLICATION BACKGROUND — NFRD (context only, not the subject) ===",
                _truncate(review.nfrd_text),
                "=== APP FACTS (context only) ===",
                _fmt(review.facts),
                "=== FORM SELECTIONS (context only) ===",
                _fmt([{"label": f.label, "selected": f.selected} for f in review.form_fields]),
            ]
        )
        for key in ("diagrams", "requirement", "architecture", "assets", "threats"):
            if analysis.get(key):
                parts.append(f"=== {key.upper()} (JSON) ===")
                parts.append(_fmt(analysis[key]))
        return "\n".join(parts)

    def _retrieve(self, review: Review, analysis: dict, seeds: list[str]) -> list:
        queries = [q for q in (seeds + [review.frd_text[:800], review.nfrd_text[:800]]) if q]
        hits = self._retrieval.query(queries, top_k=4)
        for name in self._sources(hits):
            if name not in self._seen_sources:
                self._seen_sources.append(name)
        return hits

    @staticmethod
    def _hits_text(hits) -> str:
        if not hits:
            return "- no relevant knowledge base content retrieved"
        return "\n\n".join(
            f"--- Source: {h.doc_name} [{h.doc_type.value}] ---\n{h.chunk.text[:1200]}" for h in hits[:4]
        )

    @staticmethod
    def _sources(hits) -> list[str]:
        seen: list[str] = []
        for hit in hits:
            if hit.doc_name and hit.doc_name not in seen:
                seen.append(hit.doc_name)
        return seen

    def _run_stage(
        self,
        model_cls: type[BaseModel],
        system: str,
        user: str,
        images: list[bytes] | None = None,
        step: str | None = None,
    ):
        last_error: Exception | None = None
        for attempt in range(3):
            fmt = "json" if attempt < 2 else None
            raw = self._llm.generate(
                user if attempt == 0 else "Return ONLY the JSON object matching the schema.\n\n" + user,
                system=system,
                format=fmt,
                images=images,
                step=step,
            )
            try:
                return model_cls.model_validate(parse_json_object(raw))
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise ValueError(f"Stage produced invalid output: {last_error}") from last_error

    def _set_stage(self, review: Review, analysis: dict, stage: str) -> None:
        review.analysis = analysis
        review.current_stage = stage
        self._save(review)

    def _save(self, review: Review) -> Review:
        review.updated_at = datetime.now(timezone.utc)
        return self._reviews.update(review)

    @staticmethod
    def _to_domain(model: DecisionModel) -> SecurityDecision:
        try:
            level = TestLevel(model.test_level)
        except ValueError:
            level = TestLevel.DAST
        return SecurityDecision(
            requires_pentest=model.requires_pentest,
            test_level=level,
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
