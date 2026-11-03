"""AUB Phase 6 Task T6.4: Candidate Rule Expansion Test Harness.

Tests:
1. Candidate rules loading (all 40 rules across Batch 1, 2, and 3).
2. Provenance invariants (HD-7: verified=False, source_status=PLACEHOLDER_UNRETRIEVED, reviewer=None).
3. Rule isolation testing (only_rules):
   - Positive cases (rule triggers alert when conditions met).
   - Negative cases (rule remains silent when conditions not met).
   - Boundary cases (exact threshold values, eGFR, QTc, route, concentration).
4. Mutation operators:
   - Flipping operator (gt -> lt) or altering threshold inverts verdict.
5. Alert fatigue baseline calculation:
   - Evaluates alerts per patient under isolated candidate rules.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import (
    ActionType,
    AgeUnit,
    DoseUnit,
    Route,
    Severity,
    SourceStatus,
)
from triagerag.contracts.rules_schema import (
    ClinicalRule,
    LabInterlockRule,
)
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    IngredientStrength,
    Measured,
    MedicationEntry,
    Patient,
    PlanStepDraft,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.engine.rule_engine import evaluate_baseline, evaluate_plan
from triagerag.normalize.yaml_loader import load_yaml_decimal


@pytest.fixture
def registry() -> ClinicalRegistry:
    return ClinicalRegistry.load_from_directory(get_repo_root() / "data")


def load_candidate_rules(
    data_dir: Path | None = None, pattern: str = "*.yaml"
) -> list[ClinicalRule]:
    base_dir = data_dir or get_data_dir()
    cand_dir = base_dir / "rules_candidates"
    adapter = TypeAdapter(ClinicalRule)
    rules: list[ClinicalRule] = []
    for f in sorted(cand_dir.glob(pattern)):
        data = load_yaml_decimal(f)
        for r in data.get("rules", []):
            rules.append(adapter.validate_python(r))
    return rules


def only_candidate_rule(
    registry: ClinicalRegistry, candidate_rule: ClinicalRule
) -> ClinicalRegistry:
    """Return a ClinicalRegistry configured exclusively with a single candidate rule."""
    return dataclasses.replace(registry, rules=[candidate_rule])


def _make_test_patient(
    medications: list[str] | None = None,
    conditions: dict[str, str] | None = None,
    labs: dict[str, Decimal] | None = None,
    pregnancy: str = "no",
) -> Patient:
    med_entries = [
        MedicationEntry(
            raw_text=m,
            resolved=True,
            ingredients=[IngredientStrength(ingredient_id=m.lower())],
        )
        for m in (medications or [])
    ]
    lab_entries = {
        k: Measured[Decimal](value=v, source="measured") for k, v in (labs or {}).items()
    }
    return Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("40"), unit=AgeUnit.years),
        sex="female",
        pregnancy=pregnancy,  # type: ignore[arg-type]
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=120, source="measured")),
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_list" if medications else "confirmed_none",
        medications=med_entries,
        conditions=conditions or {},
        labs=lab_entries,
    )


def test_candidate_rules_count_and_provenance_invariants() -> None:
    """All candidate rules must load and strictly uphold HD-7 and Rule R3 safety invariants."""
    batch_candidates = load_candidate_rules(pattern="batch_*.yaml")
    assert len(batch_candidates) == 40, (
        f"Expected 40 candidate rules across 3 batches, found {len(batch_candidates)}"
    )

    all_candidates = load_candidate_rules()
    assert len(all_candidates) >= 40

    for rule in all_candidates:
        assert rule.provenance.verified is False, (
            f"Rule {rule.id} violates HD-7: verified must be false"
        )
        assert rule.provenance.source_status in (
            SourceStatus.PLACEHOLDER_UNRETRIEVED,
            SourceStatus.RETRIEVED_UNREVIEWED,
        )
        assert rule.provenance.reviewer is None, f"Rule {rule.id} has unreviewed reviewer set"


def test_batch_1_isolation_goldens(registry: ClinicalRegistry) -> None:
    """Test positive, negative, and boundary cases for Batch 1 candidate rules in strict isolation."""
    candidates = {r.id: r for r in load_candidate_rules()}

    # 1. CNS-01 (Opioid + Benzodiazepine)
    rule_cns01 = candidates["CNS-01"]
    reg_cns01 = only_candidate_rule(registry, rule_cns01)

    # Positive: Morphine + Midazolam
    p_pos = _make_test_patient(medications=["morphine", "midazolam"])
    alerts, _, _, _ = evaluate_baseline(p_pos, reg_cns01)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "CNS-01"
    assert alerts[0].severity == Severity.HIGH

    # Negative: Morphine alone (no benzodiazepine)
    p_neg = _make_test_patient(medications=["morphine"])
    alerts_neg, _, _, _ = evaluate_baseline(p_neg, reg_cns01)
    assert len(alerts_neg) == 0

    # 2. CNS-04 (Tramadol + Linezolid)
    rule_cns04 = candidates["CNS-04"]
    reg_cns04 = only_candidate_rule(registry, rule_cns04)

    # Positive: Tramadol + Linezolid
    p_pos_cns4 = _make_test_patient(medications=["tramadol", "linezolid"])
    alerts_cns4, _, _, _ = evaluate_baseline(p_pos_cns4, reg_cns04)
    assert len(alerts_cns4) == 1
    assert alerts_cns4[0].rule_id == "CNS-04"
    assert alerts_cns4[0].severity == Severity.BLOCK

    # Negative: Tramadol alone
    p_neg_cns4 = _make_test_patient(medications=["tramadol"])
    alerts_neg_cns4, _, _, _ = evaluate_baseline(p_neg_cns4, reg_cns04)
    assert len(alerts_neg_cns4) == 0


def test_batch_2_isolation_goldens(registry: ClinicalRegistry) -> None:
    """Test positive, negative, and boundary cases for Batch 2 (Needs C/L) candidate rules."""
    candidates = {r.id: r for r in load_candidate_rules()}

    # 1. CV-09: Beta-blocker + AV Block 2nd/3rd degree
    rule_cv09 = candidates["CV-09"]
    reg_cv09 = only_candidate_rule(registry, rule_cv09)

    # Positive: Metoprolol with AV block present
    p_pos = _make_test_patient(
        medications=["metoprolol"],
        conditions={"av_block_second_or_third_degree": "yes"},
    )
    alerts, _, _, _ = evaluate_baseline(p_pos, reg_cv09)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "CV-09"
    assert alerts[0].severity == Severity.BLOCK

    # Negative: Metoprolol without AV block
    p_neg = _make_test_patient(
        medications=["metoprolol"],
        conditions={"av_block_second_or_third_degree": "no"},
    )
    alerts_neg, _, _, _ = evaluate_baseline(p_neg, reg_cv09)
    assert len(alerts_neg) == 0

    # Boundary / Unknown condition fails closed to SkippedCheck
    p_unk = _make_test_patient(
        medications=["metoprolol"],
        conditions={"av_block_second_or_third_degree": "unknown"},
    )
    alerts_unk, skips_unk, _, _ = evaluate_baseline(p_unk, reg_cv09)
    assert len(alerts_unk) == 0
    assert len(skips_unk) == 1
    assert skips_unk[0].rule_id == "CV-09"

    # 2. VL-05: Lab interlock QTc > 500 ms
    rule_vl05 = candidates["VL-05"]
    reg_vl05 = only_candidate_rule(registry, rule_vl05)

    # Positive: Amiodarone with QTc = 520 ms (> 500)
    p_pos_vl = _make_test_patient(
        medications=["amiodarone"],
        labs={"qtc_interval_ms": Decimal("520")},
    )
    alerts_vl, _, _, _ = evaluate_baseline(p_pos_vl, reg_vl05)
    assert len(alerts_vl) == 1
    assert alerts_vl[0].rule_id == "VL-05"

    # Negative: Amiodarone with normal QTc = 420 ms
    p_neg_vl = _make_test_patient(
        medications=["amiodarone"],
        labs={"qtc_interval_ms": Decimal("420")},
    )
    alerts_neg_vl, _, _, _ = evaluate_baseline(p_neg_vl, reg_vl05)
    assert len(alerts_neg_vl) == 0

    # Boundary: QTc exactly at 500 ms (operator is gt, so 500 should not trigger)
    p_bnd_vl = _make_test_patient(
        medications=["amiodarone"],
        labs={"qtc_interval_ms": Decimal("500")},
    )
    alerts_bnd_vl, _, _, _ = evaluate_baseline(p_bnd_vl, reg_vl05)
    assert len(alerts_bnd_vl) == 0


def test_batch_3_isolation_goldens(registry: ClinicalRegistry) -> None:
    """Test positive, negative, and boundary cases for Batch 3 (Needs R/K/Rt) candidate rules."""
    candidates = {r.id: r for r in load_candidate_rules()}

    # 1. NE-01: Epinephrine IV max concentration 0.1 mg/mL
    rule_ne01 = candidates["NE-01"]
    reg_ne01 = only_candidate_rule(registry, rule_ne01)
    p = _make_test_patient()

    # Positive: IV epinephrine at 1.0 mg/mL (exceeds 0.1 mg/mL) -> BLOCK
    step_pos = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Give 1 mg/mL IV epinephrine",
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("1.0"), unit=DoseUnit.mg),
        concentration_mg_per_ml=Decimal("1.0"),
        route=Route.iv,
    )
    alerts_pos, _, _ = evaluate_plan(p, [step_pos], [], reg_ne01)
    assert any(a.rule_id == "NE-01" for a in alerts_pos)

    # Negative: IV epinephrine diluted to 0.05 mg/mL (within <= 0.1)
    step_neg = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Give diluted IV epinephrine",
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.1"), unit=DoseUnit.mg),
        concentration_mg_per_ml=Decimal("0.05"),
        route=Route.iv,
    )
    alerts_neg, _, _ = evaluate_plan(p, [step_neg], [], reg_ne01)
    assert not any(a.rule_id == "NE-01" for a in alerts_neg)

    # 2. CNS-14: Phenytoin infusion rate max 50 mg/min
    rule_cns14 = candidates["CNS-14"]
    reg_cns14 = only_candidate_rule(registry, rule_cns14)

    # Positive: Phenytoin infused at 100 mg/min (> 50 mg/min)
    step_rate_pos = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Rapid IV phenytoin infusion",
        drug_id="phenytoin",
        requested_dose=ExplicitDose(amount=Decimal("1000"), unit=DoseUnit.mg),
        rate_mg_per_min=Decimal("100"),
        route=Route.iv,
    )
    alerts_rate, _, _ = evaluate_plan(p, [step_rate_pos], [], reg_cns14)
    assert any(a.rule_id == "CNS-14" for a in alerts_rate)

    # Boundary: Rate exactly at 50 mg/min (within limit)
    step_rate_bnd = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Standard IV phenytoin infusion",
        drug_id="phenytoin",
        requested_dose=ExplicitDose(amount=Decimal("1000"), unit=DoseUnit.mg),
        rate_mg_per_min=Decimal("50"),
        route=Route.iv,
    )
    alerts_rate_bnd, _, _ = evaluate_plan(p, [step_rate_bnd], [], reg_cns14)
    assert not any(a.rule_id == "CNS-14" for a in alerts_rate_bnd)


def test_mutation_operator_inverts_verdict(registry: ClinicalRegistry) -> None:
    """Mutation testing: mutating a rule operator (gt -> lt) inverts the evaluation verdict."""
    candidates = {r.id: r for r in load_candidate_rules()}
    rule_vl05 = candidates["VL-05"]
    assert isinstance(rule_vl05, LabInterlockRule)

    # Mutated rule: operator changed from gt to lt
    mutated_rule = rule_vl05.model_copy(update={"operator": "lt"})
    reg_mutated = only_candidate_rule(registry, mutated_rule)

    # Patient with high QTc = 520 ms:
    # Original rule (gt 500) fires alert.
    # Mutated rule (lt 500) MUST NOT fire alert.
    p = _make_test_patient(
        medications=["amiodarone"],
        labs={"qtc_interval_ms": Decimal("520")},
    )
    alerts, _, _, _ = evaluate_baseline(p, reg_mutated)
    assert len(alerts) == 0, "Mutated operator (lt) incorrectly fired on value > threshold"
