"""Evaluation runner for shipped ruleset golden cases.

Safety Property (Rule R10):
Asserts 100% recall on BLOCK and HIGH severity cases in the golden set.
CI fails immediately on any missed BLOCK/HIGH case.
"""

from __future__ import annotations

import sys
from typing import Any

from triagerag.config import get_data_dir
from triagerag.contracts.schemas import (
    Patient,
)
from triagerag.engine.registry import load_registry
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.normalize.validators import build_patient_from_case
from triagerag.normalize.yaml_loader import load_yaml_decimal


def _build_patient_from_case(case: dict[str, Any], registry: Any) -> Patient:
    """Delegate to centralized build_patient_from_case."""
    return build_patient_from_case(case, registry)


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
    reports_dir = data_dir.parent / "eval" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_json = {
        "suite": "golden",
        "passed": passed_count,
        "total": len(cases),
        "score": round((passed_count / len(cases)) * 100.0, 1) if cases else 0.0,
        "status": "PASS" if not failed_cases else "FAIL",
        "failed_cases": failed_cases,
    }
    import json

    (reports_dir / "golden.json").write_text(json.dumps(report_json, indent=2), encoding="utf-8")

    if failed_cases:
        print("[FAIL] Golden cases failed:")
        for fc in failed_cases:
            print(f"  - {fc}")
        return 1

    print("[OK] Golden Suite 100% green on all shipped rules.")
    return 0


if __name__ == "__main__":
    sys.exit(run_golden_suite())
