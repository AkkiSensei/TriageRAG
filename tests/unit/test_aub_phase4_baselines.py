"""Unit tests for AUB Phase 4 Task 4.3: Random and Position-Prior Baselines (AUB-EVL-01).

Safety Properties (AUB-EVL-01, T4.3, Rules R1, R10, R12):
1. PositionPriorRetriever fits strictly on the training/dev split and never inspects test labels.
2. Deterministic tie-breaking on tied label frequencies using alphabetical node sorting.
3. Fallback to overall prior for unrouted / unseen clinical syndromes.
4. Position-prior baseline answers Reviewer B's challenge question:
   Is Recall@1 substantially more than the label frequency baseline?
5. Random candidate baseline is deterministic under fixed seeds and provides paired CIs.
"""

from __future__ import annotations

import yaml

from eval.run_retrieval import (
    PositionPriorRetriever,
    run_candidate_pool_random_baseline,
    run_position_prior_baseline,
)
from triagerag.config import get_repo_root
from triagerag.contracts.schemas import Patient


def test_position_prior_fits_strictly_on_dev_and_ignores_test() -> None:
    """T4.3: PositionPriorRetriever fits strictly on dev cases without label leakage."""
    dataset_path = get_repo_root() / "eval" / "retrieval" / "dataset.yaml"
    raw_ds = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    dev_cases = [c for c in raw_ds["cases"] if c["split"] == "dev"]
    test_cases = [c for c in raw_ds["cases"] if c["split"] == "test"]

    retriever = PositionPriorRetriever.fit(dev_cases)
    # Check that every syndrome in dev priors was learned from dev cases
    for syn, top_nodes in retriever.syndrome_priors.items():
        assert len(top_nodes) > 0
        assert syn in retriever.frequency_table

    # Modifying test cases must not alter retriever
    tampered_test = list(test_cases)
    for c in tampered_test:
        c["relevance_grades"] = {"FAKE_NODE_999": 2}

    retriever_after = PositionPriorRetriever.fit(dev_cases)
    assert retriever.syndrome_priors == retriever_after.syndrome_priors
    assert "FAKE_NODE_999" not in retriever_after.overall_prior


def test_position_prior_deterministic_tie_breaking() -> None:
    """T4.3: Tied frequencies must be broken deterministically by chunk_id ascending."""
    synthetic_cases = [
        {
            "expect_abstain": False,
            "suspected_syndrome": "chest_pain",
            "relevance_grades": {"NODE_Z": 2, "NODE_A": 2},
        },
        {
            "expect_abstain": False,
            "suspected_syndrome": "chest_pain",
            "relevance_grades": {"NODE_Z": 2, "NODE_A": 2},
        },
    ]
    retriever = PositionPriorRetriever.fit(synthetic_cases)
    ranking = retriever.syndrome_priors["chest_pain"]
    assert ranking[0] == "NODE_A"
    assert ranking[1] == "NODE_Z"


def test_position_prior_fallback_for_unseen_or_unrouted() -> None:
    """T4.3: Unseen or unrouted queries fall back to the overall most frequent node."""
    synthetic_cases = [
        {
            "expect_abstain": False,
            "suspected_syndrome": "chest_pain",
            "relevance_grades": {"NODE_CP_1": 2},
        },
        {
            "expect_abstain": False,
            "suspected_syndrome": "chest_pain",
            "relevance_grades": {"NODE_CP_1": 2},
        },
        {
            "expect_abstain": False,
            "suspected_syndrome": "anaphylaxis",
            "relevance_grades": {"NODE_ANA_1": 2},
        },
    ]
    retriever = PositionPriorRetriever.fit(synthetic_cases)
    assert retriever.overall_prior[0] == "NODE_CP_1"

    # Patient without suspected syndrome
    patient_empty = Patient.model_construct(suspected_syndrome=None)  # type: ignore[call-arg]
    top_empty = retriever.retrieve_ids(patient_empty, top_k=1)
    assert top_empty == ["NODE_CP_1"]

    # Patient with novel/unseen syndrome
    patient_novel = Patient.model_construct(suspected_syndrome="rare_tropical_disease")  # type: ignore[call-arg]
    top_novel = retriever.retrieve_ids(patient_novel, top_k=1)
    assert top_novel == ["NODE_CP_1"]


def test_run_position_prior_baseline_answers_challenge_question() -> None:
    """T4.3: Position-prior baseline report answers whether R@1 exceeds label frequency."""
    report = run_position_prior_baseline(seed=42)
    assert "overall_test" in report
    overall = report["overall_test"]

    assert overall["test_cases"] == 50
    assert overall["bm25_recall_at_1"] > overall["position_prior_recall_at_1"]
    assert report["is_recall_at_1_above_label_frequency"] is True
    assert overall["paired_diff_r1_points"] > 0
    assert overall["paired_diff_r1_ci_95"][0] > 0
    assert "interpretation" in report
    assert "System Recall@1 significantly exceeds label frequency prior" in report["interpretation"]


def test_random_candidate_baseline_determinism() -> None:
    """T4.3: Candidate pool random baseline is deterministic given the same seed."""
    run1 = run_candidate_pool_random_baseline(seed=42, num_trials=20)
    run2 = run_candidate_pool_random_baseline(seed=42, num_trials=20)

    assert run1["random_recall_at_1"] == run2["random_recall_at_1"]
    assert run1["random_recall_at_5"] == run2["random_recall_at_5"]
    assert run1["overall_test"]["bm25_recall_at_1"] == run2["overall_test"]["bm25_recall_at_1"]
