"""Clinical payload normalization and validation helpers.

Safety Property:
Normalizes Patient entities using the immutable registry without mutating input state.
Fuzzy matches populate suggestion fields while preserving resolved=False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from triagerag.contracts.schemas import IngredientStrength, Patient

if TYPE_CHECKING:
    from triagerag.normalize.aliases import AliasResolver


def normalize_patient(patient: Patient, resolver: AliasResolver) -> Patient:
    """Normalize a patient medication and allergy entries using an AliasResolver.

    Returns a new or updated Patient instance with normalized/resolved fields populated.
    """
    updated_meds = []
    for med in patient.medications:
        med_copy = med.model_copy()
        resolved, matched_id, suggestion = resolver.resolve(med.raw_text)
        if resolved and matched_id:
            med_copy.resolved = True
            med_copy.suggestion = None

            # Populate ingredients if matched to an alias or formulary drug
            if matched_id in resolver.aliases:
                alias_entry = resolver.aliases[matched_id]
                med_copy.ingredients = list(alias_entry.strengths)
            elif matched_id in resolver.formulary_drugs:
                drug = resolver.formulary_drugs[matched_id]
                med_copy.ingredients = [
                    IngredientStrength(ingredient_id=ing) for ing in drug.ingredient_ids
                ]
            else:
                # Direct active ingredient
                med_copy.ingredients = [IngredientStrength(ingredient_id=matched_id)]
        else:
            med_copy.resolved = False
            med_copy.suggestion = suggestion
        updated_meds.append(med_copy)

    updated_allergies = []
    for allergy in patient.allergies:
        allergy_copy = allergy.model_copy()
        resolved, matched_id, suggestion = resolver.resolve(allergy.raw_substance)
        if resolved and matched_id:
            allergy_copy.resolved = True
            allergy_copy.normalized_allergen_id = matched_id
            allergy_copy.suggestion = None
        else:
            allergy_copy.resolved = False
            allergy_copy.suggestion = suggestion
        updated_allergies.append(allergy_copy)

    patient_copy = patient.model_copy(
        update={
            "medications": updated_meds,
            "allergies": updated_allergies,
        }
    )
    return patient_copy


def build_patient_from_case(case: dict[str, Any], registry: Any) -> Patient:
    """Build and normalize a Patient model from a golden case definition dictionary."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal
    from typing import Literal

    from triagerag.contracts.enums import Consciousness
    from triagerag.contracts.schemas import (
        Age,
        AllergyEntry,
        Measured,
        MedicationEntry,
        Patient,
        Vitals,
    )

    assessed_at = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)

    age_val = Decimal(str(case.get("age_value", 35)))
    age_unit = case.get("age_unit", "years")
    age = Age(value=age_val, unit=age_unit)

    # Build vitals
    sbp_val = case.get("systolic_bp")
    hr_val = case.get("heart_rate")

    vitals = Vitals(
        systolic_bp_mmhg=(
            Measured[int](value=int(sbp_val), source="measured")
            if sbp_val is not None
            else Measured[int]()
        ),
        heart_rate_bpm=(
            Measured[int](value=int(hr_val), source="measured")
            if hr_val is not None
            else Measured[int]()
        ),
        respiratory_rate_bpm=Measured[int](value=16, source="measured"),
        spo2_percent=Measured[int](value=98, source="measured"),
        supplemental_o2=Measured[Literal["yes", "no", "unknown"]](value="no", source="measured"),
        temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
        consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
    )

    # Build medications
    medications: list[MedicationEntry] = []
    med_names = case.get("medications", [])
    last_dose_map = case.get("last_dose_hours_ago", {})

    for name in med_names:
        last_dose_time = None
        if name in last_dose_map:
            hours_ago = last_dose_map[name]
            if hours_ago is not None:
                last_dose_time = assessed_at - timedelta(hours=float(hours_ago))

        medications.append(
            MedicationEntry(
                raw_text=name,
                last_dose_time=last_dose_time,
            )
        )

    # Build allergies
    allergies: list[AllergyEntry] = []
    raw_allergies = case.get("allergies", [])
    for a in raw_allergies:
        allergies.append(
            AllergyEntry(
                raw_substance=a["substance"],
                reaction_type=a.get("reaction_type", "unknown"),
            )
        )

    med_status = case.get("medication_history_status")
    if not med_status:
        med_status = "confirmed_list" if medications else "confirmed_none"

    allergy_status = case.get("allergy_history_status")
    if not allergy_status:
        allergy_status = "confirmed_list" if allergies else "confirmed_none"

    raw_patient = Patient(
        assessed_at=assessed_at,
        age=age,
        sex=case.get("sex", "female"),
        pregnancy=case.get("pregnancy", "no"),
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=vitals,
        allergy_history_status=allergy_status,
        medication_history_status=med_status,
        allergies=allergies,
        medications=medications,
    )

    return normalize_patient(raw_patient, registry.resolver)
