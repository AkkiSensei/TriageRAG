"""10,000-chunk synthetic scale latency benchmark for TriageRAG retrieval (WP9).

Safety Property (RAG-16, Rule R12):
Verifies that BM25ClinicalIndex scales to 10,000 protocol decision chunks with
lexical search p95 latency strictly under 50 ms on CPU, and outputs a structured
JSON report to eval/reports/latency_benchmark.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.index import BM25ClinicalIndex

REPO_ROOT = Path(__file__).resolve().parent.parent

DISCLAIMER = "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."


def _generate_synthetic_10k_corpus(target_chunks: int = 10000) -> list[ProtocolChunk]:
    """Deterministically generate a 10,000-chunk synthetic protocol corpus."""
    syndromes = [
        ("chest_pain", "adult"),
        ("sepsis", "adult"),
        ("anaphylaxis", "adult"),
        ("asthma", "adult"),
        ("stroke", "adult"),
        ("paediatric_sepsis", "paediatric"),
    ]
    clinical_phrases = [
        (
            "IF patient presents with acute chest pain and hypotension "
            "THEN obtain immediate 12-lead ECG and withhold nitrates"
        ),
        (
            "IF suspected sepsis with hyperlactataemia and tachycardia "
            "THEN initiate broad-spectrum intravenous antimicrobials"
        ),
        (
            "IF anaphylaxis with stridor hypoxia or hypotension "
            "THEN administer intramuscular adrenaline and high-flow oxygen"
        ),
        (
            "IF acute severe asthma exacerbation with silent chest or hypercapnia "
            "THEN administer nebulised bronchodilators"
        ),
        (
            "IF acute focal neurological deficit with facial droop or arm drift "
            "THEN perform urgent non-contrast CT head"
        ),
        (
            "IF paediatric fever with prolonged capillary refill and lethargy "
            "THEN escalate to senior paediatrician"
        ),
    ]
    chunks: list[ProtocolChunk] = []
    for idx in range(target_chunks):
        syn, pop = syndromes[idx % len(syndromes)]
        phrase = clinical_phrases[idx % len(clinical_phrases)]
        doc_id = f"SYN-SCALE-{syn.upper()}-{idx // 20:04d}"
        section = f"Section {idx % 5 + 1} Clinical Assessment"
        text = f"{phrase} [variant_node_{idx}]"
        chunks.append(
            ProtocolChunk(
                doc_id=doc_id,
                section=section,
                chunk_id=f"{doc_id}#node_{idx:05d}",
                parent_id=f"{doc_id}#sec_{idx % 5:02d}",
                text=text,
                population=pop,
                syndrome=syn,
                synthetic=True,
                version="1.0.0",
            )
        )
    return chunks


def run_scale_benchmark(
    target_chunks: int = 10000,
    num_queries: int = 100,
    output_path: Path | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    """Run lexical retrieval latency benchmark on a 10,000-chunk synthetic corpus."""
    chunks = _generate_synthetic_10k_corpus(target_chunks=target_chunks)

    t0_build = time.perf_counter()
    index = BM25ClinicalIndex(chunks)
    build_ms = (time.perf_counter() - t0_build) * 1000.0

    queries = [
        ("chest_pain hypotension tachycardia", "adult", "chest_pain"),
        ("sepsis fever hypotension hyperlactataemia", "adult", "sepsis"),
        ("anaphylaxis hypoxia stridor hypotension", "adult", "anaphylaxis"),
        ("asthma hypoxia tachypnoea wheeze", "adult", "asthma"),
        ("stroke focal deficit hypertension", "adult", "stroke"),
        ("paediatric_sepsis fever tachycardia", "paediatric", "paediatric_sepsis"),
    ]

    # Warmup
    for q_text, pop, syn in queries[:2]:
        index.search(query=q_text, population=pop, top_k=5, syndrome=syn)

    latencies_ms: list[float] = []
    for i in range(num_queries):
        q_text, pop, syn = queries[i % len(queries)]
        t0 = time.perf_counter()
        res = index.search(query=q_text, population=pop, top_k=5, syndrome=syn)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        assert len(res) == 5
        latencies_ms.append(dt_ms)

    latencies_sorted = sorted(latencies_ms)
    p50_idx = int(0.50 * (len(latencies_sorted) - 1))
    p95_idx = int(0.95 * (len(latencies_sorted) - 1))
    p99_idx = int(0.99 * (len(latencies_sorted) - 1))

    report: dict[str, Any] = {
        "disclaimer": DISCLAIMER,
        "total_chunks": len(chunks),
        "num_queries": num_queries,
        "index_build_ms": round(build_ms, 2),
        "mean_latency_ms": round(sum(latencies_ms) / len(latencies_ms), 3),
        "p50_latency_ms": round(latencies_sorted[p50_idx], 3),
        "p95_latency_ms": round(latencies_sorted[p95_idx], 3),
        "p99_latency_ms": round(latencies_sorted[p99_idx], 3),
        "target_p95_ms": 50.0,
        "passed": latencies_sorted[p95_idx] < 50.0,
    }

    if write_report:
        dest = output_path or (REPO_ROOT / "eval" / "reports" / "latency_benchmark.json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


if __name__ == "__main__":
    res = run_scale_benchmark()
    print(
        f"10k-Chunk Scale Benchmark: build={res['index_build_ms']}ms, "
        f"p50={res['p50_latency_ms']}ms, p95={res['p95_latency_ms']}ms "
        f"(target < {res['target_p95_ms']}ms) -> {'PASS' if res['passed'] else 'FAIL'}"
    )
    if not res["passed"]:
        sys.exit(1)
