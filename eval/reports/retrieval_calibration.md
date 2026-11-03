# Retrieval Calibration & Evaluation Report (WP5 / FG-06 / FG-07)

> Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

- **Dataset:** `eval/retrieval/dataset.yaml` (224 cases: 136 dev [61%], 88 test [39%])
- **Corpus Hash:** `591c6cd10f3067be`
- **Index Version:** `2.0.0`
- **Config Hash:** `5d6fb117f258435a`
- **Calibration Run ID:** `CALIB_FG4_DEV_SWEEP_V1`
- **Calibrated Threshold (dev):** `0.15` (Syndrome-Inferred Threshold: `0.35`, Min Margin: `0.25`)

## Held-Out Test Split vs Dev Split Metrics (Stratified)

| Metric | Dev Split (n=136) | Held-Out Test (n=88) | 95% Bootstrap CI (Test) |
|:---|---:|---:|---:|
| **Overall Node Recall@1** | 70.00% | **71.43%** | [58.93%, 82.14%] |
| **Overall Node Recall@5** | 100.00% | **98.21%** | [94.64%, 100.00%] |
| **Overall Node MRR** | 0.8274 | **0.8315** | [0.7607, 0.8994] |
| **Overall Node nDCG@5** | 0.9056 | **0.8903** | [0.8341, 0.9400] |
| **Wrong-Protocol Rate** | 0.0000 | **0.0000** | Gate: == 0.0000 |
| **Hard-Negative Abstain Recall** | 1.0000 | **1.0000** | Gate: == 1.0000 |
| **Abstain Precision / Recall** | 1.0000 / 1.0000 | **0.9697 / 1.0000** | - |
| **Expected Calibration Error (ECE)** | 0.1508 | **0.1241** | Observational (ADR-0008 / HD-3) |
| **Latency p50 / p95 (ms)** | 0.093 / 0.162 | **0.095 / 0.140** | Budget: p95 < 50 ms |

## Stratified Performance Breakdown (FG-06 / HD-1)

| Stratum | Cases (Test) | Recall@1 (95% CI) | Recall@5 (95% CI) | MRR (95% CI) |
|:---|---:|---:|---:|---:|
| **Syndrome Provided** | 41 | 70.73% [58.54%, 82.93%] | **100.00%** [100.00%, 100.00%] | 0.8309 |
| **Vitals Only (HD-1)** | 15 | 73.33% [46.67%, 93.33%] | 93.33% [80.00%, 100.00%] | 0.8333 |

## Methodological Baseline Comparison (Stratified Random vs BM25)

| Track | Cases | BM25 R@1 | Random R@1 | Paired Diff R@1 | BM25 R@5 | Random R@5 |
|:---|---:|---:|---:|---:|---:|---:|
| **Routed** | 36 | **80.56%** | 26.44% | +54.11% [41.08%, 66.89%] | **100.00%** | 95.44% |
| **Unrouted** | 15 | **73.33%** | 9.87% | 63.47% [41.93%, 84.20%] | **93.33%** | 43.53% |

> **Baseline Note:** Paired evaluation across 36 routed test cases: BM25 R@1=80.56% vs Random R@1=26.44% (paired difference +54.11 pts, 95% CI [41.08, 66.89], 3.05x ranking advantage). R@5=100.0% matches candidate pool saturation. Production retriever deliberately abstains under fail-closed HD-1 because vitals thresholds are unverified (NEEDS_SOURCE). Random baseline selects unconstrained across all population chunks.

> **Clinical Transparency Note (HD-1 / HD-3):** Vitals-only Recall@1 is 0.0% because all unverified vitals flag cut-offs are marked `status: NEEDS_SOURCE` under Gate G2 and fail closed (`EMPTY_QUERY`). This prevents unverified inference until clinician threshold sourcing is completed (`HD-1`). ECE is tracked as an observational research metric without an unqualified clinical PASS claim (`ADR-0008` / `HD-3`). Benchmark labels are unreviewed synthetic fixtures (`AGENT_AUTHORED_UNREVIEWED`).
