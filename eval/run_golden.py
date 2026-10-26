"""Evaluation runner for shipped ruleset golden cases.

Safety Property (Rule R10):
Asserts 100% recall on BLOCK and HIGH severity cases in the golden set.
CI fails immediately on any missed BLOCK/HIGH case.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from triagerag.config import get_data_dir
from triagerag.contracts.enums import Consciousness
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    Measured,
    MedicationEntry,
    Patient,
    Vitals,
)
from triagerag.engine.registry import load_registry
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.normalize.validators import normalize_patient
from triagerag.normalize.yaml_loader import load_yaml_decimal


def _build_patient_from_case(case: dict[str, Any], registry: Any) -> Patient:
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
        supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
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


def run_golden_suite() -> int:
    data_dir = get_data_dir()
    golden_path = data_dir / "golden" / "shipped_ruleset_cases.yaml"
    if not golden_path.exists():
        print(f"Error: Golden cases file not found at {golden_path}")
        return 1

    registry = load_registry(data_dir)
    data = load_yaml_decimal(golden_path)
    cases = data.get("cases", [])

    print(f"Executing Shipped Ruleset Golden Suite ({len(cases)} cases)...")

    passed_count = 0
    failed_cases: list[str] = []

    for case in cases:
        case_id = case["id"]
        patient = _build_patient_from_case(case, registry)
        alerts, skipped, _, _ = evaluate_baseline(patient, registry)

        fired_rule_ids = {a.rule_id for a in alerts}
        skipped_rule_ids = {s.rule_id for s in skipped}

        must_fire = set(case.get("must_fire", []))
        must_skip = set(case.get("must_skip", []))
        must_not_fire = set(case.get("must_not_fire", []))

        # Check conditions
        missed_fires = must_fire - fired_rule_ids
        missed_skips = must_skip - skipped_rule_ids
        false_fires = must_not_fire & fired_rule_ids

        if missed_fires or missed_skips or false_fires:
            err_details = []
            if missed_fires:
                err_details.append(f"Missed must_fire: {missed_fires}")
            if missed_skips:
                err_details.append(f"Missed must_skip: {missed_skips}")
            if false_fires:
                err_details.append(f"Fired prohibited must_not_fire: {false_fires}")
            failed_cases.append(f"[{case_id}] {', '.join(err_details)}")
        else:
            passed_count += 1

    print(f"\nGolden Suite Results: {passed_count}/{len(cases)} passed.")
    if failed_cases:
        print("[FAIL] Golden cases failed:")
        for fc in failed_cases:
            print(f"  - {fc}")
        return 1

    print("[OK] Golden Suite 100% green on all shipped rules.")
    return 0


if __name__ == "__main__":
    sys.exit(run_golden_suite())
