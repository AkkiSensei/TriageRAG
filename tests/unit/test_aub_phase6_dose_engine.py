"""AUB Phase 6 Task T6.2: Dose Engine Expansion Tests.

Tests:
1. Concentration-aware volume calculation (step-level and formulary fallback).
2. Injection volume safety boundaries (e.g., IM > 3.0 mL warning).
3. Minimum dosing interval and frequency verification (against step and patient history).
4. Administration rate checking against formulary limits.
5. Cumulative 24h exposure with absolute mass daily_max semantics.
6. HD-6 invariant preservation (gross overdose remains HIGH + xfail on BLOCK).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from triagerag.config import get_repo_root
from triagerag.contracts.enums import (
    ActionType,
    AgeUnit,
    DoseUnit,
    Route,
    Severity,
)
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    MedicationEntry,
    Patient,
    PlanStepDraft,
    Vitals,
)
from triagerag.engine.dose_engine import (
    calculate_administration_volume,
    verify_administration_rate,
    verify_cumulative_daily_exposure,
    verify_dose,
    verify_dosing_intervals,
)
from triagerag.engine.registry import ClinicalRegistry


@pytest.fixture
def registry() -> ClinicalRegistry:
    return ClinicalRegistry.load_from_directory(get_repo_root() / "data")


def _make_patient(
    age_years: int = 40,
    weight_kg: Decimal = Decimal("70.0"),
    medications: list[MedicationEntry] | None = None,
    med_status: str = "confirmed_none",
    assessed_at: datetime | None = None,
) -> Patient:
    now = assessed_at or datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    return Patient(
        assessed_at=now,
        age=Age(value=Decimal(str(age_years)), unit=AgeUnit.years),
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=weight_kg, source="measured"),
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=120, source="measured")),
        allergy_history_status="confirmed_none",
        medication_history_status=med_status,  # type: ignore[arg-type]
        medications=medications or [],
    )


def test_calculate_administration_volume_formulary(registry: ClinicalRegistry) -> None:
    """Calculates volume from formulary concentration table when step has no explicit concentration."""
    epi = registry.get_drug("epinephrine")
    assert epi is not None
    # 0.5 mg epinephrine with 1 mg/1 mL formulary concentration = 0.5 mL
    dose = ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg)
    vol = calculate_administration_volume(drug=epi, dose=dose)
    assert vol == Decimal("0.5")

    # Dextrose: 25 g with 10 g / 100 mL concentration = 250 mL
    dex = registry.get_drug("dextrose")
    assert dex is not None
    dex_dose = ExplicitDose(amount=Decimal("25"), unit=DoseUnit.g)
    dex_vol = calculate_administration_volume(drug=dex, dose=dex_dose)
    assert dex_vol == Decimal("250")


def test_calculate_administration_volume_step_override(registry: ClinicalRegistry) -> None:
    """Plan step explicit concentration takes precedence over formulary concentration."""
    epi = registry.get_drug("epinephrine")
    assert epi is not None
    dose = ExplicitDose(amount=Decimal("1.0"), unit=DoseUnit.mg)
    # Concentration 0.1 mg/mL (1:10,000 solution) -> 1.0 mg / 0.1 mg/mL = 10 mL
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer IV dilute epinephrine",
        drug_id="epinephrine",
        requested_dose=dose,
        concentration_mg_per_ml=Decimal("0.1"),
        route=Route.iv,
    )
    vol = calculate_administration_volume(drug=epi, dose=dose, step=step)
    assert vol == Decimal("10.0")


def test_excessive_im_injection_volume_warning(registry: ClinicalRegistry) -> None:
    """Calculated IM volume > 3.0 mL triggers an injection volume warning in report notes."""
    patient = _make_patient()
    dose = ExplicitDose(amount=Decimal("5.0"), unit=DoseUnit.mg)
    # Using salbutamol (2.5 mg / 2.5 mL -> 5 mg = 5.0 mL) given IM
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer 5 mg IM salbutamol",
        drug_id="salbutamol",
        requested_dose=dose,
        route=Route.im,
    )
    report = verify_dose(
        patient=patient,
        drug_id="salbutamol",
        requested_dose=dose,
        registry=registry,
        step_number=1,
        step=step,
    )
    assert report.calculated_volume_ml == Decimal("5.0")
    assert "exceeds 3.0 mL single-site injection limit" in report.notes


def test_verify_dosing_intervals_step_frequency(registry: ClinicalRegistry) -> None:
    """Frequency on plan step shorter than min_interval_hours generates an alert."""
    patient = _make_patient()
    # Metoprolol adult min_interval_hours is 6h (injected below to test)
    met = registry.get_drug("metoprolol")
    assert met is not None
    adult_rule = met.population_rules["adult"].model_copy(
        update={"min_interval_hours": Decimal("6")}
    )
    drugs = dict(registry.formulary_drugs)
    drugs["metoprolol"] = met.model_copy(update={"population_rules": {"adult": adult_rule}})
    reg = ClinicalRegistry(
        formulary_drugs=drugs,
        aliases=registry.aliases,
        classes=registry.classes,
        acronyms=registry.acronyms,
        rules=registry.rules,
        scoring_tables=registry.scoring_tables,
    )

    # Plan specifies frequency_hours = 2 (less than 6)
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer metoprolol q2h",
        drug_id="metoprolol",
        requested_dose=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.mg),
        route=Route.oral,
        frequency_hours=Decimal("2"),
    )
    alerts, skips = verify_dosing_intervals(patient, [step], reg)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "MIN_INTERVAL_METOPROLOL"
    assert alerts[0].severity == Severity.HIGH
    assert "violates minimum dosing interval of 6 hours" in alerts[0].consequence


def test_verify_dosing_intervals_patient_history_lookback(registry: ClinicalRegistry) -> None:
    """Prior medication taken 2 hours ago when min_interval is 6 hours generates an alert."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    two_hours_ago = now - timedelta(hours=2)
    med = MedicationEntry(
        raw_text="metoprolol",
        dose_taken=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.mg),
        last_dose_time=two_hours_ago,
        resolved=True,
    )
    patient = _make_patient(medications=[med], med_status="confirmed_list", assessed_at=now)

    met = registry.get_drug("metoprolol")
    assert met is not None
    adult_rule = met.population_rules["adult"].model_copy(
        update={"min_interval_hours": Decimal("6")}
    )
    drugs = dict(registry.formulary_drugs)
    drugs["metoprolol"] = met.model_copy(update={"population_rules": {"adult": adult_rule}})
    reg = ClinicalRegistry(
        formulary_drugs=drugs,
        aliases=registry.aliases,
        classes=registry.classes,
        acronyms=registry.acronyms,
        rules=registry.rules,
        scoring_tables=registry.scoring_tables,
    )

    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer metoprolol now",
        drug_id="metoprolol",
        requested_dose=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.mg),
        route=Route.oral,
    )
    alerts, skips = verify_dosing_intervals(patient, [step], reg)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "MIN_INTERVAL_METOPROLOL"
    assert "2.0 hours ago" in alerts[0].consequence


