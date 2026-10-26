"""Data schemas for YAML files in data/ directory.

Safety Property:
Enforces strict validation of formulary drugs, brand aliases, drug classes,
and scoring tables at load time. FDC formulations must specify valid dose_basis_ingredient_id.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from triagerag.contracts.enums import (
    DoseUnit,
    PopulationCategory,
    Route,
    RuleStatus,
    ScoreBand,
)
from triagerag.contracts.schemas import ExplicitDose, IngredientStrength, Provenance


class PopulationDoseLimit(BaseModel):
    """Formulary dosage boundaries for a specific population category."""

    model_config = ConfigDict(extra="forbid")

    dose_basis: Literal["fixed", "weight"] = "fixed"
    per_dose_min: Decimal | None = None
    per_dose_max: Decimal | None = None
    daily_max: Decimal | None = None
    unit: DoseUnit = DoseUnit.mg
    status: RuleStatus = RuleStatus.ACTIVE
    provenance: Provenance

    @model_validator(mode="after")
    def validate_limits(self) -> PopulationDoseLimit:
        if (
            self.status == RuleStatus.ACTIVE
            and self.per_dose_min is not None
            and self.per_dose_max is not None
            and self.per_dose_min > self.per_dose_max
        ):
            raise ValueError("per_dose_min cannot exceed per_dose_max")
        return self


class ConcentrationEntry(BaseModel):
    """Standard concentration and volume entry."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal
    unit: DoseUnit
    volume_ml: Decimal


class FormularyDrug(BaseModel):
    """Formulary drug specification."""

    model_config = ConfigDict(extra="forbid")

    drug_id: str
    display_name: str
    ingredient_ids: list[str]
    classes: list[str] = Field(default_factory=list)
    routes: list[Route]
    dose_basis_ingredient_id: str | None = None
    ingredient_daily_ceilings: dict[str, ExplicitDose] = Field(default_factory=dict)
    population_rules: dict[str, PopulationDoseLimit] = Field(default_factory=dict)
    concentrations: list[ConcentrationEntry] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def validate_fdc_requirements(self) -> FormularyDrug:
        if len(self.ingredient_ids) > 1:
            if not self.dose_basis_ingredient_id:
                err = (
                    f"Fixed-dose combination drug '{self.drug_id}' "
                    "must specify dose_basis_ingredient_id"
                )
                raise ValueError(err)
            if self.dose_basis_ingredient_id not in self.ingredient_ids:
                err = (
                    f"dose_basis_ingredient_id '{self.dose_basis_ingredient_id}' "
                    "not found in ingredient_ids"
                )
                raise ValueError(err)
        return self


class AliasEntry(BaseModel):
    """Brand name or alias mapping to active ingredients."""

    model_config = ConfigDict(extra="forbid")

    brand_name: str
    ingredient_ids: list[str]
    strengths: list[IngredientStrength] = Field(default_factory=list)
    dose_basis_ingredient_id: str | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_alias_fdc(self) -> AliasEntry:
        if len(self.ingredient_ids) > 1 and not self.dose_basis_ingredient_id:
            raise ValueError(
                f"Multi-ingredient alias '{self.brand_name}' must declare dose_basis_ingredient_id"
            )
        return self


class ClassesMapping(BaseModel):
    """Mapping of active ingredients to clinical classes."""

    model_config = ConfigDict(extra="forbid")

    ingredient_to_classes: dict[str, list[str]]
    provenance: Provenance


class AcronymMapping(BaseModel):
    """Clinical acronym expansion mapping."""

    model_config = ConfigDict(extra="forbid")

    acronyms: dict[str, str]


class EWSThresholdRow(BaseModel):
    """Single row in an early warning score physiological table."""

    model_config = ConfigDict(extra="forbid")

    parameter: str
    score: int
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    string_value: str | None = None


class EWSTable(BaseModel):
    """Physiological early-warning score definition."""

    model_config = ConfigDict(extra="forbid")

    table_name: str
    population: PopulationCategory
    rows: list[EWSThresholdRow]
    bands: dict[ScoreBand, tuple[int, int]]
    provenance: Provenance
