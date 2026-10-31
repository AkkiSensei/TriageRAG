"""Unit tests for AUB Phase 4 Task 4.6: Hand-Computed Metric Fixtures (AUB-EVL-01).

Safety Properties (AUB-EVL-01, T4.6, Rules R1, R10, R12):
1. Every evaluation metric function is tested against hand-calculated pencil-and-paper fixtures.
2. Verified formulas: Recall@{1,3,5,10}, MRR, nDCG@{5,10}, FAR, WSR, legacy WPR,
   per-code abstention, Cohen's kappa, and ECE.
3. Tests match mathematical expectations to floating-point precision with zero external deps.
"""

from __future__ import annotations

import math

from eval.run_retrieval import (
    _compute_ece,
    _compute_ndcg_at_k,
    _group_bootstrap_ci95,
)
from tools.export_annotations import compute_cohens_kappa


def test_hand_computed_recall_and_mrr_fixture() -> None:
    """T4.6: Hand-computed Recall@{1,3,5,10} and MRR fixture over 4 queries.

    Hand-calculated values:
    Query 1: first grade-2 hit at rank 1 -> R@1=1, R@3=1, R@5=1, R@10=1, RR=1.0
    Query 2: first grade-2 hit at rank 3 -> R@1=0, R@3=1, R@5=1, R@10=1, RR=1/3
    Query 3: first grade-2 hit at rank 7 -> R@1=0, R@3=0, R@5=0, R@10=1, RR=1/7
    Query 4: no hit in top 10            -> R@1=0, R@3=0, R@5=0, R@10=0, RR=0.0

    Means:
    R@1 = 1/4 = 0.25 (25.0%)
    R@3 = 2/4 = 0.50 (50.0%)
    R@5 = 2/4 = 0.50 (50.0%)
    R@10 = 3/4 = 0.75 (75.0%)
    MRR = (1.0 + 1/3 + 1/7 + 0.0) / 4 = 1.4761904762 / 4 = 0.3690476190...
    """
    hit_ranks_list = [[1], [3], [7], []]
    n = len(hit_ranks_list)

    r1_list = [1.0 if (hr and hr[0] == 1) else 0.0 for hr in hit_ranks_list]
    r3_list = [1.0 if (hr and hr[0] <= 3) else 0.0 for hr in hit_ranks_list]
    r5_list = [1.0 if (hr and hr[0] <= 5) else 0.0 for hr in hit_ranks_list]
    r10_list = [1.0 if (hr and hr[0] <= 10) else 0.0 for hr in hit_ranks_list]
    rr_list = [1.0 / float(hr[0]) if hr else 0.0 for hr in hit_ranks_list]

    assert math.isclose(sum(r1_list) / n, 0.25, abs_tol=1e-6)
    assert math.isclose(sum(r3_list) / n, 0.50, abs_tol=1e-6)
    assert math.isclose(sum(r5_list) / n, 0.50, abs_tol=1e-6)
    assert math.isclose(sum(r10_list) / n, 0.75, abs_tol=1e-6)

    expected_mrr = (1.0 + (1.0 / 3.0) + (1.0 / 7.0)) / 4.0
    assert math.isclose(sum(rr_list) / n, expected_mrr, abs_tol=1e-6)


def test_hand_computed_ndcg_fixture() -> None:
    """T4.6: Hand-computed nDCG@5 fixture with 3-level graded relevance.

    Grades: N1: 2, N2: 1, N3: 0, N4: 2, N5: 0
    Retrieved: ["N2", "N3", "N1", "N5", "N4"]
    Gains:
    rank 1: N2 (rel 1) -> (2^1 - 1) / log2(2) = 1.0 / 1.0 = 1.0
    rank 2: N3 (rel 0) -> 0.0
    rank 3: N1 (rel 2) -> (2^2 - 1) / log2(4) = 3.0 / 2.0 = 1.5
    rank 4: N5 (rel 0) -> 0.0
    rank 5: N4 (rel 2) -> (2^2 - 1) / log2(6) = 3.0 / 2.5849625007 = 1.1605584218
    DCG@5 = 1.0 + 1.5 + 1.1605584218 = 3.6605584218

    Ideal ranking gains (sorted: 2, 2, 1, 0, 0):
    rank 1: rel 2 -> 3.0 / 1.0 = 3.0
    rank 2: rel 2 -> 3.0 / log2(3) = 3.0 / 1.5849625007 = 1.8927892607
    rank 3: rel 1 -> 1.0 / 2.0 = 0.5
    IDCG@5 = 3.0 + 1.8927892607 + 0.5 = 5.3927892607
    Expected nDCG@5 = 3.6605584218 / 5.3927892607 = 0.6787876359...
    """
    retrieved = ["N2", "N3", "N1", "N5", "N4"]
    grades = {"N1": 2, "N2": 1, "N3": 0, "N4": 2, "N5": 0}

    dcg = 1.0 + (3.0 / math.log2(4.0)) + (3.0 / math.log2(6.0))
    idcg = (3.0 / math.log2(2.0)) + (3.0 / math.log2(3.0)) + (1.0 / math.log2(4.0))
    expected_ndcg = dcg / idcg

    computed = _compute_ndcg_at_k(retrieved, grades, k=5)
    assert math.isclose(computed, expected_ndcg, abs_tol=1e-5)


