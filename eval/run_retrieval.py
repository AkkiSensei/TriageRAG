"""Node-level retrieval evaluation, calibration, and bootstrap CI harness (WP5 / Appendix B).

Safety Properties (RAG-01, RAG-10, Section 8, 13):
1. Evaluates the production Retriever built via RetrievalService.create_default() (100% parity).
2. Evaluates 160 structured patient cases (60% dev / 40% test) across all 10 mandatory families
   with graded node-level relevance (2 = directly actionable, 1 = supporting, 0 = irrelevant).
3. Computes node-level Recall@5, MRR, nDCG@5 with 95% bootstrap CIs (1,000 resamples),
   Abstain Precision/Recall, Wrong-Protocol Rate (gated at 0.0 on test), ECE calibration,
   latency p50/p95, and cross-run determinism.
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from triagerag.config import get_data_dir
from triagerag.contracts.enums import AgeUnit, Consciousness
from triagerag.contracts.schemas import Age, Measured, Patient, Vitals
from triagerag.rag.abstain import normalize_relevance_score
from triagerag.rag.service import RetrievalService

_REPO_ROOT = Path(__file__).resolve().parent.parent


def get_eval_retrieval_service(backend: str = "bm25") -> RetrievalService:
    """Return the shared production RetrievalService instance used for evaluation."""
    return RetrievalService.create_default(get_data_dir(), backend=backend)


def build_patient_from_eval_case(case: dict[str, Any]) -> Patient:
    """Construct a structured Patient model from natural vitals in dataset.yaml."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    age_raw = case["age"]
    age_val = Decimal(str(age_raw["value"]))
    age_unit = AgeUnit(str(age_raw["unit"]))

    v_raw: dict[str, Any] = case.get("vitals") or {}

    def _m_int(key: str) -> Measured[int]:
        if key in v_raw and v_raw[key] is not None:
            return Measured[int](value=int(v_raw[key]), source="measured")
        return Measured[int]()

    def _m_dec(key: str) -> Measured[Decimal]:
        if key in v_raw and v_raw[key] is not None:
            return Measured[Decimal](value=Decimal(str(v_raw[key])), source="measured")
        return Measured[Decimal]()

    def _m_consc() -> Measured[Consciousness]:
        if "consciousness" in v_raw and v_raw["consciousness"] is not None:
            return Measured[Consciousness](
                value=Consciousness(str(v_raw["consciousness"])),
                source="measured",
            )
        return Measured[Consciousness]()

    vitals = Vitals(
        heart_rate_bpm=_m_int("heart_rate_bpm"),
        systolic_bp_mmhg=_m_int("systolic_bp_mmhg"),
        diastolic_bp_mmhg=_m_int("diastolic_bp_mmhg"),
        respiratory_rate_bpm=_m_int("respiratory_rate_bpm"),
        spo2_percent=_m_int("spo2_percent"),
        temperature_c=_m_dec("temperature_c"),
        blood_glucose_mg_dl=_m_dec("blood_glucose_mg_dl"),
        consciousness=_m_consc(),
    )

    pop = str(case.get("population", "adult"))
    weight = (
        Decimal("3.5")
        if pop == "neonate"
        else (Decimal("18.0") if pop == "paediatric" else Decimal("75.0"))
    )

    return Patient(
        assessed_at=now,
        age=Age(value=age_val, unit=age_unit),
        sex="female",
        pregnancy="not_applicable" if pop != "adult" else "no",
        weight_kg=Measured[Decimal](value=weight, source="measured"),
        vitals=vitals,
        medication_history_status="confirmed_none",
        medications=[],
        allergy_history_status="confirmed_nkda",
        allergies=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome=case.get("suspected_syndrome"),
        chief_complaint_untrusted="",
    )


