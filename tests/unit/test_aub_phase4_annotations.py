"""Unit tests for AUB Phase 4 Task 4.2: Relevance Labels and Agreement (AUB-EVL-01).

Safety Properties (AUB-EVL-01, T4.2, Rules R1, R3, R10, R12):
1. ANNOTATION_GUIDE.md specifies the 3-level relevance grading ontology and mandatory disclaimer.
2. Blinded case export produces >= 100 cases with zero leakage of ground truth, scores, or rankings.
3. Cohen's kappa calculation matches hand-computed analytic fixtures for perfect agreement,
   chance agreement, and a 3-category confusion matrix.
4. Honest reporting invariant: agreement_status.json explicitly records the unreviewed state
   and human dependency without fabricated metrics.
"""

from __future__ import annotations

import json
import math

from tools.export_annotations import compute_cohens_kappa
from triagerag.config import get_repo_root


def test_annotation_guide_ontology_and_disclaimer() -> None:
    """T4.2: ANNOTATION_GUIDE.md defines 0, 1, 2 grades and carries research disclaimer."""
    guide_path = get_repo_root() / "docs" / "evaluation" / "ANNOTATION_GUIDE.md"
    assert guide_path.exists(), "docs/evaluation/ANNOTATION_GUIDE.md missing"

    content = guide_path.read_text(encoding="utf-8")
    disclaimer = (
        "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
    )
    assert disclaimer in content
    assert "Grade 2" in content or "Grade 2: Directly Actionable" in content
    assert "Grade 1" in content or "Grade 1: Supporting" in content
    assert "Grade 0" in content or "Grade 0: Irrelevant" in content


def test_blinded_cases_export_leakage_free() -> None:
    """T4.2: Blinded export must contain >= 100 cases with zero ground truth leakage."""
    blinded_path = get_repo_root() / "eval" / "annotations" / "blinded_cases.json"
    assert blinded_path.exists(), "eval/annotations/blinded_cases.json missing"

    data = json.loads(blinded_path.read_text(encoding="utf-8"))
    cases = data.get("blinded_cases", [])
    assert len(cases) >= 100

    forbidden_keys = {
        "expected_syndrome",
        "expect_abstain",
        "expected_abstain_code",
        "relevance_grades",
        "reviewed_by",
        "score",
        "rank",
    }
    for c in cases:
        for k in forbidden_keys:
            assert k not in c, f"Leaked key '{k}' found in blinded case {c.get('case_id')}"
        assert "candidate_nodes_to_grade" in c
        assert "ratings_placeholder" in c


def test_cohens_kappa_perfect_agreement() -> None:
    """T4.2: Perfect agreement yields kappa = 1.0 and observed agreement = 1.0."""
    ratings = [0, 1, 2, 0, 1, 2, 2, 1, 0, 2]
    res = compute_cohens_kappa(ratings, ratings, categories=[0, 1, 2])
    assert math.isclose(res["observed_agreement"], 1.0, abs_tol=1e-5)
    assert math.isclose(res["cohens_kappa"], 1.0, abs_tol=1e-5)


def test_cohens_kappa_chance_agreement() -> None:
    """T4.2: Pure chance distribution yields kappa approx 0.0."""
    # Balanced cross-product distribution
    rater_a = [0, 0, 1, 1]
    rater_b = [0, 1, 0, 1]
    res = compute_cohens_kappa(rater_a, rater_b, categories=[0, 1])
    # Po = 2/4 = 0.5, Pe = (2/4*2/4) + (2/4*2/4) = 0.5 -> kappa = 0.0
    assert math.isclose(res["observed_agreement"], 0.5, abs_tol=1e-5)
    assert math.isclose(res["expected_agreement"], 0.5, abs_tol=1e-5)
    assert math.isclose(res["cohens_kappa"], 0.0, abs_tol=1e-5)


def test_cohens_kappa_hand_computed_fixture() -> None:
    """T4.2: Hand-computed 3x3 category matrix matches analytic expectation.

    Fixture:
    N = 50 items rated by Rater A and Rater B into categories [0, 1, 2]:
    C = [
      [15, 5, 0],   # rater A=0: 20 items (15 with B=0, 5 with B=1, 0 with B=2)
      [2, 18, 3],   # rater A=1: 23 items (2 with B=0, 18 with B=1, 3 with B=2)
      [0, 2, 5]     # rater A=2: 7 items (0 with B=0, 2 with B=1, 5 with B=2)
    ]
    Rater B marginals: col 0 = 17, col 1 = 25, col 2 = 8
    Po = (15 + 18 + 5) / 50 = 38 / 50 = 0.76
    Pe = (20*17 + 23*25 + 7*8) / 2500 = (340 + 575 + 56) / 2500 = 971 / 2500 = 0.3884
    Expected kappa = (0.76 - 0.3884) / (1.0 - 0.3884) = 0.3716 / 0.6116 = 0.6075866579...
    """
    rater_a: list[int] = []
    rater_b: list[int] = []

    # A=0: 15 with B=0, 5 with B=1, 0 with B=2
    rater_a.extend([0] * 15)
    rater_b.extend([0] * 15)
    rater_a.extend([0] * 5)
    rater_b.extend([1] * 5)

    # A=1: 2 with B=0, 18 with B=1, 3 with B=2
    rater_a.extend([1] * 2)
    rater_b.extend([0] * 2)
    rater_a.extend([1] * 18)
    rater_b.extend([1] * 18)
    rater_a.extend([1] * 3)
    rater_b.extend([2] * 3)

    # A=2: 0 with B=0, 2 with B=1, 5 with B=2
    rater_a.extend([2] * 2)
    rater_b.extend([1] * 2)
    rater_a.extend([2] * 5)
    rater_b.extend([2] * 5)

    assert len(rater_a) == 50
    assert len(rater_b) == 50

    res = compute_cohens_kappa(rater_a, rater_b, categories=[0, 1, 2])
    assert math.isclose(res["observed_agreement"], 0.76, abs_tol=1e-5)
    assert math.isclose(res["expected_agreement"], 0.3884, abs_tol=1e-5)
    expected_kappa = 0.3716 / 0.6116
    assert math.isclose(res["cohens_kappa"], expected_kappa, abs_tol=1e-4)


def test_agreement_status_honest_human_dependency() -> None:
    """T4.2: agreement_status.json honestly records human dependency."""
    status_path = get_repo_root() / "eval" / "annotations" / "agreement_status.json"
    assert status_path.exists(), "eval/annotations/agreement_status.json missing"

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["human_agreement_measured"] is False
    assert status["cohens_kappa"] is None
    assert status["provenance_status"] == "AGENT_AUTHORED_UNREVIEWED"
    assert status["agreement_state"] == "BLOCKED_PENDING_INDEPENDENT_HUMAN_ANNOTATION"
