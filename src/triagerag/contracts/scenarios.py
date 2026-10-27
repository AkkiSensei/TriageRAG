"""Preloaded synthetic scenarios for testing, CLI demos, and Streamlit UI.

Safety Property:
All scenarios use 100% synthetic patient data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from triagerag.contracts.enums import (
    AgeUnit,
    Consciousness,
    DoseUnit,
    Route,
)
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    ExplicitDose,
    IngredientStrength,
    Measured,
    MedicationEntry,
    OverrideRecord,
    Patient,
    Vitals,
)


def get_preloaded_scenario(name: str) -> tuple[Patient, list[OverrideRecord]]:
    """Return a preloaded synthetic patient and optional overrides.

    Scenarios:
    1. BLOCK: Patient on sildenafil within 12h presenting with ischemic chest pain.
       Nitroglycerin protocol step is BLOCKED and struck through.
    2. UNVERIFIED: Patient with unknown allergy history and missing vital signs.
       Yields UNVERIFIED verdict and highlights 'What I couldn't check'.
    3. HIGH: Patient with penicillin allergy prescribed cephalosporin (dissimilar side-chain).
       Requires clinician override to proceed.
    4. CLEAN: Patient with acute anaphylaxis, full vital signs, confirmed NKDA.
       Normal clear protocol verification.
    """
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)

    if name.upper() == "BLOCK":
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("58"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("82.0"), source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=92, source="measured"),
                systolic_bp_mmhg=Measured[int](value=138, source="measured"),
                diastolic_bp_mmhg=Measured[int](value=84, source="measured"),
                respiratory_rate_bpm=Measured[int](value=18, source="measured"),
                spo2_percent=Measured[int](value=97, source="measured"),
                supplemental_o2=Measured[str](value="no", source="measured"),
                temperature_c=Measured[Decimal](value=Decimal("37.1"), source="measured"),
                consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
            ),
            medication_history_status="confirmed_list",
            medications=[
                MedicationEntry(
                    raw_text="Viagra",
                    ingredients=[
                        IngredientStrength(
                            ingredient_id="sildenafil",
                            strength_amount=Decimal("50"),
                            strength_unit=DoseUnit.mg,
                        )
                    ],
                    dose_taken=ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg),
                    route=Route.oral,
                    last_dose_time=now - timedelta(hours=12),
                    resolved=True,
                )
            ],
            allergy_history_status="confirmed_nkda",
            allergies=[],
            renal_impairment="no",
            hepatic_impairment="no",
            suspected_syndrome="chest_pain",
            chief_complaint_untrusted="Substernal chest pressure for 2 hours radiating to left jaw",
        )
        return p, []

    if name.upper() == "UNVERIFIED":
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("45"), unit=AgeUnit.years),
            sex="female",
            pregnancy="unknown",
            weight_kg=Measured[Decimal](value=None, source="unknown"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=105, source="measured"),
                systolic_bp_mmhg=Measured[int](value=None, source="unknown"),
                respiratory_rate_bpm=Measured[int](value=None, source="unknown"),
                spo2_percent=Measured[int](value=94, source="measured"),
                supplemental_o2=Measured[str](value=None, source="unknown"),
                consciousness=Measured[Consciousness](value=Consciousness.V, source="measured"),
            ),
            medication_history_status="unknown_unobtainable",
            medications=[],
            allergy_history_status="unknown_unobtainable",
            allergies=[],
            renal_impairment="unknown",
            hepatic_impairment="unknown",
            suspected_syndrome="altered_mental_status",
            chief_complaint_untrusted="Found unresponsive at bus stop, no identification",
        )
        return p, []

    if name.upper() == "HIGH":
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("8"), unit=AgeUnit.years),
            sex="female",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("25.0"), source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=145, source="measured"),
                systolic_bp_mmhg=Measured[int](value=95, source="measured"),
                diastolic_bp_mmhg=Measured[int](value=55, source="measured"),
                respiratory_rate_bpm=Measured[int](value=32, source="measured"),
                spo2_percent=Measured[int](value=94, source="measured"),
                supplemental_o2=Measured[str](value="no", source="measured"),
                temperature_c=Measured[Decimal](value=Decimal("39.2"), source="measured"),
                consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
            ),
            medication_history_status="confirmed_none",
            medications=[],
            allergy_history_status="confirmed_list",
            allergies=[
                AllergyEntry(
                    raw_substance="penicillin",
                    normalized_allergen_id="penicillin",
                    allergen_class="PENICILLINS",
                    reaction_type="anaphylaxis_ige",
                    resolved=True,
                )
            ],
            renal_impairment="no",
            hepatic_impairment="no",
            suspected_syndrome="paediatric_sepsis",
            chief_complaint_untrusted="Fever, chills, lethargy, tachycardia for 1 day",
        )
        override = OverrideRecord(
            rule_id="ALLERGY_PENICILLIN_CEPH_R1_DISSIMILAR",
            step_number=1,
            reason=(
                "Clinician assessment: low cross-reactivity with dissimilar "
                "side chain ceftriaxone in severe sepsis"
            ),
            clinician_id="DR_EMERGENCY_99",
        )
        return p, [override]

    # CLEAN scenario
    p = Patient(
        assessed_at=now,
        age=Age(value=Decimal("30"), unit=AgeUnit.years),
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=122, source="measured"),
            systolic_bp_mmhg=Measured[int](value=88, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=56, source="measured"),
            respiratory_rate_bpm=Measured[int](value=28, source="measured"),
            spo2_percent=Measured[int](value=91, source="measured"),
            supplemental_o2=Measured[str](value="yes", source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_none",
        medications=[],
        allergy_history_status="confirmed_nkda",
        allergies=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome="anaphylaxis",
        chief_complaint_untrusted="Diffuse urticaria, facial angioedema, wheezing after bee sting",
    )
    return p, []
