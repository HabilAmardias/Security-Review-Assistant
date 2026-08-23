"""Pydantic schemas that validate structured LLM output (facts + decision)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FactsModel(BaseModel):
    app_name: str = ""
    app_type: str = "web"  # web | mobile | api | desktop | internal | other
    exposure: str = "internal"  # internet-facing | internal | partner
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
    test_level: str = "dast"  # pentest | dast | both | none
    classification_reason: str = ""
    risk_factors: list[str] = Field(default_factory=list)
    scope: ScopeModel = Field(default_factory=ScopeModel)
    recommended_frameworks: list[str] = Field(default_factory=list)
