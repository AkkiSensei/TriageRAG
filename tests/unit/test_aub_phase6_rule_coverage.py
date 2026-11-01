"""Unit tests for Rule Coverage Matrix and Alert Fatigue Gate (AUB Phase 6 Task T6.5).

Safety Properties (Rule R10, AUB T6.5):
1. Asserts 100% case-kind coverage across all active shipped rules (pos >= 3, neg >= 3, bnd >= 1).
2. Verifies 0.0% false-alert rate on negative cases.
3. Computes alert fatigue (alerts per patient) to monitor alert burden.
4. Detects defect regressions when a required case kind is removed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from tools.rule_coverage import compute_rule_coverage
from triagerag.config import get_data_dir


def test_rule_coverage_all_active_rules_pass() -> None:
    """Verify that all shipped active clinical rules pass the 3-case coverage requirement."""
    metrics = compute_rule_coverage()

    assert metrics["total_active_rules"] == 12
    assert metrics["covered_active_rules"] == 12
    assert metrics["failing_rules"] == []
    assert metrics["false_alert_rate"] == 0.0
    assert metrics["candidate_rules_count"] == 40
    assert metrics["total_cases"] >= 80
    assert metrics["alerts_per_patient"] > 0.0
    assert metrics["alerts_per_patient"] < 2.0  # Safe alert fatigue upper bound


def test_rule_coverage_case_counts_per_rule() -> None:
    """Inspect each rule's specific positive, negative, and boundary counts."""
    metrics = compute_rule_coverage()
    status_map = metrics["rule_status"]

    for rule_id, rule_info in status_map.items():
        if rule_info["status"] == "NEEDS_SOURCE":
            assert rule_info["pos"] == 0, (
                f"NEEDS_SOURCE rule {rule_id} should not have positive fires"
            )
            assert rule_info["neg"] >= 3, f"NEEDS_SOURCE rule {rule_id} requires >= 3 negatives"
            assert rule_info["bnd"] >= 1, f"NEEDS_SOURCE rule {rule_id} requires >= 1 boundary"
        else:
            assert rule_info["pos"] >= 3, (
                f"Rule {rule_id} requires >= 3 positive cases, got {rule_info['pos']}"
            )
            assert rule_info["neg"] >= 3, (
                f"Rule {rule_id} requires >= 3 negative cases, got {rule_info['neg']}"
            )
            assert rule_info["bnd"] >= 1, (
                f"Rule {rule_id} requires >= 1 boundary cases, got {rule_info['bnd']}"
            )

        assert rule_info["passed"] is True, f"Rule {rule_id} marked as failed in coverage status"


def test_rule_coverage_fails_on_missing_coverage_kind() -> None:
    """Simulate a deficient golden suite and verify that the coverage gate detects the missing cases."""
    real_data_dir = get_data_dir()
    golden_path = real_data_dir / "golden" / "shipped_ruleset_cases.yaml"

    with open(golden_path, encoding="utf-8") as f:
        cases_data = yaml.safe_load(f)

    # Filter out all positive cases for DUP_PDE5_INHIBITORS
    mutated_cases = []
    for c in cases_data.get("cases", []):
        if "DUP_PDE5_INHIBITORS" in c.get("must_fire", []):
            continue
        mutated_cases.append(c)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        golden_dir = tmp_path / "golden"
        golden_dir.mkdir(parents=True)
        (golden_dir / "shipped_ruleset_cases.yaml").write_text(
            yaml.dump({"cases": mutated_cases}), encoding="utf-8"
        )

        # Copy data directories needed by load_registry
        for sub in ("rules", "formulary", "classes", "aliases", "rules_candidates", "acronyms"):
            src_sub = real_data_dir / sub
            if src_sub.is_dir():
                import shutil

                shutil.copytree(src_sub, tmp_path / sub)
            elif (real_data_dir / f"{sub}.yaml").exists():
                import shutil

                shutil.copy2(real_data_dir / f"{sub}.yaml", tmp_path / f"{sub}.yaml")

        mutated_metrics = compute_rule_coverage(data_dir=tmp_path)
        assert "DUP_PDE5_INHIBITORS" in mutated_metrics["failing_rules"]
        assert mutated_metrics["rule_status"]["DUP_PDE5_INHIBITORS"]["passed"] is False