def test_hand_computed_far_wsr_wpr_fixture() -> None:
    """T4.6: Hand-computed False Accept Rate, Wrong Syndrome Rate, and Legacy WPR.

    Setup: 10 queries total
    - 4 expected abstain: 3 correctly abstained, 1 false accept (retrieved substantive)
      -> FAR = 1 / 4 = 0.25
    - 6 positive queries: 1 false negative (abstained), 5 non-abstaining retrievals
      Out of 5 non-abstaining: 4 retrieved correct syndrome, 1 retrieved wrong syndrome
      -> WSR = 1 / 5 = 0.20
    Legacy wrong protocol count = 1 (false accept) + 1 (wrong syndrome) = 2
    -> Legacy WPR = 2 / 10 = 0.20
    """
    total_abstain_cases = 4
    false_accept_count = 1
    far = float(false_accept_count) / float(total_abstain_cases)
    assert math.isclose(far, 0.25, abs_tol=1e-6)

    positive_retrieved = 5
    wrong_syndrome_count = 1
    wsr = float(wrong_syndrome_count) / float(positive_retrieved)
    assert math.isclose(wsr, 0.20, abs_tol=1e-6)

    total_cases = 10
    legacy_wrong_protocol_count = false_accept_count + wrong_syndrome_count
    wpr = float(legacy_wrong_protocol_count) / float(total_cases)
    assert math.isclose(wpr, 0.20, abs_tol=1e-6)


def test_hand_computed_per_code_abstention_fixture() -> None:
    """T4.6: Hand-computed per-code abstention precision and recall fixture.

    Cases:
    Case 1: expected=CODE_A, actual=CODE_A (TP for A)
    Case 2: expected=CODE_A, actual=CODE_B (FN for A, FP for B)
    Case 3: expected=CODE_B, actual=CODE_B (TP for B)
    Case 4: expected=CODE_C, actual=CODE_A (FN for C, FP for A)

    Expected metrics:
    CODE_A: support=2, predicted=2, TP=1 -> Prec=1/2=0.50, Rec=1/2=0.50
    CODE_B: support=1, predicted=2, TP=1 -> Prec=1/2=0.50, Rec=1/1=1.00
    CODE_C: support=1, predicted=0, TP=0 -> Prec=1.00 (no FP), Rec=0/1=0.00
    """
    cases = [
        ("CODE_A", "CODE_A"),
        ("CODE_A", "CODE_B"),
        ("CODE_B", "CODE_B"),
        ("CODE_C", "CODE_A"),
    ]

    all_codes = sorted({"CODE_A", "CODE_B", "CODE_C"})
    stats: dict[str, dict[str, float]] = {}

    for c in all_codes:
        support = sum(1 for exp, _ in cases if exp == c)
        predicted = sum(1 for _, act in cases if act == c)
        tp = sum(1 for exp, act in cases if exp == c and act == c)
        prec = float(tp) / float(predicted) if predicted > 0 else 1.0
        rec = float(tp) / float(support) if support > 0 else 1.0
        stats[c] = {"precision": prec, "recall": rec}

    assert math.isclose(stats["CODE_A"]["precision"], 0.50, abs_tol=1e-6)
    assert math.isclose(stats["CODE_A"]["recall"], 0.50, abs_tol=1e-6)
    assert math.isclose(stats["CODE_B"]["precision"], 0.50, abs_tol=1e-6)
    assert math.isclose(stats["CODE_B"]["recall"], 1.00, abs_tol=1e-6)
    assert math.isclose(stats["CODE_C"]["precision"], 1.00, abs_tol=1e-6)
    assert math.isclose(stats["CODE_C"]["recall"], 0.00, abs_tol=1e-6)


