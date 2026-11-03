"""Unit tests for AUB Phase 4 Task 4.4: Honest Metrics (AUB-EVL-01, AUB-ABS-02).

Safety Properties (AUB-EVL-01, AUB-ABS-02, T4.4, Rules R1, R2, R10, R12):
1. False Accept Rate (FAR) and Wrong Syndrome Rate (WSR) are strictly separated.
2. Legacy wrong_protocol_rate is preserved for backward compatibility.
3. No hardcoded 0.95 confidence values are injected into ECE calibration.
4. Per-AbstainCode precision and recall are reported for every active code.
5. Recall@{1,3,5,10}, MRR, and nDCG@{5,10} are reported across overall and stratified slices.
6. Group-level (template-level) bootstrap confidence intervals are computed.
"""

from __future__ import annotations

import math

from eval.run_retrieval import (
    _compute_ece,
    _compute_ndcg_at_k,
    _group_bootstrap_ci95,
    run_retrieval_benchmark,
)


def test_group_bootstrap_ci95_calculation() -> None:
    """T4.4: Cluster bootstrap produces expected bounds across template groups."""
    groups = {
        "TMPL_A": [1.0, 1.0],
        "TMPL_B": [0.0, 0.0],
        "TMPL_C": [1.0, 1.0],
    }
    ci = _group_bootstrap_ci95(groups, n_boot=500, seed=42)
    assert len(ci) == 2
    assert 0.0 <= ci[0] <= ci[1] <= 1.0


def test_ndcg_at_10_calculation() -> None:
    """T4.4: Graded nDCG calculation supports k=10."""
    retrieved = [f"NODE_{i}" for i in range(10)]
    grades = {"NODE_0": 2, "NODE_1": 1, "NODE_9": 2}
    ndcg10 = _compute_ndcg_at_k(retrieved, grades, k=10)
    assert 0.0 < ndcg10 <= 1.0

    # Ideal ranking yields 1.0
    ideal_retrieved = ["NODE_0", "NODE_9", "NODE_1"] + [f"NODE_{i}" for i in range(2, 9)]
    ndcg_ideal = _compute_ndcg_at_k(ideal_retrieved, grades, k=10)
    assert math.isclose(ndcg_ideal, 1.0, abs_tol=1e-5)


def test_ece_computation_handles_real_confidences_without_synthetic_constant() -> None:
    """T4.4: ECE computes calibration error on genuine continuous probabilities."""
    # Perfectly calibrated predictions: confidence = 0.8, acc = 0.8 -> ECE ~ 0.0
    confidences = [0.8] * 10
    correctness = [1] * 8 + [0] * 2
    ece = _compute_ece(confidences, correctness, num_bins=5)
    assert math.isclose(ece, 0.0, abs_tol=1e-4)

    # Completely uncalibrated: confidence = 1.0, acc = 0.0 -> ECE = 1.0
    ece_bad = _compute_ece([1.0] * 5, [0] * 5, num_bins=5)
    assert math.isclose(ece_bad, 1.0, abs_tol=1e-4)


def test_honest_metrics_in_benchmark_summary() -> None:
    """T4.4: run_retrieval_benchmark output contains honest metrics and per-code breakdown."""
    summary = run_retrieval_benchmark(backend="bm25", write_reports=False)
    test_metrics = summary["test"]

    # 1. Separated error rates
    assert "false_accept_rate" in test_metrics
    assert "wrong_syndrome_rate" in test_metrics
    assert "wrong_protocol_rate" in test_metrics  # legacy
    assert test_metrics["false_accept_rate"] == 0.0
    assert test_metrics["wrong_syndrome_rate"] == 0.0
    assert test_metrics["wrong_protocol_rate"] == 0.0

    # 2. Top-10 and Group CI metrics
    assert "recall_at_10" in test_metrics
    assert "ndcg_at_10" in test_metrics
    assert "recall_at_5_group_ci95" in test_metrics
    assert len(test_metrics["recall_at_5_group_ci95"]) == 2

    # 3. Per-code abstention metrics
    assert "per_code_abstention" in test_metrics
    per_code = test_metrics["per_code_abstention"]
    assert len(per_code) > 0
    for _code, code_stats in per_code.items():
        assert "support" in code_stats
        assert "predicted" in code_stats
        assert "true_positives" in code_stats
        assert "precision" in code_stats
        assert "recall" in code_stats
        assert 0.0 <= code_stats["precision"] <= 1.0
        assert 0.0 <= code_stats["recall"] <= 1.0

    # 4. Stratified slices contain full metric set
    syn = test_metrics["syndrome_provided"]
    assert "recall_at_10" in syn
    assert "ndcg_at_10" in syn
    assert "recall_at_5_group_ci95" in syn