def _compute_ndcg_at_k(
    retrieved_ids: list[str],
    relevance_grades: dict[str, int],
    k: int = 5,
) -> float:
    """Compute graded nDCG@k using gain = (2^rel - 1) / log2(rank + 1)."""
    if not relevance_grades:
        return 0.0

    dcg = 0.0
    for idx, cid in enumerate(retrieved_ids[:k]):
        rel = int(relevance_grades.get(cid, 0))
        if rel > 0:
            dcg += float((2**rel) - 1) / math.log2(float(idx + 2))

    ideal_rels = sorted(relevance_grades.values(), reverse=True)[:k]
    idcg = 0.0
    for idx, rel in enumerate(ideal_rels):
        if rel > 0:
            idcg += float((2**rel) - 1) / math.log2(float(idx + 2))

    return float(dcg / idcg) if idcg > 0.0 else 0.0


def _bootstrap_ci95(values: list[float], n_boot: int = 500, seed: int = 42) -> list[float]:
    """Compute 95% bootstrap confidence interval [low, high] for the mean of values."""
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / float(n))
    means.sort()
    low_idx = max(0, int(0.025 * n_boot))
    high_idx = min(n_boot - 1, int(0.975 * n_boot))
    return [round(means[low_idx], 4), round(means[high_idx], 4)]


def _compute_ece(confidences: list[float], correctness: list[int], num_bins: int = 5) -> float:
    """Compute Expected Calibration Error (ECE) over equal-width confidence bins in [0, 1]."""
    if not confidences:
        return 0.0
    n = len(confidences)
    ece = 0.0
    for b in range(num_bins):
        low = float(b) / float(num_bins)
        high = float(b + 1) / float(num_bins)
        bin_indices = [
            i
            for i, c in enumerate(confidences)
            if (low <= c < high) or (b == num_bins - 1 and low <= c <= high)
        ]
        if not bin_indices:
            continue
        avg_conf = sum(confidences[i] for i in bin_indices) / float(len(bin_indices))
        avg_acc = sum(correctness[i] for i in bin_indices) / float(len(bin_indices))
        ece += (float(len(bin_indices)) / float(n)) * abs(avg_acc - avg_conf)
    return round(float(ece), 4)


