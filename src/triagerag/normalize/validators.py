"""Clinical payload normalization and validation helpers.

Safety Property:
Normalizes Patient entities using the immutable registry without mutating input state.
Fuzzy matches populate suggestion fields while preserving resolved=False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient
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
            # Populate ingredients if matched to an alias or formulary drug
            if matched_id in resolver.aliases:
                alias_entry = resolver.aliases[matched_id]
                med_copy.ingredients = alias_entry.strengths
            med_copy.suggestion = None
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
