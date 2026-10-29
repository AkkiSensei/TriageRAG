"""Unit tests for WP5: 150-case node-level retrieval evaluation, calibration, and prod parity.

Safety Properties (RAG-01, RAG-10):
1. eval/retrieval/dataset.yaml contains >= 150 structured patient cases split 60% dev / 40% test
   across all 10 mandatory case families with graded node-level relevance (2, 1, 0).
2. Evaluation uses the shared production RetrievalService.create_default() factory (100% parity).
3. Wrong-protocol rate on the held-out test split is strictly 0.0.
4. Reports 95% bootstrap confidence intervals, ECE calibration, and determinism across runs.
"""

from __future__ import annotations

import yaml

from triagerag.config import get_data_dir, get_repo_root
from triagerag.rag.service import RetrievalService


def test_retrieval_dataset_structure_and_224_cases() -> None:
    """WP5 Gate: Dataset has 224 cases, 136/88 dev/test split, and all 10 mandatory families."""
    dataset_path = get_repo_root() / "eval" / "retrieval" / "dataset.yaml"
    assert dataset_path.exists(), "Missing eval/retrieval/dataset.yaml"

    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])
    assert len(cases) >= 224

    dev_cases = [c for c in cases if c.get("split") == "dev"]
    test_cases = [c for c in cases if c.get("split") == "test"]
    assert len(dev_cases) == 136
    assert len(test_cases) == 88

    families = {c.get("family") for c in cases}
    required_families = {
        "syndrome_positives",
        "hard_negatives",
        "conflicting_syndrome_vitals",
        "vitals_only",
        "population_boundaries",
        "unknown_missing_vitals",
        "acronym_morphology_variants",
        "corpus_poisoned_chunk",
        "near_duplicate_versions",
        "scale_latency",
    }
    assert required_families.issubset(families), f"Missing families: {required_families - families}"


def test_eval_retriever_parity_with_production() -> None:
    """WP5 Gate: Evaluation harness uses the exact same RetrievalService configuration as prod."""
    from eval.run_retrieval import get_eval_retrieval_service, run_retrieval_benchmark

    eval_service = get_eval_retrieval_service()
    prod_service = RetrievalService.create_default(get_data_dir())

    assert eval_service.corpus_hash == prod_service.corpus_hash
    assert eval_service.config_hash == prod_service.config_hash
    assert eval_service.index_version == prod_service.index_version

    metrics = run_retrieval_benchmark(write_reports=False)
    test_metrics = metrics["test"]
    assert test_metrics["wrong_protocol_rate"] == 0.0
    assert test_metrics["abstain_recall_hard_negatives"] == 1.0
    assert "recall_at_5_ci95" in test_metrics
    assert "mrr_ci95" in test_metrics
    assert "ndcg_at_5_ci95" in test_metrics
    assert "ece" in test_metrics
    assert metrics["deterministic"] is True
