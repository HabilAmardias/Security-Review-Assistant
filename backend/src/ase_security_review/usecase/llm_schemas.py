"""Pydantic schemas that validate structured LLM output (facts + decision)."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field


def parse_json_object(text: str) -> dict:
    """Tolerantly parse a JSON object from an LLM response.

    Handles empty responses, surrounding prose, and code fences. Raises a
    descriptive ValueError (including a snippet) if no JSON object is found.
    """
    if not text or not text.strip():
        raise ValueError("LLM returned an empty response")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
        stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            candidate = stripped[start : end + 1]
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                pass
        snippet = stripped[:300]
        raise ValueError(f"LLM output is not valid JSON: {snippet!r}") from None


class FactsModel(BaseModel):
    app_name: str = ""
    app_type: str = "web"  # web | mobile | api | desktop | internal | other
    exposure: str = "unclear"  # internet-facing | internal | partner | unclear
    exposure_evidence: str = ""
    change_scope: str = "other"  # full_new_app | feature_change | limited_change | other
    change_scope_evidence: str = ""
    technologies: list[str] = Field(default_factory=list)
    data_classes: list[str] = Field(default_factory=list)
    # semantic tags used by the rule engine, e.g.
    # authentication, authorization, sso, mfa, integration, webhook,
    # internet-facing, internal, compliance, admin, audit
    features: list[str] = Field(default_factory=list)
    auth_model: str = ""
    roles: list[str] = Field(default_factory=list)
    key_features: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    compliance_refs: list[str] = Field(default_factory=list)
    nfr_highlights: list[str] = Field(default_factory=list)
    summary: str = ""


class ScopeModel(BaseModel):
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    test_methods: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    effort_estimate: str = ""


class DecisionModel(BaseModel):
    requires_pentest: bool = False
    test_level: str = "dast"  # pentest | dast | none
    classification_reason: str = ""
    risk_factors: list[str] = Field(default_factory=list)
    scope: ScopeModel = Field(default_factory=ScopeModel)


# ---- staged threat-model pipeline artifacts ----

class DiagramItemModel(BaseModel):
    label: str = ""
    actors: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)
    external_systems: list[str] = Field(default_factory=list)
    notes: str = ""


class DiagramsModel(BaseModel):
    diagrams: list[DiagramItemModel] = Field(default_factory=list)
    summary: str = ""


class RequirementModel(BaseModel):
    summary: str = ""
    data_submitted: list[str] = Field(default_factory=list)      # what information is submitted/processed
    actors: list[str] = Field(default_factory=list)              # who submits / uses it
    destinations: list[str] = Field(default_factory=list)        # where it goes
    approvers: list[str] = Field(default_factory=list)           # who can approve
    triggers: list[str] = Field(default_factory=list)
    affected_features: list[str] = Field(default_factory=list)


class ComponentModel(BaseModel):
    name: str = ""
    role: str = ""
    sensitive: bool = False


class DataFlowModel(BaseModel):
    source: str = ""
    destination: str = ""
    data: str = ""
    protocol: str = ""


class TrustBoundaryModel(BaseModel):
    between: str = ""
    reason: str = ""


class ArchitectureModel(BaseModel):
    summary: str = ""
    components: list[ComponentModel] = Field(default_factory=list)
    data_flows: list[DataFlowModel] = Field(default_factory=list)
    trust_boundaries: list[TrustBoundaryModel] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)


class AssetModel(BaseModel):
    name: str = ""
    asset_type: str = ""          # data | credential | service | availability | component
    sensitivity: str = ""         # e.g. financial | pii | phi | credentials | system
    location: str = ""
    protection_basis: str = ""    # why it needs protecting (SOP/policy basis)
    kb_sources: list[str] = Field(default_factory=list)


class AssetsModel(BaseModel):
    assets: list[AssetModel] = Field(default_factory=list)


class ThreatModel(BaseModel):
    threats: list["ThreatRowModel"] = Field(default_factory=list)


class ThreatRowModel(BaseModel):
    id: str = ""
    element: str = ""             # asset / component / data flow / trust boundary
    stride_category: str = ""     # Spoofing | Tampering | Repudiation | Info disclosure | DoS | Elevation of privilege
    scenario: str = ""
    likelihood: str = ""          # low | medium | high
    impact: str = ""              # low | medium | high
    severity: str = ""            # low | medium | high | critical


ThreatModel.model_rebuild()
