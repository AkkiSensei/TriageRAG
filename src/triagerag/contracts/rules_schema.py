"""Clinical rule schema definitions and discriminated unions (Schema V2 / T6.1).

Safety Property:
All rule types are strictly validated discriminated unions with mandatory Provenance
and explicit requires_fields to prevent silent rule bypass on incomplete data.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from triagerag.contracts.enums import (
    PopulationCategory,
    Route,
    RuleStatus,
    Severity,
)
from triagerag.contracts.schemas import Provenance


class RuleEvidence(BaseModel):
    """Evidence chunk citation grounding a clinical rule (T6.1 / T6.6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    quote: str
    sha256: str


class BaselineAlertConfig(BaseModel):
    """Baseline alert text and severity for an active home medication check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Severity
    text: str


class BaseRule(BaseModel):
    """Base fields shared across all deterministic clinical rules (Schema V2)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    severity: Severity
    status: RuleStatus = RuleStatus.ACTIVE
    consequence: str
    action: str
    requires_fields: list[str] = Field(default_factory=list)
    provenance: Provenance
    tier: Literal["A", "B"] = "A"
    severity_by_context: dict[str, Severity] | None = None
    baseline: BaselineAlertConfig | None = None
    on_indeterminate: Severity | Literal["UNVERIFIED", "SKIP"] = "UNVERIFIED"
    applies_to_routes: list[Route] | None = None
    evidence: list[RuleEvidence] = Field(default_factory=list)


class PairRule(BaseRule):
    """Drug-drug interaction rule between two specific drug identifiers."""

    type: Literal["pair"]
    drug_a: str
    drug_b: str


class ClassInteractionRule(BaseRule):
    """Interaction rule between drug classes with per-ingredient lookback windows."""

    type: Literal["class_interaction"]
    class_a: str
    class_b: str
    lookback_hours_by_ingredient: dict[str, Decimal] = Field(default_factory=dict)


class AllergyCrossReactivityRule(BaseRule):
    """Cross-reactivity rule between allergen classes and target classes/side-chains."""

    type: Literal["allergy_crossreactivity"]
    allergen_class: str
    target_class: str
    reaction_types: list[
        Literal["anaphylaxis_ige", "severe_cutaneous_scar", "mild_rash", "gi_upset", "unknown"]
    ]
    cross_reactivity_risk: Severity = Severity.BLOCK


class VitalsInterlockRule(BaseRule):
    """Physiological vital sign contraindication interlock for a medication."""

    type: Literal["vitals_interlock"]
    drug_id: str
    vital_name: str
    operator: Literal["lt", "lte", "gt", "gte", "eq"]
    threshold_value: Decimal | None = None
    threshold_str: str | None = None


class PopulationRule(BaseRule):
    """Population-based or pregnancy contraindication rule."""

    type: Literal["population"]
    drug_id: str
    contraindicated_population: PopulationCategory | None = None
    contraindicated_pregnancy: bool = False


class DuplicationRule(BaseRule):
    """Therapeutic duplication rule for excessive concurrent agents within a class."""

    type: Literal["duplication"]
    class_name: str
    max_concurrent: int = 1


# --- Schema V2 New Rule Types (T6.1 / AUB-ENG-03) ---


class ConditionContraindicationRule(BaseRule):
    """Medication or class contraindicated given a clinical condition or diagnosis (Need C)."""

    type: Literal["condition_contraindication"]
    drug_id: str | None = None
    class_name: str | None = None
    condition: str
    prohibited_status: Literal["yes", "no", "unknown"] = "yes"


class LabInterlockRule(BaseRule):
    """Laboratory value interlock contraindication or threshold limit (Need L)."""

    type: Literal["lab_interlock"]
    drug_id: str | None = None
    class_name: str | None = None
    lab_name: str
    operator: Literal["lt", "lte", "gt", "gte", "eq"]
    threshold_value: Decimal
    unit: str


class RouteConcentrationRule(BaseRule):
    """Administration route, maximum concentration, and diluent safety rule (Needs R, K)."""

    type: Literal["route_concentration"]
    drug_id: str
    max_concentration_mg_per_ml: Decimal | None = None
    allowed_routes: list[Route] = Field(default_factory=list)
    allowed_diluents: list[str] = Field(default_factory=list)
    requires_central_line: bool = False


class OrganFunctionRule(BaseRule):
    """Renal or hepatic impairment dosing and contraindication interlock (Needs L, C)."""

    type: Literal["organ_function"]
    drug_id: str
    organ: Literal["renal", "hepatic"]
    max_stage_allowed: Literal["none", "mild", "moderate", "severe"] = "moderate"
    egfr_cutoff_ml_min: Decimal | None = None
    contraindicated_if_dialysis: bool = True


class CoAdministrationRule(BaseRule):
    """Rule governing concurrent co-administration of drug combinations or routes."""

    type: Literal["co_administration"]
    drug_or_class_a: str
    drug_or_class_b: str
    routes_a: list[Route] | None = None
    routes_b: list[Route] | None = None
    concurrent_only: bool = True


class RateLimitRule(BaseRule):
    """Maximum administration rate ceiling rule (Need Rt)."""

    type: Literal["rate_limit"]
    drug_id: str
    max_rate_mg_per_min: Decimal | None = None
    max_rate_mg_per_kg_min: Decimal | None = None
    route: Route = Route.iv


ClinicalRule = Annotated[
    PairRule
    | ClassInteractionRule
    | AllergyCrossReactivityRule
    | VitalsInterlockRule
    | PopulationRule
    | DuplicationRule
    | ConditionContraindicationRule
    | LabInterlockRule
    | RouteConcentrationRule
    | OrganFunctionRule
    | CoAdministrationRule
    | RateLimitRule,
    Field(discriminator="type"),
]
