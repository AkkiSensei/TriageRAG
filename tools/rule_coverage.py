"""Rule Coverage Matrix and Alert Fatigue Gate Runner.

AUB Phase 6 Task T6.5:
Fails CI if any active rule lacks the three case kinds (positive >= 3,
negative >= 3, boundary >= 1).
Reports alerts per patient (alert fatigue metric) and false-alert rate on negatives.
"""

from __future__ import annotations

import dataclasses
import glob
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from triagerag.config import get_data_dir
from triagerag.contracts.enums import RuleStatus
from triagerag.contracts.rules_schema import ClinicalRule
from triagerag.contracts.schemas import Patient
from triagerag.engine.registry import ClinicalRegistry, load_registry
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.normalize.validators import build_patient_from_case
from triagerag.normalize.yaml_loader import load_yaml_decimal


def only_rules(reg: ClinicalRegistry, *rule_ids: str) -> ClinicalRegistry:
    """Return a ClinicalRegistry containing ONLY the named rules to prevent redundancy masking."""
    kept = [r for r in reg.rules if r.id in rule_ids]
    return dataclasses.replace(reg, rules=kept)


def compute_rule_coverage(data_dir: Path | None = None) -> dict[str, Any]:
    """Compute rule coverage matrix and alert fatigue metrics across golden cases."""
    data_dir = data_dir or get_data_dir()
    golden_path = data_dir / "golden" / "shipped_ruleset_cases.yaml"
    if not golden_path.exists():
        raise FileNotFoundError(f"Golden cases file missing at {golden_path}")

    registry = load_registry(data_dir)
    golden_data = load_yaml_decimal(golden_path)
    cases = golden_data.get("cases", [])

    # Group active rules
    active_rules: dict[str, ClinicalRule] = {r.id: r for r in registry.rules}

    # Tracking counters
    pos_cases: dict[str, list[str]] = defaultdict(list)
    neg_cases: dict[str, list[str]] = defaultdict(list)
    bnd_cases: dict[str, list[str]] = defaultdict(list)

    total_alerts_across_cases = 0
    total_negative_checks = 0
    false_alerts_on_negatives = 0

    # Execute cases
    for case in cases:
        case_id = case.get("id", "UNKNOWN")
        patient: Patient = build_patient_from_case(case, registry)
        alerts, skipped, _, _ = evaluate_baseline(patient, registry)

        fired_rule_ids = {a.rule_id for a in alerts}
        skipped_rule_ids = {s.rule_id for s in skipped}
        total_alerts_across_cases += len(alerts)

        must_fire = set(case.get("must_fire", []))
        must_skip = set(case.get("must_skip", []))
        must_not_fire = set(case.get("must_not_fire", []))

        # Check positive cases with isolation verification
        for rule_id in must_fire:
            if rule_id in active_rules and rule_id in fired_rule_ids:
                iso_reg = only_rules(registry, rule_id)
                iso_alerts, _, _, _ = evaluate_baseline(patient, iso_reg)
                if any(a.rule_id == rule_id for a in iso_alerts):
                    pos_cases[rule_id].append(case_id)

        # Check boundary/skip cases with isolation verification
        for rule_id in must_skip:
            if rule_id in active_rules and rule_id in skipped_rule_ids:
                iso_reg = only_rules(registry, rule_id)
                _, iso_skips, _, _ = evaluate_baseline(patient, iso_reg)
                if any(s.rule_id == rule_id for s in iso_skips):
                    bnd_cases[rule_id].append(case_id)

        # Check negative cases
        for rule_id in must_not_fire:
            if rule_id in active_rules:
                total_negative_checks += 1
                if rule_id in fired_rule_ids:
                    false_alerts_on_negatives += 1
                else:
                    neg_cases[rule_id].append(case_id)

    # Compute rule coverage status
    rule_status: dict[str, dict[str, Any]] = {}
    failing_rules: list[str] = []

    for rule_id, rule in active_rules.items():
        pos_cnt = len(pos_cases[rule_id])
        neg_cnt = len(neg_cases[rule_id])
        bnd_cnt = len(bnd_cases[rule_id])

        is_needs_source = rule.status == RuleStatus.NEEDS_SOURCE
        # Normal rules need >= 3 pos, >= 3 neg, >= 1 bnd
        # NEEDS_SOURCE rules need >= 3 neg, >= 1 bnd (0 pos expected)
        if is_needs_source:
            passed = (neg_cnt >= 3) and (bnd_cnt >= 1)
        else:
            passed = (pos_cnt >= 3) and (neg_cnt >= 3) and (bnd_cnt >= 1)

        if not passed:
            failing_rules.append(rule_id)

        rule_status[rule_id] = {
            "type": rule.type,
            "status": rule.status.value,
            "pos": pos_cnt,
            "neg": neg_cnt,
            "bnd": bnd_cnt,
            "passed": passed,
        }

    # Candidate rules count
    candidate_files = glob.glob(str(data_dir / "rules_candidates" / "*.yaml"))
    candidate_rules_count = 0
    for cand_file in candidate_files:
        cand_data = load_yaml_decimal(Path(cand_file))
        candidate_rules_count += len(cand_data.get("rules", []))

    total_patients = len(cases)
    alerts_per_patient = (
        round(total_alerts_across_cases / total_patients, 2) if total_patients > 0 else 0.0
    )
    false_alert_rate = (
        round((false_alerts_on_negatives / total_negative_checks) * 100.0, 2)
        if total_negative_checks > 0
        else 0.0
    )

    return {
        "rule_status": rule_status,
        "failing_rules": failing_rules,
        "total_active_rules": len(active_rules),
        "covered_active_rules": len(active_rules) - len(failing_rules),
        "total_cases": total_patients,
        "alerts_per_patient": alerts_per_patient,
        "false_alert_rate": false_alert_rate,
        "candidate_rules_count": candidate_rules_count,
    }


