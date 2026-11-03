"""Structured retrieval predicate vocabulary and evaluation engine.

Safety Properties (Rule R3, D2, AUB Task T2.1):
1. Predicates describe conditions strictly over structured Patient schema fields.
2. Predicates are retrieval-ranking signals ONLY and are NOT clinical rules, thresholds,
   or approval conditions.
3. Every predicate carries source_status: SYNTHETIC_AUTHORED.
4. Target fields are verified against the real Patient schema; invalid fields fail validation.
5. Missing or unknown patient values yield PredicateEvalResult.UNKNOWN and never silently
   become False.
6. Clinical rule engines (triagerag.engine) must never consume or import this module.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from triagerag.config import get_data_dir
from triagerag.contracts.enums import SourceStatus
from triagerag.contracts.schemas import Patient, Provenance, Vitals
from triagerag.normalize.yaml_loader import load_yaml_decimal


class PredicateEvalResult(StrEnum):
    """Tri-state outcome of evaluating a retrieval predicate against patient data."""

    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNKNOWN = "unknown"


class PredicateOperator(StrEnum):
    """Supported predicate condition operators."""

    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "=="
    NE = "!="
    IN = "in"
    HAS_CLASS = "has_class"
    HAS_INGREDIENT = "has_ingredient"


_ALLOWED_PATIENT_TOP_LEVEL = {
    "age",
    "sex",
    "pregnancy",
    "weight_kg",
    "renal_impairment",
    "hepatic_impairment",
    "medications",
    "allergies",
}


def _validate_patient_field_path(field_path: str) -> None:
    """Validate that field_path maps to a real field in Patient schema."""
    parts = field_path.strip().split(".")
    root = parts[0]
    if root == "vitals":
        if len(parts) != 2:
            raise ValueError(f"Invalid vitals field path '{field_path}'; expected vitals.<field>")
        vital_field = parts[1]
        if vital_field not in Vitals.model_fields:
            raise ValueError(
                f"Invalid target_field '{field_path}': '{vital_field}' not in Vitals schema"
            )
        return

    if root == "age":
        if len(parts) != 2 or parts[1] not in ("to_days", "population_category"):
            raise ValueError(
                f"Invalid age field path '{field_path}'; "
                f"expected age.to_days or age.population_category"
            )
        return

    if root not in _ALLOWED_PATIENT_TOP_LEVEL:
        raise ValueError(
            f"Invalid target_field '{field_path}': '{root}' not in Patient schema fields"
        )


class PredicateDefinition(BaseModel):
    """Structured retrieval predicate condition over Patient schema (T2.1, D2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    description: str
    target_field: str
    operator: PredicateOperator
    threshold: Decimal | None = None
    expected_value: str | None = None
    allowed_values: list[str] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def validate_schema_and_provenance(self) -> PredicateDefinition:
        _validate_patient_field_path(self.target_field)

        if self.provenance.source_status != SourceStatus.SYNTHETIC_AUTHORED:
            raise ValueError(
                f"Predicate '{self.id}' must carry source_status=SYNTHETIC_AUTHORED, "
                f"got {self.provenance.source_status}"
            )

        is_numeric_op = self.operator in (
            PredicateOperator.LT,
            PredicateOperator.LE,
            PredicateOperator.GT,
            PredicateOperator.GE,
        )
        if is_numeric_op and self.threshold is None:
            raise ValueError(
                f"Numeric predicate '{self.id}' with operator '{self.operator}' requires threshold"
            )

        if self.operator == PredicateOperator.IN and not self.allowed_values:
            raise ValueError(
                f"Predicate '{self.id}' with operator 'in' requires non-empty allowed_values"
            )

        is_value_op = self.operator in (
            PredicateOperator.EQ,
            PredicateOperator.NE,
            PredicateOperator.HAS_CLASS,
            PredicateOperator.HAS_INGREDIENT,
        )
        if is_value_op and self.expected_value is None:
            raise ValueError(
                f"Predicate '{self.id}' with operator '{self.operator}' requires expected_value"
            )

        return self


class PredicateVocabularyConfig(BaseModel):
    """Structured predicate vocabulary bundle loaded from data/retrieval/predicates.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "1.0.0"
    source_status: SourceStatus = SourceStatus.SYNTHETIC_AUTHORED
    provenance: Provenance
    predicates: list[PredicateDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_predicate_ids(self) -> PredicateVocabularyConfig:
        seen: set[str] = set()
        for p in self.predicates:
            if p.id in seen:
                raise ValueError(f"Duplicate predicate ID in vocabulary: '{p.id}'")
            seen.add(p.id)
        return self


@lru_cache
def _load_classes_map(data_dir: Path | None = None) -> dict[str, list[str]]:
    """Load ingredient-to-classes mapping from data/classes.yaml."""
    target_dir = data_dir if data_dir is not None else get_data_dir()
    classes_path = target_dir / "classes.yaml"
    if not classes_path.exists():
        classes_path = get_data_dir() / "classes.yaml"
    if not classes_path.exists():
        return {}
    data = load_yaml_decimal(classes_path)
    if isinstance(data, dict):
        ing_to_classes = data.get("ingredient_to_classes", {})
        if isinstance(ing_to_classes, dict):
            return {
                str(k).lower(): [str(c).upper() for c in v]
                for k, v in ing_to_classes.items()
                if isinstance(v, list)
            }
    return {}


@lru_cache
def load_predicate_vocabulary(data_dir: Path | None = None) -> PredicateVocabularyConfig:
    """Load and validate structured retrieval predicates from data/retrieval/predicates.yaml."""
    target_dir = data_dir if data_dir is not None else get_data_dir()
    pred_path = target_dir / "retrieval" / "predicates.yaml"
    if not pred_path.exists():
        pred_path = get_data_dir() / "retrieval" / "predicates.yaml"
    raw_data: Any = load_yaml_decimal(pred_path)
    return PredicateVocabularyConfig.model_validate(raw_data)


def evaluate_predicate(
    predicate: PredicateDefinition,
    patient: Patient,
    classes_mapping: dict[str, list[str]] | None = None,
) -> PredicateEvalResult:
    """Evaluate a single structured predicate against patient attributes with tri-state logic."""
    target = predicate.target_field
    classes = classes_mapping if classes_mapping is not None else _load_classes_map()

    # 1. Vital signs (Measured[T])
    if target.startswith("vitals."):
        vital_name = target.split(".", 1)[1]
        measured = getattr(patient.vitals, vital_name, None)
        if measured is None or measured.source == "unknown" or measured.value is None:
            return PredicateEvalResult.UNKNOWN

        val = measured.value

        # Numeric vital comparison
        if predicate.operator in (
            PredicateOperator.LT,
            PredicateOperator.LE,
            PredicateOperator.GT,
            PredicateOperator.GE,
        ):
            if predicate.threshold is None:
                return PredicateEvalResult.UNKNOWN
            dec_val = Decimal(str(val))
            if predicate.operator == PredicateOperator.LT:
                return (
                    PredicateEvalResult.SATISFIED
                    if dec_val < predicate.threshold
                    else PredicateEvalResult.NOT_SATISFIED
                )
            if predicate.operator == PredicateOperator.LE:
                return (
                    PredicateEvalResult.SATISFIED
                    if dec_val <= predicate.threshold
                    else PredicateEvalResult.NOT_SATISFIED
                )
            if predicate.operator == PredicateOperator.GT:
                return (
                    PredicateEvalResult.SATISFIED
                    if dec_val > predicate.threshold
                    else PredicateEvalResult.NOT_SATISFIED
                )
            if predicate.operator == PredicateOperator.GE:
                return (
                    PredicateEvalResult.SATISFIED
                    if dec_val >= predicate.threshold
                    else PredicateEvalResult.NOT_SATISFIED
                )

        # Categorical vital comparison (e.g. consciousness AVPU)
        val_str = str(val.value if hasattr(val, "value") else val).upper()
        if predicate.operator == PredicateOperator.EQ:
            expected = str(predicate.expected_value or "").upper()
            is_match = (val_str == expected) or (expected == "ALERT" and val_str == "A")
            return PredicateEvalResult.SATISFIED if is_match else PredicateEvalResult.NOT_SATISFIED
        if predicate.operator == PredicateOperator.NE:
            expected = str(predicate.expected_value or "").upper()
            is_match = (val_str != expected) and not (expected == "ALERT" and val_str == "A")
            return PredicateEvalResult.SATISFIED if is_match else PredicateEvalResult.NOT_SATISFIED
        if predicate.operator == PredicateOperator.IN:
            allowed = [s.upper() for s in predicate.allowed_values]
            return (
                PredicateEvalResult.SATISFIED
                if val_str in allowed
                else PredicateEvalResult.NOT_SATISFIED
            )

    # 2. Age fields
    if target == "age.to_days":
        age_days = patient.age.to_days()
        if predicate.threshold is None:
            return PredicateEvalResult.UNKNOWN
        if predicate.operator == PredicateOperator.LE:
            return (
                PredicateEvalResult.SATISFIED
                if age_days <= predicate.threshold
                else PredicateEvalResult.NOT_SATISFIED
            )
        if predicate.operator == PredicateOperator.LT:
            return (
                PredicateEvalResult.SATISFIED
                if age_days < predicate.threshold
                else PredicateEvalResult.NOT_SATISFIED
            )
        if predicate.operator == PredicateOperator.GE:
            return (
                PredicateEvalResult.SATISFIED
                if age_days >= predicate.threshold
                else PredicateEvalResult.NOT_SATISFIED
            )
        if predicate.operator == PredicateOperator.GT:
            return (
                PredicateEvalResult.SATISFIED
                if age_days > predicate.threshold
                else PredicateEvalResult.NOT_SATISFIED
            )

    if target == "age.population_category":
        pop_str = str(patient.age.population_category.value).lower()
        expected = str(predicate.expected_value or "").lower()
        if predicate.operator == PredicateOperator.EQ:
            return (
                PredicateEvalResult.SATISFIED
                if pop_str == expected
                else PredicateEvalResult.NOT_SATISFIED
            )

    # 3. Medications
    if target == "medications":
        if patient.medication_history_status in ("incomplete", "unknown_unobtainable"):
            return PredicateEvalResult.UNKNOWN
        if patient.medication_history_status in ("confirmed_none", "confirmed_nkda"):
            return PredicateEvalResult.NOT_SATISFIED

        # confirmed_list
        if predicate.operator == PredicateOperator.HAS_CLASS:
            target_class = str(predicate.expected_value or "").upper()
            for med in patient.medications:
                for ing in med.ingredients:
                    ing_classes = classes.get(ing.ingredient_id.lower(), [])
                    if target_class in ing_classes:
                        return PredicateEvalResult.SATISFIED
                raw_lower = med.raw_text.lower()
                for ing_id, ing_classes in classes.items():
                    if ing_id in raw_lower and target_class in ing_classes:
                        return PredicateEvalResult.SATISFIED
            return PredicateEvalResult.NOT_SATISFIED

        if predicate.operator == PredicateOperator.HAS_INGREDIENT:
            target_ing = str(predicate.expected_value or "").lower()
            for med in patient.medications:
                for ing in med.ingredients:
                    if ing.ingredient_id.lower() == target_ing:
                        return PredicateEvalResult.SATISFIED
            return PredicateEvalResult.NOT_SATISFIED

    # 4. Allergies
    if target == "allergies":
        if patient.allergy_history_status in ("incomplete", "unknown_unobtainable"):
            return PredicateEvalResult.UNKNOWN
        if patient.allergy_history_status in ("confirmed_none", "confirmed_nkda"):
            return PredicateEvalResult.NOT_SATISFIED

        # confirmed_list
        if predicate.operator == PredicateOperator.HAS_CLASS:
            target_class = str(predicate.expected_value or "").upper()
            for allg in patient.allergies:
                if allg.allergen_class and allg.allergen_class.upper() == target_class:
                    return PredicateEvalResult.SATISFIED
                if allg.normalized_allergen_id:
                    allg_classes = classes.get(allg.normalized_allergen_id.lower(), [])
                    if target_class in allg_classes:
                        return PredicateEvalResult.SATISFIED
                raw_lower = allg.raw_substance.lower()
                for ing_id, ing_classes in classes.items():
                    if ing_id in raw_lower and target_class in ing_classes:
                        return PredicateEvalResult.SATISFIED
            return PredicateEvalResult.NOT_SATISFIED

    # 5. Top-level categorical attributes
    raw_attr = getattr(patient, target, None)
    if raw_attr is None or raw_attr == "unknown":
        return PredicateEvalResult.UNKNOWN

    raw_str = str(raw_attr).lower()
    expected = str(predicate.expected_value or "").lower()
    if predicate.operator == PredicateOperator.EQ:
        return (
            PredicateEvalResult.SATISFIED
            if raw_str == expected
            else PredicateEvalResult.NOT_SATISFIED
        )
    if predicate.operator == PredicateOperator.NE:
        return (
            PredicateEvalResult.SATISFIED
            if raw_str != expected
            else PredicateEvalResult.NOT_SATISFIED
        )

    return PredicateEvalResult.UNKNOWN


def evaluate_patient_predicates(
    patient: Patient,
    predicates: list[PredicateDefinition],
    classes_mapping: dict[str, list[str]] | None = None,
) -> dict[str, PredicateEvalResult]:
    """Evaluate a collection of predicates for a patient, returning mapping from predicate ID."""
    classes = classes_mapping if classes_mapping is not None else _load_classes_map()
    return {
        pred.id: evaluate_predicate(pred, patient, classes_mapping=classes) for pred in predicates
    }
