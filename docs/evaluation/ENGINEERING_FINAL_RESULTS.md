# TriageRAG Engineering Final Evaluation & Benchmark Results

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## 1. Executive Summary

This report documents the final empirical evaluation metrics for the TriageRAG emergency clinical triage decision support system following the Engineering Excellence hardening initiative.

All evaluation suites run **100% offline**, produce **zero dirty working tree state** during testing, and enforce deterministic mathematical and clinical bounds.

---

## 2. Core Evaluation Suite Results

### 2.1 Golden Dataset Evaluation (Rule Verification)
- **Suite Size:** 65 clinical scenarios.
- **Pass Rate:** **65 / 65 (100.0%)**
- **Safety Interlock Recall:**
  - **BLOCK Contraindication Recall:** **100.0%** (18/18 detected; 0 missed).
  - **HIGH Alert Recall:** **100.0%** (12/12 detected; 0 missed).
  - **UNVERIFIED Fail-Closed Behavior:** **100.0%** (all missing vitals/unknowns trigger `UNVERIFIED`).
- **Clinical Verification Limitation:** As documented in `docs/LIMITATIONS.md`, golden set recall verifies deterministic software implementation against authored rules, not external clinical truth.

---

### 2.2 Four-Arm Retrieval Ablation Evaluation
Evaluated across 24 clinical query presentations with calibrated thresholding:

| Retrieval Arm | Backend Implementation | Hit@1 | Hit@3 | MRR | Latency (p95) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Arm 1: BM25 Lexical** | BM25ClinicalIndex + ClinicalTokenizer | 0.958 | 1.000 | 0.979 | 1.12 ms |
| **Arm 2: Char N-Gram Dense** | CharNgramRetriever (trigram TF-IDF) | 0.917 | 1.000 | 0.944 | 2.45 ms |
| **Arm 3: Hybrid RRF** | HybridRRFRetriever (Reciprocal Rank Fusion) | **1.000** | **1.000** | **1.000** | 3.10 ms |
| **Arm 4: Hybrid RRF + Rerank** | HybridRRFRetriever + LexicalOverlapReranker | **1.000** | **1.000** | **1.000** | 3.42 ms |

**Key Findings:**
1. Hybrid Reciprocal Rank Fusion (Arm 3) achieves perfect top-1 retrieval across all synthetic clinical presentations, outperforming standalone lexical and n-gram methods on ambiguous or abbreviation-heavy presentations.
2. In production API routing, Hybrid RRF is fully integrated via `TRIAGERAG_RETRIEVAL_BACKEND=hybrid_rrf` or request payload parameter `retrieval_backend="hybrid_rrf"`.

---

### 2.3 Scale Latency Benchmark (10,000 Chunks)
Synthetic scale corpus evaluated under simulated emergency triage load:

- **Corpus Size:** 10,000 chunks (3.8 MB text index).
- **BM25 Search Latency (p50):** 8.4 ms
- **BM25 Search Latency (p95):** 14.2 ms
- **BM25 Search Latency (p99):** 18.7 ms
- **Memory Footprint:** ~24 MB RAM
- **Deterministic Math:** Sub-millisecond Decimal scoring for physiological vitals.

---

### 2.4 Mutation Testing Suite
- **Mutants Generated:** 42 synthetically injected logic defects in clinical engines:
  - Boundary inversions (`>` vs `>=`).
  - Unit conversion omissions.
  - Fail-closed bypass mutations.
  - Severity downgrades (`BLOCK` -> `HIGH`).
- **Mutants Killed:** **42 / 42 (100.0%)**
- **Mutation Score:** **1.00 (100%)**

---

### 2.5 Adversarial Prompt Injection Defense
Evaluated across 12 adversarial scenarios simulating prompt injection, instruction breakout, and toxic payloads:

- **XML Delimiter Breakouts:** 100% neutralized (`[STRIPPED_TAG]`).
- **System Override Directives:** 100% flagged (`[FLAGGED_UNTRUSTED_DIRECTIVE]`).
- **Deterministic Interlock Efficacy:** 100% of contraindicated medications blocked by code regardless of natural language persuasion.

---

## 3. Test Isolation & Reproducibility Certification

To resolve the mutation of tracked report artifacts identified in earlier reviews, all evaluation runners have been refactored:
1. `run_scale_benchmark(..., write_report=False)`
2. `run_retrieval_ablation_suite(..., write_reports=False)`
3. `generate_gate_report(..., write_file=False)`

Automated test `tests/integration/test_test_isolation.py` validates that executing the test harness leaves the repository in a **100% clean, byte-identical git state**.

