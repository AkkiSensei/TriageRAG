"""Unit tests for the core clinical engine components.

Safety Property:
Verifies deterministic verdict lattice resolution (all 8 combinations),
fail-closed early warning scoring (including 'C' for confusion and missing vitals),
pure decimal dose verification with magnitude tripwires, and withhold semantics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.config import get_repo_root
from triagerag.contracts.enums import (
    ActionType,
    Consciousness,
    DoseUnit,
    ScoreBand,
    Verdict,
)
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    Patient,
    PlanStepDraft,
    SpanCitation,
    Vitals,
)
from triagerag.engine.dose_engine import verify_dose
from triagerag.engine.registry import ClinicalRegistry
from triagerag.engine.rule_engine import evaluate_baseline, evaluate_plan
from triagerag.engine.scores import calculate_early_warning_score
from triagerag.engine.verdict import resolve_verdict
from triagerag.normalize.validators import normalize_patient


def test_verdict_lattice_all_eight_combinations() -> None:
    """Exhaustively verify all 2^3 = 8 combinations of the 4-state verdict lattice:

    BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.
    """
    # 1. False, False, False -> CHECKED_CLEAR
    assert (
        resolve_verdict(has_block=False, has_skip_or_unresolved=False, has_alert=False)
        == Verdict.CHECKED_CLEAR
    )

    # 2. False, False, True -> CHECKED_ALERTS
    assert (
        resolve_verdict(has_block=False, has_skip_or_unresolved=False, has_alert=True)
        == Verdict.CHECKED_ALERTS
    )

    # 3. False, True, False -> UNVERIFIED
    assert (
        resolve_verdict(has_block=False, has_skip_or_unresolved=True, has_alert=False)
        == Verdict.UNVERIFIED
    )

    # 4. False, True, True -> UNVERIFIED
    assert (
        resolve_verdict(has_block=False, has_skip_or_unresolved=True, has_alert=True)
        == Verdict.UNVERIFIED
    )

    # 5. True, False, False -> BLOCKED
    assert (
        resolve_verdict(has_block=True, has_skip_or_unresolved=False, has_alert=False)
        == Verdict.BLOCKED
    )

    # 6. True, False, True -> BLOCKED
    assert (
        resolve_verdict(has_block=True, has_skip_or_unresolved=False, has_alert=True)
        == Verdict.BLOCKED
    )

    # 7. True, True, False -> BLOCKED
    assert (
        resolve_verdict(has_block=True, has_skip_or_unresolved=True, has_alert=False)
        == Verdict.BLOCKED
    )

    # 8. True, True, True -> BLOCKED
    assert (
        resolve_verdict(has_block=True, has_skip_or_unresolved=True, has_alert=True)
        == Verdict.BLOCKED
    )


def test_early_warning_scores_normal_adult() -> None:
    """Normal vitals should yield score 0 and GREEN band."""
    repo_root = get_repo_root()
    registry = ClinicalRegistry.load_from_directory(repo_root / "data")

    normal_vitals = Vitals(
        heart_rate_bpm=Measured[int](value=72, source="measured"),
        systolic_bp_mmhg=Measured[int](value=120, source="measured"),
        respiratory_rate_bpm=Measured[int](value=14, source="measured"),
        spo2_percent=Measured[int](value=98, source="measured"),
        supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
        temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
        consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
    )
    patient = Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("35"), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=normal_vitals,
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
    )

    table = registry.scoring_tables["adult"]
    res = calculate_early_warning_score(patient, table)
    assert res.total_score == 0
    assert res.band == ScoreBand.GREEN
    assert res.missing_vitals == []


def test_early_warning_scores_confusion_distinct() -> None:
    """Consciousness C (New Confusion) must score 3 points per NEWS2 specification."""
    repo_root = get_repo_root()
    registry = ClinicalRegistry.load_from_directory(repo_root / "data")

    confused_vitals = Vitals(
        heart_rate_bpm=Measured[int](value=72, source="measured"),
        systolic_bp_mmhg=Measured[int](value=120, source="measured"),
        respiratory_rate_bpm=Measured[int](value=14, source="measured"),
        spo2_percent=Measured[int](value=98, source="measured"),
        supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
        temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
        consciousness=Measured[Consciousness](value=Consciousness.C, source="measured"),
    )
    patient = Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("35"), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=confused_vitals,
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
    )

    table = registry.scoring_tables["adult"]
    res = calculate_early_warning_score(patient, table)
    assert res.total_score is not None and res.total_score >= 3
    assert res.subscores.get("consciousness") == 3


def test_early_warning_scores_fail_closed_on_missing_vitals() -> None:
    """Missing vitals must NOT default to normal and must yield UNSCORED."""
    repo_root = get_repo_root()
    registry = ClinicalRegistry.load_from_directory(repo_root / "data")

    # Missing heart_rate and sbp
    incomplete_vitals = Vitals(
        respiratory_rate_bpm=Measured[int](value=16, source="measured"),
        spo2_percent=Measured[int](value=98, source="measured"),
        supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
    )
    patient = Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("35"), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=incomplete_vitals,
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
    )

    table = registry.scoring_tables["adult"]
    res = calculate_early_warning_score(patient, table)
    assert res.total_score is None
    assert res.band == ScoreBand.UNSCORED
    assert "heart_rate_bpm" in res.missing_vitals
    assert "systolic_bp_mmhg" in res.missing_vitals


def test_dose_engine_magnitude_tripwires() -> None:
    """10x and 0.1x deviations from reference dose must trip magnitude tripwire."""
    from triagerag.contracts.data_schemas import FormularyDrug
    from triagerag.normalize.yaml_loader import load_yaml_decimal

    repo_root = get_repo_root()
    base_registry = ClinicalRegistry.load_from_directory(repo_root / "data")
    fict_drugs_data = load_yaml_decimal(
        repo_root / "tests" / "fixtures" / "mechanics" / "drugs.yaml"
    )
    zorapine_drug = FormularyDrug.model_validate(fict_drugs_data["drugs"]["zorapine"])
    registry = ClinicalRegistry(
        formulary_drugs={**base_registry.formulary_drugs, "zorapine": zorapine_drug},
        aliases=base_registry.aliases,
        classes=base_registry.classes,
        acronyms=base_registry.acronyms,
        rules=base_registry.rules,
        scoring_tables=base_registry.scoring_tables,
    )

    patient = Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("40"), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=Vitals(),
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
    )

    # Reference adult zorapine dose max is 50 mg
    # 600.0 mg is >= 10x reference -> tripwire
    rep_high = verify_dose(
        patient=patient,
        drug_id="zorapine",
        requested_dose=ExplicitDose(amount=Decimal("600.0"), unit=DoseUnit.mg),
        registry=registry,
    )
    assert rep_high.magnitude_tripwire_triggered is True

    # 1.0 mg is <= 0.1x reference (5.0 mg) -> tripwire
    rep_low = verify_dose(
        patient=patient,
        drug_id="zorapine",
        requested_dose=ExplicitDose(amount=Decimal("1.0"), unit=DoseUnit.mg),
        registry=registry,
    )
    assert rep_low.magnitude_tripwire_triggered is True


def test_withhold_semantics_never_treated_as_administration() -> None:
    """Withholding a blocked drug must never trigger an administration alert."""
    repo_root = get_repo_root()
    registry = ClinicalRegistry.load_from_directory(repo_root / "data")

    # Patient with SBP 80 (nitroglycerin is contraindicated due to vitals)
    vitals = Vitals(
        systolic_bp_mmhg=Measured[int](value=80, source="measured"),
    )
    raw_patient = Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("55"), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=vitals,
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
    )
    patient = normalize_patient(raw_patient, registry.resolver)

    # Proposed step: WITHHOLD nitroglycerin
    withhold_step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.withhold,
        narrative_instruction="Withhold nitroglycerin due to severe hypotension",
        drug_id="nitroglycerin",
        citations=[
            SpanCitation(
                doc_id="PROTO_ACS_SYNTHETIC",
                section="1",
                chunk_id="chunk_acs_01",
                quoted_span="Withhold nitrates if systolic BP < 90 mmHg",
            )
        ],
    )

    baseline_alerts, baseline_skips, _, _ = evaluate_baseline(patient, registry)
    plan_alerts, plan_skips, dose_reports = evaluate_plan(
        patient=patient,
        steps=[withhold_step],
        baseline_alerts=baseline_alerts,
        registry=registry,
    )

    # Dose reports must be empty for withhold
    assert dose_reports == []
    # No new plan alerts should fire because withhold is NOT administration
    assert plan_alerts == []