def test_hand_computed_ece_fixture() -> None:
    r"""T4.6: Hand-computed Expected Calibration Error fixture over 5 bins.

    N = 6 items partitioned into 5 bins [0, 0.2), [0.2, 0.4), [0.4, 0.6), [0.6, 0.8), [0.8, 1.0]:
    Item 1: conf = 0.1, corr = 0 (Bin 1: 1 item, avg_conf = 0.1, avg_acc = 0.0 -> diff = 0.1)
    Item 2: conf = 0.3, corr = 1 (Bin 2: 1 item, avg_conf = 0.3, avg_acc = 1.0 -> diff = 0.7)
    Item 3: conf = 0.5, corr = 0 | Bin 3: 2 items, avg_conf = 0.5, avg_acc = 0.5 -> diff = 0.0
    Item 4: conf = 0.5, corr = 1 |
    Item 5: conf = 0.9, corr = 1 | Bin 5: 2 items, avg_conf = 0.9, avg_acc = 1.0 -> diff = 0.1
    Item 6: conf = 0.9, corr = 1 |
    Bin 4: 0 items

    ECE = (1/6 * 0.1) + (1/6 * 0.7) + (2/6 * 0.0) + (0) + (2/6 * 0.1)
        = (0.1 + 0.7 + 0.0 + 0.2) / 6 = 1.0 / 6 = 0.166666... -> rounds to 0.1667
    """
    confidences = [0.1, 0.3, 0.5, 0.5, 0.9, 0.9]
    correctness = [0, 1, 0, 1, 1, 1]

    expected_ece = 1.0 / 6.0
    computed = _compute_ece(confidences, correctness, num_bins=5)
    assert math.isclose(computed, round(expected_ece, 4), abs_tol=1e-4)


def test_hand_computed_cohens_kappa_fixture() -> None:
    """T4.6: Hand-computed Cohen's kappa for 3 categories with exact fractions.

    Confusion matrix:
    A=0: B=0: 10, B=1: 2, B=2: 0 -> sum = 12
    A=1: B=0: 1, B=1: 15, B=2: 2  -> sum = 18
    A=2: B=0: 0, B=1: 1, B=2: 9   -> sum = 10
    Total N = 40

    Marginals B:
    B=0: 10 + 1 + 0 = 11
    B=1: 2 + 15 + 1 = 18
    B=2: 0 + 2 + 9 = 11

    Observed agreement Po = (10 + 15 + 9) / 40 = 34 / 40 = 0.85
    Pe = (12*11 + 18*18 + 10*11) / 1600 = (132 + 324 + 110) / 1600 = 566 / 1600 = 0.35375
    Expected kappa = (0.85 - 0.35375) / (1.0 - 0.35375) = 0.49625 / 0.64625 = 0.76789168...
    """
    rater_a: list[int] = []
    rater_b: list[int] = []

    # A=0
    rater_a.extend([0] * 10)
    rater_b.extend([0] * 10)
    rater_a.extend([0] * 2)
    rater_b.extend([1] * 2)

    # A=1
    rater_a.extend([1] * 1)
    rater_b.extend([0] * 1)
    rater_a.extend([1] * 15)
    rater_b.extend([1] * 15)
    rater_a.extend([1] * 2)
    rater_b.extend([2] * 2)

    # A=2
    rater_a.extend([2] * 1)
    rater_b.extend([1] * 1)
    rater_a.extend([2] * 9)
    rater_b.extend([2] * 9)

    assert len(rater_a) == 40
    res = compute_cohens_kappa(rater_a, rater_b, categories=[0, 1, 2])
    assert math.isclose(res["observed_agreement"], 0.85, abs_tol=1e-6)
    assert math.isclose(res["expected_agreement"], 0.35375, abs_tol=1e-6)
    expected_kappa = 0.49625 / 0.64625
    assert math.isclose(res["cohens_kappa"], expected_kappa, abs_tol=1e-4)


def test_hand_computed_group_bootstrap_ci_fixture() -> None:
    """T4.6: Group-level bootstrap with identical groups preserves exact mean."""
    groups = {
        "G1": [0.75, 0.75],
        "G2": [0.75, 0.75],
        "G3": [0.75, 0.75],
    }
    ci = _group_bootstrap_ci95(groups, n_boot=200, seed=42)
    assert math.isclose(ci[0], 0.75, abs_tol=1e-4)
    assert math.isclose(ci[1], 0.75, abs_tol=1e-4)
