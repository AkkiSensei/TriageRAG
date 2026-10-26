"""Clinical rule schema definitions and discriminated unions.

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
    RuleStatus,
    Severity,
)
from triagerag.contracts.schemas import Provenance


class BaseRule(BaseModel):
    """Base fields shared across all deterministic clinical rules."""

    model_config = ConfigDict(extra="forbid")

    id: str
    severity: Severity
    status: RuleStatus = RuleStatus.ACTIVE
    consequence: str
    action: str
    requires_fields: list[str] = Field(default_factory=list)
    provenance: Provenance


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


ClinicalRule = Annotated[
    PairRule
    | ClassInteractionRule
    | AllergyCrossReactivityRule
    | VitalsInterlockRule
    | PopulationRule
    | DuplicationRule,
    Field(discriminator="type"),
]
