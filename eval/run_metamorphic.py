"""Metamorphic testing suite for TriageRAG.

Safety Property:
Asserts invariant clinical behaviors under semantic-preserving transformations:
1. Brand <-> Generic equivalence yields identical verdicts and alerts.
2. Entity list reordering yields stable, identical alerts and verdicts.
3. Unit conversions (e.g., 0.5 mg vs 500 mcg) produce equivalent dose clearance.
4. Magnitude shifts (10x, 1000x) reliably trip safety tripwires.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AgeUnit,
    Consciousness,
    DoseUnit,
    Route,
    Verdict,
)
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    ExplicitDose,
    Measured,
    MedicationEntry,
    Patient,
    Vitals,
)
from triagerag.engine.dose_engine import check_magnitude_tripwire
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols


def _create_base_patient(now: datetime) -> Patient:
    return Patient(
        assessed_at=now,
        age=Age(value=Decimal("50"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=80, source="measured"),
            systolic_bp_mmhg=Measured[int](value=125, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=80, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_none",
        medications=[],
        allergy_history_status="confirmed_nkda",
        allergies=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome="chest_pain",
        chief_complaint_untrusted="Chest discomfort",
    )


def test_brand_generic_equivalence(registry: ClinicalRegistry, index: BM25ClinicalIndex) -> bool:
    """Transformation: Replace brand 'Viagra' with generic 'sildenafil'."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    llm = FakeLLM(profile=FakeLLMProfile.COMPLIANT)

    # 1. Brand: Viagra
    p_brand = _create_base_patient(now)
    p_brand.medication_history_status = "confirmed_list"
    p_brand.medications = [
        MedicationEntry(
            raw_text="Viagra",
            dose_taken=ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg),
            route=Route.oral,
            last_dose_time=now - timedelta(hours=6),
        )
    ]
    resp_brand = run_triage(patient=p_brand, registry=registry, llm=llm, index=index)

    # 2. Generic: sildenafil
    p_generic = _create_base_patient(now)
    p_generic.medication_history_status = "confirmed_list"
    p_generic.medications = [
        MedicationEntry(
            raw_text="sildenafil",
            dose_taken=ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg),
            route=Route.oral,
            last_dose_time=now - timedelta(hours=6),
        )
    ]
    resp_generic = run_triage(patient=p_generic, registry=registry, llm=llm, index=index)

    # Both must yield BLOCKED with same triggered rules
    assert resp_brand.engine.verdict == Verdict.BLOCKED
    assert resp_generic.engine.verdict == Verdict.BLOCKED

    brand_rules = sorted(
        a.rule_id for a in resp_brand.engine.baseline_alerts + resp_brand.engine.plan_alerts
    )
    generic_rules = sorted(
        a.rule_id for a in resp_generic.engine.baseline_alerts + resp_generic.engine.plan_alerts
    )
    assert brand_rules == generic_rules
    return True


def test_list_reordering_invariance(registry: ClinicalRegistry, index: BM25ClinicalIndex) -> bool:
    """Transformation: Permute allergy entries list order."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    llm = FakeLLM(profile=FakeLLMProfile.COMPLIANT)

    entry1 = AllergyEntry(raw_substance="penicillin", reaction_type="mild_rash")
    entry2 = AllergyEntry(raw_substance="amoxicillin", reaction_type="anaphylaxis_ige")

    p1 = _create_base_patient(now)
    p1.allergy_history_status = "confirmed_list"
    p1.allergies = [entry1, entry2]
    resp1 = run_triage(patient=p1, registry=registry, llm=llm, index=index)

    p2 = _create_base_patient(now)
    p2.allergy_history_status = "confirmed_list"
    p2.allergies = [entry2, entry1]
    resp2 = run_triage(patient=p2, registry=registry, llm=llm, index=index)

    # Invariant: identical verdict, identical sorted alert IDs
    assert resp1.engine.verdict == resp2.engine.verdict
    alerts1 = sorted(a.rule_id for a in resp1.engine.baseline_alerts)
    alerts2 = sorted(a.rule_id for a in resp2.engine.baseline_alerts)
    assert alerts1 == alerts2
    return True


def test_equivalent_units_tripwire() -> bool:
    """Transformation: 0.5 mg vs 500 mcg reference comparison."""
    from triagerag.normalize.units import convert_dose

    # Convert 500 mcg to mg
    dose_mcg = ExplicitDose(amount=Decimal("500"), unit=DoseUnit.mcg)
    dose_mg = convert_dose(dose_mcg, DoseUnit.mg)
    assert dose_mg.amount == Decimal("0.5")

    # Reference: 0.5 mg. Safe dose (tripwire NOT triggered):
    assert not check_magnitude_tripwire(Decimal("0.5"), Decimal("0.5"))

    # 1000x excessive magnitude: 500.0 mg vs reference 0.5 mg (tripwire triggered):
    assert check_magnitude_tripwire(Decimal("500.0"), Decimal("0.5"))

    # Sub-therapeutic 0.01x magnitude: 0.005 mg vs reference 0.5 mg (tripwire triggered):
    assert check_magnitude_tripwire(Decimal("0.005"), Decimal("0.5"))
    return True


def run_metamorphic_suite() -> tuple[bool, int, int]:
    """Execute all metamorphic test transformations."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    chunks = ingest_protocols(data_dir)
    index = BM25ClinicalIndex(chunks)

    tests = [
        ("brand_generic_equivalence", test_brand_generic_equivalence),
        ("list_reordering_invariance", test_list_reordering_invariance),
        ("equivalent_units_tripwire", lambda reg, idx: test_equivalent_units_tripwire()),
    ]

    passed = 0
    total = len(tests)

    print(f"Executing Metamorphic Testing Suite ({total} transformations)...")
    for name, test_func in tests:
        try:
            ok = test_func(registry, index)
            if ok:
                passed += 1
                print(f"  [PASS] {name}")
            else:
                print(f"  [FAIL] {name}")
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    success = passed == total
    reports_dir = data_dir.parent / "eval" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_json = {
        "suite": "metamorphic",
        "passed": passed,
        "total": total,
        "score": round((passed / total) * 100.0, 1) if total else 0.0,
        "status": "PASS" if success else "FAIL",
        "transformations": [name for name, _ in tests],
    }
    import json

    (reports_dir / "metamorphic.json").write_text(
        json.dumps(report_json, indent=2), encoding="utf-8"
    )

    return success, passed, total


if __name__ == "__main__":
    success, passed, total = run_metamorphic_suite()
    if not success:
        sys.exit(1)
    print(f"\nMetamorphic Suite Results: {passed}/{total} passed.")
