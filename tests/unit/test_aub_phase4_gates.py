"""Unit tests for AUB Phase 4 Task 4.5: Validity Self-Test and Benchmark Gates (AUB-EVL-01).

Safety Properties (AUB-EVL-01, T4.5, Rules R1, R2, R10, R11, R12):
1. Benchmark validity self-test: random Recall@5 must be < 60.0% (candidate pool non-triviality).
2. Benchmark validity self-test: position-prior R@1 must be < system R@1 by a CI-excluding margin.
3. If either validity self-test fails, the benchmark itself is declared BENCHMARK_INVALID.
4. Trivial constant retriever fails the gate (violates false_accept_rate and hard_negative_abstain).
5. Trivial all-abstain retriever fails the gate (violates syndrome_provided recall threshold).
6. Production retriever passes all validity checks and safety gates.
"""

from __future__ import annotations

from typing import Any

from eval.run_retrieval import (
    run_retrieval_benchmark,
    validate_benchmark_gate,
)


def _make_dummy_summary(
    random_r5: float = 10.0,
    above_position_prior: bool = True,
    ci_prior: list[float] | None = None,
    far: float = 0.0,
    wsr: float = 0.0,
    wpr: float = 0.0,
    hn_recall: float = 1.0,
    syn_r5: float = 98.0,
    deterministic: bool = True,
) -> dict[str, Any]:
    return {
        "deterministic": deterministic,
        "random_candidate_baseline": {
            "random_recall_at_5": random_r5,
        },
        "position_prior_baseline": {
            "is_recall_at_1_above_label_frequency": above_position_prior,
            "overall_test": {
                "paired_diff_r1_ci_95": ci_prior or [10.0, 30.0],
            },
        },
        "test": {
            "false_accept_rate": far,
            "wrong_syndrome_rate": wsr,
            "wrong_protocol_rate": wpr,
            "abstain_recall_hard_negatives": hn_recall,
            "syndrome_provided": {"recall_at_5": syn_r5},
            "vitals_only": {"recall_at_5": 0.0},
        },
    }


def test_validity_self_test_rejects_saturated_candidate_pool() -> None:
    """T4.5: If random baseline Recall@5 >= 60%, benchmark is declared BENCHMARK_INVALID."""
    summary = _make_dummy_summary(random_r5=65.0)
    gate = validate_benchmark_gate(summary)
    assert gate["benchmark_valid"] is False
    assert gate["status"] == "BENCHMARK_INVALID"
    assert gate["validity_checks"]["random_baseline_recall_at_5_under_60"]["passed"] is False


def test_validity_self_test_rejects_inferior_to_position_prior() -> None:
    """T4.5: If system does not beat position prior, benchmark is BENCHMARK_INVALID."""
    summary = _make_dummy_summary(above_position_prior=False, ci_prior=[-5.0, 10.0])
    gate = validate_benchmark_gate(summary)
    assert gate["benchmark_valid"] is False
    assert gate["status"] == "BENCHMARK_INVALID"
    assert gate["validity_checks"]["position_prior_r1_margin_positive"]["passed"] is False


def test_trivial_constant_retriever_fails_gate() -> None:
    """T4.5: A trivial retriever fails false-accept and hard-negative gates."""
    # Constant retriever fails to abstain on hard negatives and produces false accepts
    summary = _make_dummy_summary(far=0.45, hn_recall=0.0, wsr=0.20, wpr=0.65)
    gate = validate_benchmark_gate(summary)
    assert gate["benchmark_valid"] is True
    assert gate["status"] == "FAIL"
    assert gate["system_checks"]["false_accept_rate_is_zero"]["passed"] is False
    assert gate["system_checks"]["hard_negative_abstain_recall_is_one"]["passed"] is False


def test_trivial_all_abstain_retriever_fails_gate() -> None:
    """T4.5: A trivial retriever that always abstains fails the syndrome-provided recall gate."""
    summary = _make_dummy_summary(syn_r5=0.0)
    gate = validate_benchmark_gate(summary)
    assert gate["benchmark_valid"] is True
    assert gate["status"] == "FAIL"
    assert gate["system_checks"]["syndrome_provided_recall_at_5_min_95"]["passed"] is False


def test_production_bm25_passes_validity_and_system_gate() -> None:
    """T4.5: Real production BM25 evaluation passes validity self-tests and performance gates."""
    summary = run_retrieval_benchmark(backend="bm25", write_reports=False)
    gate = summary.get("gate_report") or validate_benchmark_gate(summary)

    assert gate["benchmark_valid"] is True
    assert gate["validity_checks"]["random_baseline_recall_at_5_under_60"]["passed"] is True
    assert gate["validity_checks"]["position_prior_r1_margin_positive"]["passed"] is True
    assert gate["status"] == "PASS"
    assert summary["status"] == "PASS"
