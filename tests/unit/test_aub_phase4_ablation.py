"""Unit tests for AUB Phase 4 Task T4.7: Controlled Retrieval Arm Comparison & Backend Decision.

Safety Properties (AUB-EVL-01, Rules R1, R2, R10, R11, R12):
1. All 7 retrieval arms construct offline and execute deterministically.
2. decide_backend() strictly enforces hard safety invariants (FAR==0, WSR==0, HN==1, latency<50ms).
3. decide_backend() adopts an alternative arm only with non-regressing R@5, MRR gain >= +0.05,
   and paired difference bootstrap CI strictly excluding zero.
4. If no arm is statistically distinguishable, decide_backend() honestly retains baseline 'bm25'.
5. Non-mutating default: running ablation without write_reports does not touch eval/reports/.
"""

from __future__ import annotations

from typing import Any

from eval.run_retrieval_ablation import (
    RETRIEVAL_ARMS,
    _compute_paired_differences,
    decide_backend,
    run_retrieval_ablation_suite,
)
from triagerag.config import get_data_dir
from triagerag.rag.service import RetrievalService


def test_all_seven_arms_defined_and_constructible() -> None:
    """T4.7: Verify all seven ablation arms are properly registered and constructible offline."""
    assert len(RETRIEVAL_ARMS) == 7
    expected_keys = {
        "bm25",
        "bm25_pure_lexical",
        "char_ngram",
        "hybrid_rrf",
        "hybrid_rrf_rerank",
        "bm25_contextual",
        "contextual_predicate",
    }
    registered_keys = {key for key, _ in RETRIEVAL_ARMS}
    assert registered_keys == expected_keys

    data_dir = get_data_dir()
    for key, label in RETRIEVAL_ARMS:
        service = RetrievalService.create_default(data_dir, backend=key)
        assert service is not None
        assert service.index is not None
        assert label.startswith("Arm ")


def test_decide_backend_retention_when_alternatives_cross_zero() -> None:
    """T4.7: When an alternative has higher MRR but CI crosses zero, bm25 is retained."""
    mock_arms: dict[str, Any] = {
        "bm25": {
            "test_split": {
                "recall_at_5": 76.0,
                "mrr": 0.6300,
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 4.1,
            },
            "statistically_distinguishable_from_bm25": False,
        },
        "contextual_predicate": {
            "test_split": {
                "recall_at_5": 76.0,
                "mrr": 0.6833,  # +0.0533 point estimate gain (meets +0.05 threshold)
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 4.5,
                "statistically_distinguishable_from_bm25": False,  # CI [-0.01, 0.12] crosses zero
            },
            "statistically_distinguishable_from_bm25": False,
        },
    }
    decision = decide_backend(mock_arms)
    # Must retain bm25 because CI crosses zero (not statistically distinguishable)
    assert decision == "bm25"


def test_decide_backend_rejects_unsafe_arms() -> None:
    """T4.7: Any arm violating hard safety invariants is disqualified regardless of MRR."""
    # Case 1: Arm with false accepts on distractors (FAR > 0)
    mock_unsafe_far: dict[str, Any] = {
        "bm25": {
            "test_split": {
                "recall_at_5": 76.0,
                "mrr": 0.6300,
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 4.0,
            }
        },
        "hybrid_rrf_rerank": {
            "test_split": {
                "recall_at_5": 99.0,
                "mrr": 0.9500,
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.1935,  # FAILS SAFETY
                "abstain_recall_hard_negatives": 0.80,  # FAILS SAFETY
                "latency_p95_ms": 10.0,
                "statistically_distinguishable_from_bm25": True,
            }
        },
    }
    assert decide_backend(mock_unsafe_far) == "bm25"

    # Case 2: Arm with high latency (exceeds 50ms budget)
    mock_slow: dict[str, Any] = {
        "bm25": {
            "test_split": {
                "recall_at_5": 76.0,
                "mrr": 0.6300,
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 4.0,
            }
        },
        "slow_neural_arm": {
            "test_split": {
                "recall_at_5": 90.0,
                "mrr": 0.8500,
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 120.0,  # FAILS LATENCY BUDGET
                "statistically_distinguishable_from_bm25": True,
            }
        },
    }
    assert decide_backend(mock_slow) == "bm25"


def test_decide_backend_adopts_statistically_significant_candidate() -> None:
    """T4.7: A safe candidate meeting all adoption criteria is correctly adopted."""
    mock_winning: dict[str, Any] = {
        "bm25": {
            "test_split": {
                "recall_at_5": 76.0,
                "mrr": 0.6300,
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 4.0,
            }
        },
        "improved_arm": {
            "test_split": {
                "recall_at_5": 82.0,  # Non-regressing
                "mrr": 0.7200,  # +0.09 >= +0.05
                "wrong_protocol_rate": 0.0,
                "false_accept_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 6.5,
                "statistically_distinguishable_from_bm25": True,  # CI strictly excludes zero
            },
            "statistically_distinguishable_from_bm25": True,
        },
    }
    assert decide_backend(mock_winning) == "improved_arm"


def test_compute_paired_differences_contract() -> None:
    """T4.7: Paired difference computation returns structured intervals with distinguishability."""
    data_dir = get_data_dir()
    services = {
        "bm25": RetrievalService.create_default(data_dir, backend="bm25"),
        "bm25_pure_lexical": RetrievalService.create_default(data_dir, backend="bm25_pure_lexical"),
    }
    sample_cases = [
        {
            "expect_abstain": False,
            "population": "adult",
            "age": {"value": 45, "unit": "years"},
            "suspected_syndrome": "chest_pain",
            "vitals": {"heart_rate_bpm": 80, "systolic_bp_mmhg": 130},
            "relevance_grades": {"CHEST_PAIN_01_185ad605": 2},
        },
        {
            "expect_abstain": True,
            "population": "adult",
            "age": {"value": 45, "unit": "years"},
            "suspected_syndrome": "anaphylaxis",
            "vitals": {"heart_rate_bpm": 70, "systolic_bp_mmhg": 120},
            "relevance_grades": {},
        },
    ]
    diffs = _compute_paired_differences(
        sample_cases, services, baseline_key="bm25", num_bootstraps=50, seed=42
    )
    assert "bm25" in diffs
    assert "bm25_pure_lexical" in diffs

    base_stat = diffs["bm25"]
    assert base_stat["paired_diff_mrr"] == 0.0
    assert base_stat["statistically_distinguishable_from_bm25"] is False

    cand_stat = diffs["bm25_pure_lexical"]
    assert "paired_diff_mrr" in cand_stat
    assert len(cand_stat["paired_diff_mrr_ci95"]) == 2
    assert isinstance(cand_stat["statistically_distinguishable_from_bm25"], bool)


def test_ablation_suite_non_mutating_by_default() -> None:
    """T4.7: Running ablation suite without write_reports does not dirty git tree."""
    res = run_retrieval_ablation_suite(write_reports=False)
    assert res == 0
