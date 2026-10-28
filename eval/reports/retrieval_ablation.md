# TriageRAG — 4-Arm Retrieval Ablation Study (RAG-08)

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## 1. Comparative Retrieval Arms (160 Cases, Node-Level Graded Relevance)

| Arm / Backend | Recall@5 | MRR | nDCG@5 | Wrong-Protocol Rate | Hard-Neg Abstain Recall | ECE | Latency p95 (ms) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Arm 1: Lexical BM25 (Default)** (`bm25`) | 100.00% | 0.8840 | 0.9242 | 0.0000 | 1.0000 | 0.1531 | 12.77 |
| **Arm 2: Dense Vector Cosine (Char 3-gram + Token TF-IDF)** (`dense`) | 99.02% | 0.8873 | 0.9174 | 0.0000 | 1.0000 | 0.3575 | 15.97 |
| **Arm 3: Hybrid Reciprocal Rank Fusion (BM25 + Dense)** (`hybrid_rrf`) | 96.08% | 0.8578 | 0.8973 | 0.0000 | 1.0000 | 0.1460 | 21.44 |
| **Arm 4: Hybrid RRF + Lexical Overlap Reranker** (`hybrid_rrf_rerank`) | 100.00% | 0.8971 | 0.9297 | 0.0000 | 1.0000 | 0.1255 | 17.63 |

## 2. Architectural Decision & Findings

1. **Query-Time Hard Filters Dominate Safety:** Across all four arms
   (`bm25`, `dense`, `hybrid_rrf`, and `hybrid_rrf_rerank`), query-time
   hard population and hard syndrome filtering ensure **0.00% Wrong-Protocol Rate**
   and **100.0% Hard-Negative Abstain Recall**.
2. **Lexical BM25 vs. Hybrid RRF:** Because clinical queries in TriageRAG are
   constructed deterministically from normalized syndrome codes and YAML-driven
   physiological flags (`hypotension`, `tachycardia`, `hypoxia`, `hypoglycemia`),
   lexical BM25 with non-negative smoothed IDF achieves **100.0% Recall@5** at the
   lowest computational overhead and zero external model dependencies.
3. **Default Backend Selection:** `BM25ClinicalIndex` (`bm25`) is retained as the
   deterministic offline default, while `DenseRetriever`, `HybridRRFRetriever`, and
   `hybrid_rrf_rerank` remain available behind `@runtime_checkable class Retriever`
   via `RetrievalService.create_default(backend=...)`.