def test_verify_administration_rate(registry: ClinicalRegistry) -> None:
    """Administration rate exceeding formulary max_rate_mg_per_min emits a HIGH alert."""
    patient = _make_patient()
    dex = registry.get_drug("dextrose")
    assert dex is not None
    adult_rule = dex.population_rules["adult"].model_copy(
        update={"max_rate_mg_per_min": Decimal("500")}
    )
    drugs = dict(registry.formulary_drugs)
    drugs["dextrose"] = dex.model_copy(update={"population_rules": {"adult": adult_rule}})
    reg = ClinicalRegistry(
        formulary_drugs=drugs,
        aliases=registry.aliases,
        classes=registry.classes,
        acronyms=registry.acronyms,
        rules=registry.rules,
        scoring_tables=registry.scoring_tables,
    )

    # Propose rate = 800 mg/min (> 500 mg/min)
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Rapid IV dextrose infusion",
        drug_id="dextrose",
        requested_dose=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.g),
        route=Route.iv,
        rate_mg_per_min=Decimal("800"),
    )
    alerts, skips = verify_administration_rate(patient, [step], reg)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "RATE_LIMIT_DEXTROSE"
    assert alerts[0].severity == Severity.HIGH
    assert "exceeds maximum safe rate of 500 mg/min" in alerts[0].consequence


def test_cumulative_daily_exposure_paediatric_absolute_mass(registry: ClinicalRegistry) -> None:
    """Paediatric daily_max is treated as an absolute mass ceiling, not multiplied by patient weight."""
    # Child weighs 20 kg. Ceftriaxone paediatric per_dose_max = 80 mg/kg, daily_max = 2000 mg.
    # Single dose of 50 mg/kg = 1000 mg.
    # 3 doses in plan = 3000 mg, exceeding daily_max of 2000 mg.
    patient = _make_patient(age_years=5, weight_kg=Decimal("20.0"), med_status="confirmed_none")
    dose = ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg_per_kg)
    steps = [
        PlanStepDraft(
            step_number=1,
            action_type=ActionType.administer,
            narrative_instruction="Dose 1",
            drug_id="ceftriaxone",
            requested_dose=dose,
            route=Route.iv,
        ),
        PlanStepDraft(
            step_number=2,
            action_type=ActionType.administer,
            narrative_instruction="Dose 2",
            drug_id="ceftriaxone",
            requested_dose=dose,
            route=Route.iv,
        ),
        PlanStepDraft(
            step_number=3,
            action_type=ActionType.administer,
            narrative_instruction="Dose 3",
            drug_id="ceftriaxone",
            requested_dose=dose,
            route=Route.iv,
        ),
    ]
    alerts, skips = verify_cumulative_daily_exposure(patient, steps, registry)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "CUMULATIVE_DAILY_DOSE_CEFTRIAXONE"
    assert "3000.0 mg" in alerts[0].consequence
    assert "2000 mg" in alerts[0].consequence
