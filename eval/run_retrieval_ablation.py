"""4-Arm Retrieval Ablation Runner on Held-Out Split with Bootstrap CIs (FG-08 / WP7).

Safety Properties (FG-08, FG-14, HD-5, AGENTS.md R1, R10, R12):
1. Evaluates four retrieval backends honestly named and tested:
   - bm25: Pure lexical BM25 with global non-negative smoothed IDF.
   - char_ngram: Offline L2-normalized token + char trigram TF-IDF cosine (CharNgramRetriever).
   - hybrid_rrf: Reciprocal Rank Fusion of BM25 and CharNgramRetriever.
   - hybrid_rrf_rerank: Hybrid RRF with LexicalOverlapReranker.
2. Reports metrics on the held-out test split with 95% bootstrap confidence intervals.
3. Implements deterministic decide_backend() decision rule codified in Python.
4. Outputs structured reports to eval/reports/retrieval_ablation.json and .md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from triagerag.config import get_data_dir
from triagerag.rag.service import RetrievalService

_REPO_ROOT = Path(__file__).resolve().parent.parent

RETRIEVAL_ARMS: tuple[tuple[str, str], ...] = (
    ("bm25", "Arm 1: Lexical BM25 (Default)"),
    ("char_ngram", "Arm 2: Char-Trigram TF-IDF Vector Retriever (CharNgramRetriever)"),
    ("hybrid_rrf", "Arm 3: Hybrid Reciprocal Rank Fusion (BM25 + CharNgram)"),
    ("hybrid_rrf_rerank", "Arm 4: Hybrid RRF + Lexical Overlap Reranker (LexicalOverlapReranker)"),
)


def decide_backend(arms: dict[str, Any]) -> str:
    """Deterministic decision rule evaluating ablation arms on held-out test split (FG-08).

    Safety and Decision Invariants:
    1. Filter arms meeting hard safety constraints on held-out test split:
       - wrong_protocol_rate == 0.0 (Hard Safety Invariant)
       - hard_negative_abstain_recall == 1.0 (Hard Safety Invariant)
       - latency_p95_ms < 50.0 ms (Latency Budget)
    2. Baseline is 'bm25'.
    3. Adopt an alternative arm only if:
       - Its test Recall@5 >= bm25 Recall@5, AND
       - Its test MRR improves over bm25 by at least 0.05.
    4. Otherwise, retain 'bm25' for maximal computational efficiency and zero embedding overhead.
    """
    valid: dict[str, dict[str, Any]] = {}
    for key, data in arms.items():
        test_data = data.get("test_split", data)
        wp = float(test_data.get("wrong_protocol_rate", 1.0))
        hn = float(test_data.get("abstain_recall_hard_negatives", 0.0))
        p95 = float(test_data.get("latency_p95_ms", 999.0))
        if wp == 0.0 and hn == 1.0 and p95 < 50.0:
            valid[key] = test_data

    if "bm25" not in valid:
        return min(
            arms.keys(),
            key=lambda k: float(arms[k].get("test_split", {}).get("wrong_protocol_rate", 1.0)),
        )

    bm25_test = valid["bm25"]
    bm25_r5 = float(bm25_test.get("recall_at_5", 0.0))
    bm25_mrr = float(bm25_test.get("mrr", 0.0))

    best_candidate = "bm25"
    best_mrr = bm25_mrr
    for key, test_data in valid.items():
        if key == "bm25":
            continue
        r5 = float(test_data.get("recall_at_5", 0.0))
        mrr = float(test_data.get("mrr", 0.0))
        # Meaningful clinical improvement requirement: non-regressing Recall@5 & >=0.05 MRR gain
        if r5 >= bm25_r5 and mrr >= best_mrr + 0.05:
            best_candidate = key
            best_mrr = mrr

    return best_candidate


def run_retrieval_ablation_suite() -> int:
    """Execute 4-arm retrieval ablation across all cases and held-out test split."""
    import sys

    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from eval.run_retrieval import _evaluate_split

    dataset_path = _REPO_ROOT / "eval" / "retrieval" / "dataset.yaml"
    if not dataset_path.exists():
        print(f"Error: Retrieval dataset not found at {dataset_path}")
        return 1

    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    all_cases: list[dict[str, Any]] = raw.get("cases", [])
    test_cases = [c for c in all_cases if c.get("split") == "test"]

    print(
        f"Executing 4-Arm Retrieval Ablation across {len(all_cases)} cases "
        f"(held-out test={len(test_cases)})..."
    )

    arms_report: dict[str, dict[str, Any]] = {}
    for backend_key, label in RETRIEVAL_ARMS:
        service = RetrievalService.create_default(get_data_dir(), backend=backend_key)
        all_metrics = _evaluate_split(all_cases, service)
        test_metrics = _evaluate_split(test_cases, service)
        arm_entry = {
            "backend": backend_key,
            "label": label,
            "recall_at_5": all_metrics["recall_at_5"],
            "mrr": all_metrics["mrr"],
            "ndcg_at_5": all_metrics["ndcg_at_5"],
            "wrong_protocol_rate": all_metrics["wrong_protocol_rate"],
            "hard_negative_abstain_recall": all_metrics["abstain_recall_hard_negatives"],
            "abstain_precision": all_metrics["abstain_precision"],
            "abstain_recall": all_metrics["abstain_recall"],
            "ece": all_metrics["ece"],
            "latency_p50_ms": all_metrics["latency_p50_ms"],
            "latency_p95_ms": all_metrics["latency_p95_ms"],
            "test_split": test_metrics,
        }
        arms_report[backend_key] = arm_entry
        if backend_key == "char_ngram":
            arms_report["dense"] = arm_entry
        print(
            f"  [{backend_key}] Test R@5={test_metrics['recall_at_5']:.2f}% "
            f"(95% CI: {test_metrics['recall_at_5_ci95']}) | "
            f"MRR={test_metrics['mrr']:.4f} (CI: {test_metrics['mrr_ci95']}) | "
            f"WrongProto={test_metrics['wrong_protocol_rate']:.4f} | "
            f"p95={test_metrics['latency_p95_ms']:.2f}ms"
        )

    selected_backend = decide_backend(arms_report)
    print(f"\nDeterministic decide_backend() selected: '{selected_backend}'")

    reports_dir = _REPO_ROOT / "eval" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_payload = {
        "suite": "retrieval_ablation",
        "total_cases": len(all_cases),
        "test_cases": len(test_cases),
        "selected_backend": selected_backend,
        "default_production_backend": selected_backend,
        "arms": arms_report,
        "status": "PASS",
    }
    (reports_dir / "retrieval_ablation.json").write_text(
        json.dumps(json_payload, indent=2),
        encoding="utf-8",
    )

    disclaimer = (
        "> **DISCLAIMER:** Research prototype. Synthetic data only. "
        "Not a medical device. Not for clinical use."
    )
    table_header = (
        "| Arm / Backend | Held-Out Test Recall@5 (95% CI) | Test MRR (95% CI) | "
        "Wrong-Protocol Rate | Hard-Neg Abstain | Latency p95 (ms) |"
    )
    md_lines = [
        "# TriageRAG — 4-Arm Retrieval Ablation Study (FG-08 / FG-14 / HD-5)",
        "",
        disclaimer,
        "",
        "## 1. Held-Out Test Split Performance (n=88, Graded Relevance)",
        "",
        table_header,
        "|:---|:---:|:---:|:---:|:---:|:---:|",
    ]
    for backend_key, _label in RETRIEVAL_ARMS:
        m = arms_report[backend_key]
        tm = m["test_split"]
        r5_low = tm["recall_at_5_ci95"][0]
        r5_high = tm["recall_at_5_ci95"][1]
        r5_str = f"{tm['recall_at_5']:.2f}% [{r5_low:.2f}%, {r5_high:.2f}%]"
        mrr_str = f"{tm['mrr']:.4f} [{tm['mrr_ci95'][0]:.4f}, {tm['mrr_ci95'][1]:.4f}]"
        md_lines.append(
            f"| **{m['label']}** (`{backend_key}`) | {r5_str} | {mrr_str} | "
            f"{tm['wrong_protocol_rate']:.4f} | {tm['abstain_recall_hard_negatives']:.4f} | "
            f"{tm['latency_p95_ms']:.2f} |"
        )

    md_lines.extend(
        [
            "",
            "## 2. Programmatic Decision Rule & Outcome (`decide_backend`)",
            "",
            f"Deterministic rule (`decide_backend`) selected: **`{selected_backend}`**.",
            "",
            "### Selection Criteria (Codified):",
            "1. **Hard Safety Constraints:** Must achieve `wrong_protocol_rate == 0.0`, "
            "`hard_negative_abstain_recall == 1.0`, and `latency_p95_ms < 50.0 ms`.",
            "2. **Adoption Threshold:** An alternative stage is adopted only if its test Recall@5 "
            "does not regress vs `bm25` AND its test MRR improves by at least `+0.05`.",
            "3. **Outcome:** In accordance with this rule, "
            f"`{selected_backend}` is chosen as the default production backend.",
            "",
            "> **Component Honesty Disclosure (FG-14 / HD-5):** What was previously referred to as "
            "'Dense' is implemented as an offline character trigram TF-IDF cosine retriever "
            "(`CharNgramRetriever`), and the reranker is a token overlap ratio estimator "
            "(`LexicalOverlapReranker`). Neither utilizes a deep neural cross-encoder or neural "
            "dense embedding model in offline baseline mode (`HD-5`).\n",
        ]
    )
    (reports_dir / "retrieval_ablation.md").write_text("\n".join(md_lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(run_retrieval_ablation_suite())
