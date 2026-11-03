"""Tests for the default vital policy (Rule R2, R4).

Safety Properties:
- Demo defaults are strictly tagged [ASSUMED DEMO DEFAULT].
- Missing vitals are filled with conservative population-appropriate values only.
- Measured values are NEVER overwritten.
- GCS is never assumed (unknown consciousness is safer).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.contracts.enums import AgeUnit
from triagerag.contracts.schemas import Age, Measured, Patient, Vitals
from triagerag.defaults import (
    DEFAULT_DEMO_VITALS_BY_AGE_GROUP,
    DEFAULT_DEMO_WEIGHT_KG,
    apply_demo_defaults,
)


def _make_adult_patient_unknown_vitals() -> Patient:
    return Patient(
        assessed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        age=Age(value=Decimal("30"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](source="unknown"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](source="unknown"),
            systolic_bp_mmhg=Measured[int](source="unknown"),
            diastolic_bp_mmhg=Measured[int](source="unknown"),
            respiratory_rate_bpm=Measured[int](source="unknown"),
            spo2_percent=Measured[int](source="unknown"),
            temperature_c=Measured[Decimal](source="unknown"),
        ),
        allergy_history_status="confirmed_nkda",
        medication_history_status="confirmed_none",
    )


def test_apply_demo_defaults_fills_unknown_vitals() -> None:
    patient = _make_adult_patient_unknown_vitals()
    filled, tags = apply_demo_defaults(patient)
    assert filled.vitals.heart_rate_bpm.source == "estimated"
    assert filled.vitals.heart_rate_bpm.value == 80
    assert filled.vitals.systolic_bp_mmhg.source == "estimated"
    assert filled.vitals.systolic_bp_mmhg.value == 120
    assert filled.vitals.spo2_percent.source == "estimated"
    assert filled.vitals.spo2_percent.value == 98
    assert filled.weight_kg.source == "estimated"
    assert filled.weight_kg.value == Decimal("70")


def test_apply_demo_defaults_assumption_tags_labeled() -> None:
    patient = _make_adult_patient_unknown_vitals()
    _, tags = apply_demo_defaults(patient)
    assert len(tags) > 0
    assert all("[ASSUMED DEMO DEFAULT]" in t for t in tags)
    assert any("Weight" in t for t in tags)
    assert any("Heart rate" in t for t in tags)
    assert any("Systolic BP" in t for t in tags)


def test_apply_demo_defaults_does_not_override_measured() -> None:
    patient = _make_adult_patient_unknown_vitals()
    measured_vitals = patient.vitals.model_copy(
        update={"heart_rate_bpm": Measured[int](value=95, source="measured")}
    )
    patient = patient.model_copy(update={"vitals": measured_vitals})
    filled, tags = apply_demo_defaults(patient)
    assert filled.vitals.heart_rate_bpm.value == 95
    assert filled.vitals.heart_rate_bpm.source == "measured"
    assert not any("Heart rate" in t for t in tags)


def test_apply_demo_defaults_no_change_when_all_measured() -> None:
    patient = _make_adult_patient_unknown_vitals()
    measured_vitals = patient.vitals.model_copy(
        update={
            "heart_rate_bpm": Measured[int](value=80, source="measured"),
            "systolic_bp_mmhg": Measured[int](value=120, source="measured"),
            "diastolic_bp_mmhg": Measured[int](value=80, source="measured"),
            "respiratory_rate_bpm": Measured[int](value=16, source="measured"),
            "spo2_percent": Measured[int](value=98, source="measured"),
            "temperature_c": Measured[Decimal](value=Decimal("37.0"), source="measured"),
        }
    )
    measured_weight = Measured[Decimal](value=Decimal("75"), source="measured")
    patient = patient.model_copy(update={"vitals": measured_vitals, "weight_kg": measured_weight})
    filled, tags = apply_demo_defaults(patient)
    assert tags == []
    assert filled == patient


def test_apply_demo_defaults_gcs_never_filled() -> None:
    patient = _make_adult_patient_unknown_vitals()
    filled, tags = apply_demo_defaults(patient)
    if filled.vitals.gcs_total is not None:
        assert filled.vitals.gcs_total.source == "unknown"


def test_apply_demo_defaults_paediatric_population() -> None:
    patient = Patient(
        assessed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        age=Age(value=Decimal("5"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](source="unknown"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](source="unknown"),
            systolic_bp_mmhg=Measured[int](source="unknown"),
        ),
        allergy_history_status="confirmed_nkda",
        medication_history_status="confirmed_none",
    )
    filled, tags = apply_demo_defaults(patient)
    assert filled.weight_kg.value == DEFAULT_DEMO_WEIGHT_KG["paediatric"]
    assert (
        filled.vitals.heart_rate_bpm.value
        == DEFAULT_DEMO_VITALS_BY_AGE_GROUP["paediatric"]["heart_rate_bpm"]
    )
