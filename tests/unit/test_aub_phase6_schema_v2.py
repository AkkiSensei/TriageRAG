"""Unit tests for Schema V2 & Expanded Rule Types (T6.1 / AUB-ENG-03).

Safety Properties (Rules R1, R2, R3, R12):
1. Backward compatibility: All 12 existing rules load completely unchanged.
2. New rule types:
   - condition_contraindication
   - lab_interlock
   - route_concentration
   - organ_function
   - co_administration
   - rate_limit
3. Structured patient extensions:
   - conditions: dict[str, Literal["yes", "no", "unknown"]]
   - labs: dict[str, Measured[Decimal]]
   - gestation_weeks, lactating
4. Fail-closed on indeterminate:
   Missing or unknown conditions/labs result in SkippedCheck (UNVERIFIED), never silent bypass.
5. Isolation goldens: Demonstrated with only_rules harness.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import TypeAdapter

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    ActionType,
    Consciousness,
    ContentOrigin,
    Route,
    RuleStatus,
    Severity,
    SourceStatus,
)
from triagerag.contracts.rules_schema import (
    BaseRule,
    ClinicalRule,
    CoAdministrationRule,
    ConditionContraindicationRule,
    LabInterlockRule,
    OrganFunctionRule,
    RateLimitRule,
    RouteConcentrationRule,
)
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    MedicationEntry,
    Patient,
    PlanStepDraft,
    Provenance,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry, load_registry
from triagerag.engine.rule_engine import evaluate_baseline, evaluate_plan
from triagerag.normalize.yaml_loader import load_yaml_decimal


@pytest.fixture(scope="module")
def base_registry() -> ClinicalRegistry:
    return load_registry()


def _build_test_patient(
    *,
    conditions: dict[str, Literal["yes", "no", "unknown"]] | None = None,
    labs: dict[str, Measured[Decimal]] | None = None,
    medications: list[MedicationEntry] | None = None,
    renal_impairment: Literal["none", "mild", "moderate", "severe", "unknown"] = "none",
) -> Patient:
    meds = medications or []
    med_status: Literal["confirmed_none", "confirmed_list"] = (
        "confirmed_list" if len(meds) > 0 else "confirmed_none"
    )
    return Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("45"), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
            heart_rate_bpm=Measured[int](value=72, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medications=meds,
        allergies=[],
        allergy_history_status="confirmed_none",
        medication_history_status=med_status,
        renal_impairment=renal_impairment,
        suspected_syndrome="chest_pain",
        conditions=conditions or {},
        labs=labs or {},
    )


def test_existing_12_rules_load_unchanged(base_registry: ClinicalRegistry) -> None:
    """All 12 shipped rules load unchanged into Schema V2 discriminated union."""
    rules_dir = get_data_dir() / "rules"
    rule_files = list(rules_dir.glob("*.yaml"))
    assert len(rule_files) >= 5

    adapter = TypeAdapter(ClinicalRule)
    total_loaded = 0
    for f in rule_files:
        data = load_yaml_decimal(f)
        for r in data.get("rules", []):
            validated = adapter.validate_python(r)
            assert isinstance(validated, BaseRule)
            assert validated.id
            assert validated.provenance.source_status
            total_loaded += 1

    assert total_loaded == 12
    assert len(base_registry.rules) == 12


def test_condition_contraindication_rule_isolation(base_registry: ClinicalRegistry) -> None:
    """Isolation golden for condition_contraindication rule."""
    prov = Provenance(
        source_doc="TEST_SCHEMA_V2",
        section_ref="SEC_C1",
        version_or_date="2026",
        source_status=SourceStatus.REVIEWED,
        content_origin=ContentOrigin.SOURCE_EXTRACT,
        verified=True,
        reviewer="DR_CLINICIAN",
    )
    rule = ConditionContraindicationRule(
        id="RULE_BETA_BLOCKER_ASTHMA",
        type="condition_contraindication",
        class_name="BETA_BLOCKERS",
        condition="asthma",
        prohibited_status="yes",
        severity=Severity.BLOCK,
        status=RuleStatus.ACTIVE,
        consequence="Bronchospasm in asthmatic patient receiving beta blocker",
        action="Withhold non-selective beta blocker; select alternative agent",
        provenance=prov,
    )
    registry = base_registry.with_rules([rule])

    # 1. Condition Present (yes) -> BLOCK alert fires
    pat_asthma = _build_test_patient(
        conditions={"asthma": "yes"},
        medications=[MedicationEntry(raw_text="metoprolol", resolved=True)],
    )
    alerts, skips, _, _ = evaluate_baseline(pat_asthma, registry)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "RULE_BETA_BLOCKER_ASTHMA"
    assert alerts[0].severity == Severity.BLOCK
    assert len(skips) == 0

    # 2. Condition Absent (no) -> No alert fires
    pat_no_asthma = _build_test_patient(
        conditions={"asthma": "no"},
        medications=[MedicationEntry(raw_text="metoprolol", resolved=True)],
    )
    alerts_no, skips_no, _, _ = evaluate_baseline(pat_no_asthma, registry)
    assert len(alerts_no) == 0
    assert len(skips_no) == 0

    # 3. Condition Unknown/Missing -> Fails closed to SkippedCheck
    pat_unknown = _build_test_patient(
        conditions={},
        medications=[MedicationEntry(raw_text="metoprolol", resolved=True)],
    )
    alerts_unk, skips_unk, _, _ = evaluate_baseline(pat_unknown, registry)
    assert len(alerts_unk) == 0
    assert len(skips_unk) == 1
    assert skips_unk[0].rule_id == "RULE_BETA_BLOCKER_ASTHMA"
    assert "conditions.asthma" in skips_unk[0].missing_fields


def test_lab_interlock_rule_isolation(base_registry: ClinicalRegistry) -> None:
    """Isolation golden for lab_interlock rule."""
    prov = Provenance(
        source_doc="TEST_SCHEMA_V2",
        section_ref="SEC_L1",
        version_or_date="2026",
        source_status=SourceStatus.REVIEWED,
        content_origin=ContentOrigin.SOURCE_EXTRACT,
        verified=True,
        reviewer="DR_CLINICIAN",
    )
    rule = LabInterlockRule(
        id="RULE_ACEI_HYPERKALEMIA",
        type="lab_interlock",
        drug_id="lisinopril",
        lab_name="potassium_mmol_l",
        operator="gt",
        threshold_value=Decimal("5.5"),
        unit="mmol/L",
        severity=Severity.HIGH,
        status=RuleStatus.ACTIVE,
        consequence="Severe life-threatening hyperkalemia with ACE inhibitor",
        action="Withhold ACE inhibitor until serum potassium normalized",
        provenance=prov,
    )
    registry = base_registry.with_rules([rule])

    # 1. Lab above threshold (5.8 > 5.5) -> Alert fires
    pat_high_k = _build_test_patient(
        labs={"potassium_mmol_l": Measured[Decimal](value=Decimal("5.8"), source="measured")},
        medications=[MedicationEntry(raw_text="lisinopril", resolved=True)],
    )
    alerts, skips, _, _ = evaluate_baseline(pat_high_k, registry)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "RULE_ACEI_HYPERKALEMIA"
    assert alerts[0].severity == Severity.HIGH

    # 2. Lab below threshold (4.2 <= 5.5) -> No alert fires
    pat_normal_k = _build_test_patient(
        labs={"potassium_mmol_l": Measured[Decimal](value=Decimal("4.2"), source="measured")},
        medications=[MedicationEntry(raw_text="lisinopril", resolved=True)],
    )
    alerts_norm, skips_norm, _, _ = evaluate_baseline(pat_normal_k, registry)
    assert len(alerts_norm) == 0
    assert len(skips_norm) == 0

    # 3. Lab unmeasured -> SkippedCheck (fail-closed)
    pat_no_k = _build_test_patient(
        labs={},
        medications=[MedicationEntry(raw_text="lisinopril", resolved=True)],
    )
    alerts_unk, skips_unk, _, _ = evaluate_baseline(pat_no_k, registry)
    assert len(alerts_unk) == 0
    assert len(skips_unk) == 1
    assert "labs.potassium_mmol_l" in skips_unk[0].missing_fields


def test_organ_function_rule_isolation(base_registry: ClinicalRegistry) -> None:
    """Isolation test for organ_function rule."""
    prov = Provenance(
        source_doc="TEST_SCHEMA_V2",
        section_ref="SEC_O1",
        version_or_date="2026",
        source_status=SourceStatus.REVIEWED,
        content_origin=ContentOrigin.SOURCE_EXTRACT,
        verified=True,
        reviewer="DR_CLINICIAN",
    )
    rule = OrganFunctionRule(
        id="RULE_METFORMIN_SEVERE_RENAL",
        type="organ_function",
        drug_id="metformin",
        organ="renal",
        max_stage_allowed="mild",
        egfr_cutoff_ml_min=Decimal("30"),
        severity=Severity.BLOCK,
        status=RuleStatus.ACTIVE,
        consequence="Lactic acidosis risk in severe renal impairment",
        action="Contraindicated in severe renal impairment",
        provenance=prov,
    )
    registry = base_registry.with_rules([rule])

    pat_severe = _build_test_patient(
        renal_impairment="severe",
        medications=[MedicationEntry(raw_text="metformin", resolved=True)],
    )
    alerts, skips, _, _ = evaluate_baseline(pat_severe, registry)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "RULE_METFORMIN_SEVERE_RENAL"
    assert alerts[0].severity == Severity.BLOCK


def test_route_concentration_and_rate_limit_rules(base_registry: ClinicalRegistry) -> None:
    """Test route_concentration and rate_limit in plan evaluation."""
    prov = Provenance(
        source_doc="TEST_SCHEMA_V2",
        section_ref="SEC_R1",
        version_or_date="2026",
        source_status=SourceStatus.REVIEWED,
        content_origin=ContentOrigin.SOURCE_EXTRACT,
        verified=True,
        reviewer="DR_CLINICIAN",
    )
    r_conc = RouteConcentrationRule(
        id="RULE_POTASSIUM_CONCENTRATION_CAP",
        type="route_concentration",
        drug_id="potassium_chloride",
        max_concentration_mg_per_ml=Decimal("40.0"),
        allowed_routes=[Route.iv],
        severity=Severity.BLOCK,
        status=RuleStatus.ACTIVE,
        consequence="Severe peripheral phlebitis / arrhythmia from high potassium concentration",
        action="Dilute to safe concentration",
        provenance=prov,
    )
    r_rate = RateLimitRule(
        id="RULE_PHENYTOIN_RATE_CAP",
        type="rate_limit",
        drug_id="phenytoin",
        max_rate_mg_per_min=Decimal("50.0"),
        route=Route.iv,
        severity=Severity.HIGH,
        status=RuleStatus.ACTIVE,
        consequence="Hypotension and cardiac arrest from rapid IV phenytoin infusion",
        action="Infuse at rate not exceeding 50 mg/min",
        provenance=prov,
    )
    registry = base_registry.with_rules([r_conc, r_rate])
    patient = _build_test_patient()

    # Step exceeding concentration limit
    step_conc = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="potassium_chloride",
        route=Route.iv,
        narrative_instruction="Administer IV potassium chloride concentrated",
        concentration_mg_per_ml=Decimal("60.0"),
    )
    # Step exceeding rate limit
    step_rate = PlanStepDraft(
        step_number=2,
        action_type=ActionType.administer,
        drug_id="phenytoin",
        route=Route.iv,
        narrative_instruction="Administer IV phenytoin infusion",
        rate_mg_per_min=Decimal("80.0"),
    )

    alerts, skips, _ = evaluate_plan(patient, [step_conc, step_rate], [], registry)
    fired_ids = {a.rule_id for a in alerts}
    assert "RULE_POTASSIUM_CONCENTRATION_CAP" in fired_ids
    assert "RULE_PHENYTOIN_RATE_CAP" in fired_ids
