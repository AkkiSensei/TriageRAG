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
Evaluated across 224 clinical presentations (136 dev cases, 88 test cases) with calibrated fail-closed thresholding:

| Retrieval Arm | Backend Implementation | Test R@1 | Test R@5 | Test MRR | Test Latency (p95) | Wrong Protocol | Hard Negative Abstain |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Arm 1: BM25 Lexical** | BM25ClinicalIndex + ClinicalTokenizer (Default) | 39.29% | 73.21% | 0.5417 | 0.051 ms | **0.0%** | **100.0%** |
| **Arm 2: Char N-Gram Dense** | CharNgramRetriever (trigram TF-IDF) | 37.50% | 73.21% | 0.5045 | 0.074 ms | **0.0%** | **100.0%** |
| **Arm 3: Hybrid RRF** | HybridRRFRetriever (Reciprocal Rank Fusion) | **41.07%** | **73.21%** | **0.5491** | 0.097 ms | **0.0%** | **100.0%** |
| **Arm 4: Hybrid RRF + Rerank** | HybridRRFRetriever + LexicalOverlapReranker | **41.07%** | **73.21%** | **0.5491** | 0.215 ms | **0.0%** | **100.0%** |

**Stratified Performance (Syndrome-Provided Subset, N=41 Test):**
- **BM25 Recall@1:** 53.66% [95% CI: 39.02% - 68.29%]
- **BM25 Recall@3:** 100.0% [95% CI: 100.0% - 100.0%]
- **BM25 Recall@5:** 100.0% [95% CI: 100.0% - 100.0%]
- **BM25 MRR:** 0.7398 [95% CI: 0.6585 - 0.8252]
- **BM25 nDCG@5:** 0.8660 [95% CI: 0.8331 - 0.9009]

**Key Findings:**
1. Hybrid Reciprocal Rank Fusion (Arm 3) improves Test MRR from 0.5417 to 0.5491 while preserving the zero wrong-protocol rate (0.0%) and 100% hard-negative abstention recall.
2. In production API routing, Hybrid RRF can be selected via `TRIAGERAG_RETRIEVAL_BACKEND=hybrid_rrf` or request payload parameter `retrieval_backend="hybrid_rrf"`.
3. As disclosed in the UI and documentation, BM25 and lexical ranking scores reflect token matching against controlled vocabulary, not clinical probability or diagnostic certainty.

---

### 2.3 Scale Latency Benchmark (10,000 Chunks)
Synthetic scale corpus evaluated under simulated emergency triage load (`eval/reports/latency_benchmark.json`):

- **Corpus Size:** 10,000 chunks (3.8 MB text index).
- **Queries Evaluated:** 100 queries.
- **Index Build Time:** 566.72 ms.
- **BM25 Search Latency (Mean):** 4.259 ms.
- **BM25 Search Latency (p50):** 3.979 ms.
- **BM25 Search Latency (p95):** 6.687 ms (Target: <= 50.0 ms).
- **BM25 Search Latency (p99):** 7.507 ms.
- **Deterministic Math:** Sub-millisecond Decimal scoring for physiological vitals.

---

### 2.4 Mutation Testing Suite
Comprehensive logic and rule mutation testing (`eval/reports/mutation.json`):
- **Rule Mutants Injected:** 12 (boundary inversions, missing vital overrides).
- **Rule Mutants Killed:** **12 / 12 (100.0%)**
- **Code Mutants Injected:** 40 (unit conversion omissions, fail-closed bypasses, severity downgrades).
- **Code Mutants Killed:** **40 / 40 (100.0%)**
- **Total Mutants Killed:** **52 / 52 (100.0%)**
- **Mutation Score:** **1.00 (100.0%)**

---

### 2.5 Adversarial Prompt Injection Defense
Evaluated across 19 adversarial scenarios simulating prompt injection, instruction breakout, and toxic payloads (`eval/reports/adversarial.json`):

- **Scenarios Evaluated:** **19 / 19 passed (100.0%)**
- **Invariance Score:** **100.0%**
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

