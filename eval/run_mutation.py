"""Mutation testing runner for TriageRAG clinical rules.

Safety Property (Rule R10):
Measured, not claimed. Dropping any BLOCK or HIGH rule via registry injection
MUST cause the golden test suite to fail (killing the mutant).
If any mutant survives, CI fails.
"""

from __future__ import annotations

import dataclasses
import sys
from typing import Any

from eval.run_golden import _build_patient_from_case
from triagerag.config import get_data_dir
from triagerag.contracts.enums import Severity
from triagerag.engine.registry import ClinicalRegistry
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.normalize.yaml_loader import load_yaml_decimal


def evaluate_cases_on_registry(cases: list[dict[str, Any]], registry: ClinicalRegistry) -> bool:
    """Evaluate golden cases against a (potentially mutated) registry.

    Returns True if ALL cases pass, False if any case fails.
    """
    for case in cases:
        patient = _build_patient_from_case(case, registry)
        alerts, skipped, _, _ = evaluate_baseline(patient, registry)

        fired_rule_ids = {a.rule_id for a in alerts}
        skipped_rule_ids = {s.rule_id for s in skipped}

        must_fire = set(case.get("must_fire", []))
        must_skip = set(case.get("must_skip", []))
        must_not_fire = set(case.get("must_not_fire", []))

        # Check conditions
        if not must_fire.issubset(fired_rule_ids):
            return False
        if not must_skip.issubset(skipped_rule_ids):
            return False
        if not must_not_fire.isdisjoint(fired_rule_ids):
            return False

    return True


def run_mutation_suite() -> tuple[bool, int, int, float]:
    """Execute mutation testing: drop each BLOCK/HIGH rule and verify test failure."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    golden_path = data_dir / "golden" / "shipped_ruleset_cases.yaml"

    cases_data = load_yaml_decimal(golden_path)
    cases = cases_data.get("cases", [])

    # Identify all BLOCK and HIGH severity rules in the ruleset
    critical_rules = [r for r in registry.rules if r.severity in (Severity.BLOCK, Severity.HIGH)]

    print(f"Executing Mutation Testing across {len(critical_rules)} critical BLOCK/HIGH rules...")

    killed_mutants = 0
    survived_mutants: list[str] = []

    for rule in critical_rules:
        # Create mutant by dropping rule
        mutant_rules = [r for r in registry.rules if r.id != rule.id]
        mutated_registry = dataclasses.replace(registry, rules=mutant_rules)

        # Run golden suite against mutated registry
        all_passed = evaluate_cases_on_registry(cases, mutated_registry)
        if not all_passed:
            # Good: Mutant was caught and killed by the test suite!
            killed_mutants += 1
            print(
                f"  [KILLED] Dropped {rule.severity.value} rule '{rule.id}' -> Golden suite failed."
            )
        else:
            # Bad: Mutant survived! The test suite lacked coverage for this critical rule.
            survived_mutants.append(rule.id)
            print(f"  [SURVIVED] Dropped {rule.severity.value} rule '{rule.id}' -> Golden passed!")

    total_mutants = len(critical_rules)
    mutation_score = (killed_mutants / total_mutants) * 100.0 if total_mutants > 0 else 0.0

    print(f"\nMutation Score: {killed_mutants}/{total_mutants} killed ({mutation_score:.1f}%).")
    if survived_mutants:
        print(f"WARNING: Survived mutants: {', '.join(survived_mutants)}")

    success = killed_mutants == total_mutants
    return success, killed_mutants, total_mutants, mutation_score


if __name__ == "__main__":
    success, killed, total, score = run_mutation_suite()
    if not success:
        sys.exit(1)