def main() -> int:
    """CLI entrypoint for rule coverage matrix and alert fatigue gate."""
    console = Console()
    console.print(
        "\n[bold cyan]=== TRIAGERAG RULE COVERAGE & ALERT FATIGUE GATE (T6.5) ===[/bold cyan]\n"
    )

    metrics = compute_rule_coverage()

    table = Table(title="Shipped Clinical Ruleset Coverage Matrix", show_header=True)
    table.add_column("Rule ID", style="bold")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Positive (>=3)", justify="right")
    table.add_column("Negative (>=3)", justify="right")
    table.add_column("Boundary (>=1)", justify="right")
    table.add_column("Verdict", justify="center")

    for rule_id, info in sorted(metrics["rule_status"].items()):
        is_needs_source = info["status"] == RuleStatus.NEEDS_SOURCE.value
        pos_display = f"{info['pos']} (N/A)" if is_needs_source else str(info["pos"])
        status_color = "green" if info["passed"] else "red"
        verdict = f"[{status_color}]{'PASS' if info['passed'] else 'FAIL'}[/{status_color}]"

        table.add_row(
            rule_id,
            info["type"],
            info["status"],
            pos_display,
            str(info["neg"]),
            str(info["bnd"]),
            verdict,
        )

    console.print(table)

    # Summary metrics
    console.print("\n[bold]Metrics Summary:[/bold]")
    console.print(
        f"  * Total Active Rules: {metrics['total_active_rules']} "
        f"({metrics['covered_active_rules']} fully covered)"
    )
    console.print(f"  * Total Golden Test Scenarios: {metrics['total_cases']}")
    console.print(f"  * Alert Fatigue Metric: {metrics['alerts_per_patient']} alerts/patient")
    console.print(f"  * False-Alert Rate on Negatives: {metrics['false_alert_rate']}%")
    console.print(
        f"  * Schema V2 Candidate Rules (Batches 1-3): {metrics['candidate_rules_count']} "
        "(status: UNVERIFIED / RETRIEVED_UNREVIEWED)"
    )

    if metrics["failing_rules"]:
        console.print(
            f"\n[bold red][FAIL] CI Gate Failed: {len(metrics['failing_rules'])} "
            f"rules lack required case coverage: {metrics['failing_rules']}[/bold red]\n"
        )
        return 1

    if metrics["false_alert_rate"] > 0.0:
        console.print(
            f"\n[bold red][FAIL] CI Gate Failed: False-alert rate on negatives must be 0.0% "
            f"(got {metrics['false_alert_rate']}%)[/bold red]\n"
        )
        return 1

    console.print(
        "\n[bold green][OK] Rule coverage matrix and alert fatigue gate PASSED (100% compliant).[/bold green]\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