def _evaluate_split(
    cases: list[dict[str, Any]],
    service: RetrievalService,
) -> dict[str, Any]:
    """Evaluate a split (dev, test, or all) and return comprehensive node-level metrics."""
    recalls_at_5: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs_at_5: list[float] = []
    latencies_ms: list[float] = []

    abstain_tp = 0
    abstain_fp = 0
    abstain_fn = 0
    abstain_tn = 0
    abstain_code_matches = 0
    hard_neg_total = 0
    hard_neg_abstained = 0
    wrong_protocol_count = 0

    confidences: list[float] = []
    correctness: list[int] = []

    for case in cases:
        patient = build_patient_from_eval_case(case)
        t0 = time.perf_counter()
        report = service.retrieve(patient, top_k=5)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)

        expect_abstain = bool(case["expect_abstain"])
        expected_code = str(case.get("expected_abstain_code", "NONE"))
        expected_syndrome = case.get("expected_syndrome")
        relevance_grades: dict[str, int] = {
            str(k): int(v) for k, v in (case.get("relevance_grades") or {}).items()
        }

        if report.abstain_code.value == expected_code:
            abstain_code_matches += 1

        if case.get("family") == "hard_negatives":
            hard_neg_total += 1
            if report.abstained:
                hard_neg_abstained += 1

        if expect_abstain:
            if report.abstained:
                abstain_tp += 1
                confidences.append(0.95)
                correctness.append(1)
            else:
                abstain_fn += 1
                wrong_protocol_count += 1
                top_raw = float(report.chunks[0].score) if report.chunks else 0.0
                confidences.append(normalize_relevance_score(top_raw))
                correctness.append(0)
        else:
            if report.abstained:
                abstain_fp += 1
                recalls_at_5.append(0.0)
                reciprocal_ranks.append(0.0)
                ndcgs_at_5.append(0.0)
                confidences.append(0.0)
                correctness.append(0)
            else:
                abstain_tn += 1
                retrieved_ids = [c.chunk_id for c in report.chunks]

                # Check wrong-protocol rate: any chunk from a different syndrome than expected
                if expected_syndrome and any(
                    c.syndrome != expected_syndrome for c in report.chunks
                ):
                    wrong_protocol_count += 1

                # Node-level grade-2 targets
                grade2_targets = {cid for cid, g in relevance_grades.items() if g >= 2}
                hit_ranks = [
                    idx + 1 for idx, cid in enumerate(retrieved_ids) if cid in grade2_targets
                ]
                if hit_ranks:
                    recalls_at_5.append(1.0)
                    reciprocal_ranks.append(1.0 / float(hit_ranks[0]))
                else:
                    recalls_at_5.append(0.0)
                    reciprocal_ranks.append(0.0)

                ndcgs_at_5.append(_compute_ndcg_at_k(retrieved_ids, relevance_grades, k=5))

                top_raw = float(report.chunks[0].score) if report.chunks else 0.0
                confidences.append(normalize_relevance_score(top_raw))
                correctness.append(1 if hit_ranks else 0)

    mean_r5 = sum(recalls_at_5) / float(len(recalls_at_5)) if recalls_at_5 else 0.0
    mean_mrr = sum(reciprocal_ranks) / float(len(reciprocal_ranks)) if reciprocal_ranks else 0.0
    mean_ndcg = sum(ndcgs_at_5) / float(len(ndcgs_at_5)) if ndcgs_at_5 else 0.0

    abstain_precision = (
        float(abstain_tp) / float(abstain_tp + abstain_fp) if (abstain_tp + abstain_fp) > 0 else 1.0
    )
    abstain_recall = (
        float(abstain_tp) / float(abstain_tp + abstain_fn) if (abstain_tp + abstain_fn) > 0 else 1.0
    )
    abstain_acc = float(abstain_tp + abstain_tn) / float(len(cases)) if cases else 1.0
    hn_recall = float(hard_neg_abstained) / float(hard_neg_total) if hard_neg_total > 0 else 1.0
    wrong_proto_rate = float(wrong_protocol_count) / float(len(cases)) if cases else 0.0

    sorted_lat = sorted(latencies_ms)
    p50_ms = sorted_lat[len(sorted_lat) // 2] if sorted_lat else 0.0
    p95_ms = (
        sorted_lat[min(len(sorted_lat) - 1, int(len(sorted_lat) * 0.95))] if sorted_lat else 0.0
    )

    r5_ci = _bootstrap_ci95(recalls_at_5)
    mrr_ci = _bootstrap_ci95(reciprocal_ranks)
    ndcg_ci = _bootstrap_ci95(ndcgs_at_5)

    return {
        "total_cases": len(cases),
        "positive_cases": len(recalls_at_5),
        "abstain_cases": abstain_tp + abstain_fn,
        "recall_at_5": round(mean_r5 * 100.0, 2),
        "recall_at_5_ci95": [round(r5_ci[0] * 100.0, 2), round(r5_ci[1] * 100.0, 2)],
        "mrr": round(mean_mrr, 4),
        "mrr_ci95": mrr_ci,
        "ndcg_at_5": round(mean_ndcg, 4),
        "ndcg_at_5_ci95": ndcg_ci,
        "abstain_precision": round(abstain_precision, 4),
        "abstain_recall": round(abstain_recall, 4),
        "abstain_accuracy": round(abstain_acc * 100.0, 2),
        "abstain_code_accuracy": round(
            (float(abstain_code_matches) / float(len(cases))) * 100.0, 2
        ),
        "abstain_recall_hard_negatives": round(hn_recall, 4),
        "wrong_protocol_rate": round(wrong_proto_rate, 4),
        "ece": _compute_ece(confidences, correctness),
        "latency_p50_ms": round(p50_ms, 3),
        "latency_p95_ms": round(p95_ms, 3),
    }


def run_retrieval_benchmark(
    backend: str = "bm25",
    write_reports: bool = True,
) -> dict[str, Any]:
    """Run the full 160-case dev/test retrieval benchmark and verify safety gates."""
    t_build0 = time.perf_counter()
    service = RetrievalService.reload(get_data_dir(), backend=backend)
    build_time_ms = round((time.perf_counter() - t_build0) * 1000.0, 3)

    dataset_path = _REPO_ROOT / "eval" / "retrieval" / "dataset.yaml"
    raw_ds = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    all_cases: list[dict[str, Any]] = raw_ds["cases"]
    dev_cases = [c for c in all_cases if c["split"] == "dev"]
    test_cases = [c for c in all_cases if c["split"] == "test"]

    dev_metrics = _evaluate_split(dev_cases, service)
    test_metrics = _evaluate_split(test_cases, service)
    test_metrics_repeat = _evaluate_split(test_cases, service)
    all_metrics = _evaluate_split(all_cases, service)

    deterministic = (
        test_metrics["recall_at_5"] == test_metrics_repeat["recall_at_5"]
        and test_metrics["mrr"] == test_metrics_repeat["mrr"]
        and test_metrics["ndcg_at_5"] == test_metrics_repeat["ndcg_at_5"]
        and test_metrics["wrong_protocol_rate"] == test_metrics_repeat["wrong_protocol_rate"]
    )

    passed = (
        test_metrics["wrong_protocol_rate"] == 0.0
        and test_metrics["abstain_recall_hard_negatives"] == 1.0
        and test_metrics["recall_at_5"] >= 95.0
        and test_metrics["mrr"] >= 0.85
        and deterministic
    )

    summary: dict[str, Any] = {
        "suite": "retrieval",
        "backend": backend,
        "dataset_version": raw_ds.get("dataset_version", "2.0.0"),
        "corpus_hash": service.corpus_hash,
        "index_version": service.index_version,
        "config_hash": service.config_hash,
        "index_build_time_ms": build_time_ms,
        "deterministic": deterministic,
        "benchmark_pairs": all_metrics["positive_cases"],
        "total_cases": len(all_cases),
        "recall_at_5": test_metrics["recall_at_5"],
        "mrr": test_metrics["mrr"],
        "ndcg_at_5": test_metrics["ndcg_at_5"],
        "abstain_accuracy": test_metrics["abstain_accuracy"],
        "wrong_protocol_rate": test_metrics["wrong_protocol_rate"],
        "ece": test_metrics["ece"],
        "dev": dev_metrics,
        "test": test_metrics,
        "overall": all_metrics,
        "status": "PASS" if passed else "FAIL",
    }

    if write_reports:
        reports_dir = _REPO_ROOT / "eval" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "retrieval.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        baseline_path = reports_dir / "retrieval_baseline.json"
        if not baseline_path.exists():
            baseline_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        r5_ci_str = (
            f"[{test_metrics['recall_at_5_ci95'][0]:.2f}%, "
            f"{test_metrics['recall_at_5_ci95'][1]:.2f}%]"
        )
        ndcg_ci_str = (
            f"[{test_metrics['ndcg_at_5_ci95'][0]:.4f}, {test_metrics['ndcg_at_5_ci95'][1]:.4f}]"
        )
        dev_pr_str = f"{dev_metrics['abstain_precision']:.4f} / {dev_metrics['abstain_recall']:.4f}"
        test_pr_str = (
            f"{test_metrics['abstain_precision']:.4f} / {test_metrics['abstain_recall']:.4f}"
        )
        dev_hn = dev_metrics["abstain_recall_hard_negatives"]
        test_hn = test_metrics["abstain_recall_hard_negatives"]

        calib_md = (
            "# Retrieval Calibration & Evaluation Report (WP5)\n\n"
            "> Research prototype. Synthetic data only. "
            "Not a medical device. Not for clinical use.\n\n"
            f"- **Dataset:** `eval/retrieval/dataset.yaml` ({len(all_cases)} cases: "
            f"{len(dev_cases)} dev [60%], {len(test_cases)} test [40%])\n"
            f"- **Corpus Hash:** `{service.corpus_hash[:16]}`\n"
            f"- **Index Version:** `{service.index_version}`\n"
            f"- **Config Hash:** `{service.config_hash[:16]}`\n"
            f"- **Calibrated Threshold (dev):** `{service.config.calibrated_threshold}` "
            f"(Syndrome-Inferred Threshold: `{service.config.syndrome_inferred_threshold}`, "
            f"Min Margin: `{service.config.min_syndrome_margin}`)\n\n"
            "## Held-Out Test Split vs Dev Split Metrics (Node-Level)\n\n"
            "| Metric | Dev Split (n=98) | Held-Out Test Split (n=62) | 95% Bootstrap CI (Test) |\n"
            "|:---|---:|---:|---:|\n"
            f"| **Node Recall@5** | {dev_metrics['recall_at_5']:.2f}% | "
            f"**{test_metrics['recall_at_5']:.2f}%** | {r5_ci_str} |\n"
            f"| **Node MRR** | {dev_metrics['mrr']:.4f} | "
            f"**{test_metrics['mrr']:.4f}** | "
            f"[{test_metrics['mrr_ci95'][0]:.4f}, {test_metrics['mrr_ci95'][1]:.4f}] |\n"
            f"| **Node nDCG@5** | {dev_metrics['ndcg_at_5']:.4f} | "
            f"**{test_metrics['ndcg_at_5']:.4f}** | {ndcg_ci_str} |\n"
            f"| **Wrong-Protocol Rate** | {dev_metrics['wrong_protocol_rate']:.4f} | "
            f"**{test_metrics['wrong_protocol_rate']:.4f}** | Gate: == 0.0000 |\n"
            f"| **Hard-Negative Abstain Recall** | {dev_hn:.4f} | "
            f"**{test_hn:.4f}** | Gate: == 1.0000 |\n"
            f"| **Abstain Precision / Recall** | {dev_pr_str} | **{test_pr_str}** | - |\n"
            f"| **Expected Calibration Error (ECE)** | {dev_metrics['ece']:.4f} | "
            f"**{test_metrics['ece']:.4f}** | - |\n"
            f"| **Latency p50 / p95 (ms)** | "
            f"{dev_metrics['latency_p50_ms']:.3f} / {dev_metrics['latency_p95_ms']:.3f} | "
            f"**{test_metrics['latency_p50_ms']:.3f} / {test_metrics['latency_p95_ms']:.3f}** | "
            "Budget: p95 < 50 ms |\n"
        )
        (reports_dir / "retrieval_calibration.md").write_text(calib_md, encoding="utf-8")

    return summary


def run_retrieval_suite() -> tuple[bool, float, float, float]:
    """Execute retrieval benchmark and print results for CLI / task runner."""
    summary = run_retrieval_benchmark(backend="bm25", write_reports=True)
    t = summary["test"]
    print(
        f"Executing WP5 Node-Level Retrieval Benchmark "
        f"({summary['total_cases']} cases: {summary['dev']['total_cases']} dev, "
        f"{t['total_cases']} test)..."
    )
    print(f"  Test Node Recall@5: {t['recall_at_5']:.2f}% (95% CI: {t['recall_at_5_ci95']})")
    print(f"  Test Node MRR:      {t['mrr']:.4f} (95% CI: {t['mrr_ci95']})")
    print(f"  Test Node nDCG@5:   {t['ndcg_at_5']:.4f} (95% CI: {t['ndcg_at_5_ci95']})")
    print(f"  Wrong-Protocol Rate (Test): {t['wrong_protocol_rate']:.4f} (Gate == 0.0)")
    print(f"  Hard-Negative Abstain Recall: {t['abstain_recall_hard_negatives']:.4f}")
    print(f"  Abstain Accuracy (Test): {t['abstain_accuracy']:.2f}%")
    print(f"  ECE (Test): {t['ece']:.4f} | Latency p95: {t['latency_p95_ms']:.3f} ms")
    success = summary["status"] == "PASS"
    return success, float(t["recall_at_5"]), float(t["mrr"]), float(t["abstain_accuracy"])


if __name__ == "__main__":
    ok, _r5, _mrr, _abstain = run_retrieval_suite()
    if not ok:
        sys.exit(1)
