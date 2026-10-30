# Retrieval Calibration & Evaluation Report (WP5 / FG-06 / FG-07)

> Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

- **Dataset:** `eval/retrieval/dataset.yaml` (224 cases: 136 dev [61%], 88 test [39%])
- **Corpus Hash:** `591c6cd10f3067be`
- **Index Version:** `2.0.0`
- **Config Hash:** `ffb6892cc1524c60`
- **Calibration Run ID:** `CALIB_FG4_DEV_SWEEP_V1`
- **Calibrated Threshold (dev):** `0.15` (Syndrome-Inferred Threshold: `0.35`, Min Margin: `0.25`)

## Held-Out Test Split vs Dev Split Metrics (Stratified)

| Metric | Dev Split (n=136) | Held-Out Test (n=88) | 95% Bootstrap CI (Test) |
|:---|---:|---:|---:|
| **Overall Node Recall@1** | 24.44% | **39.29%** | [26.79%, 53.57%] |
| **Overall Node Recall@5** | 67.78% | **73.21%** | [60.71%, 83.93%] |
| **Overall Node MRR** | 0.4278 | **0.5417** | [0.4375, 0.6577] |
| **Overall Node nDCG@5** | 0.5712 | **0.6340** | [0.5339, 0.7323] |
| **Wrong-Protocol Rate** | 0.0000 | **0.0000** | Gate: == 0.0000 |
| **Hard-Negative Abstain Recall** | 1.0000 | **1.0000** | Gate: == 1.0000 |
| **Abstain Precision / Recall** | 0.6133 / 1.0000 | **0.6809 / 1.0000** | - |
| **Expected Calibration Error (ECE)** | 0.1447 | **0.1453** | Observational (ADR-0008 / HD-3) |
| **Latency p50 / p95 (ms)** | 0.017 / 0.092 | **0.019 / 0.060** | Budget: p95 < 50 ms |

## Stratified Performance Breakdown (FG-06 / HD-1)

| Stratum | Cases (Test) | Recall@1 (95% CI) | Recall@5 (95% CI) | MRR (95% CI) |
|:---|---:|---:|---:|---:|
| **Syndrome Provided** | 41 | 53.66% [39.02%, 68.29%] | **100.00%** [100.00%, 100.00%] | 0.7398 |
| **Vitals Only (HD-1)** | 15 | 0.00% [0.00%, 0.00%] | 0.00% [0.00%, 0.00%] | 0.0000 |

## Methodological Baseline Comparison (Stratified Random vs BM25)

| Track | Cases | BM25 R@1 | Random R@1 | Paired Diff R@1 | BM25 R@5 | Random R@5 |
|:---|---:|---:|---:|---:|---:|---:|
| **Routed** | 36 | **52.78%** | 26.44% | +26.33% [9.75%, 42.56%] | **100.00%** | 95.44% |
| **Unrouted** | 15 | **0.00%** | 9.87% | -9.87% [-15.00%, -5.93%] | **0.00%** | 43.53% |

> **Baseline Note:** Paired evaluation across 36 routed test cases: BM25 R@1=52.78% vs Random R@1=26.44% (paired difference +26.33 pts, 95% CI [9.75, 42.56], 2.0x ranking advantage). R@5=100.0% matches candidate pool saturation. Production retriever deliberately abstains under fail-closed HD-1 because vitals thresholds are unverified (NEEDS_SOURCE). Random baseline selects unconstrained across all population chunks.

> **Clinical Transparency Note (HD-1 / HD-3):** Vitals-only Recall@1 is 0.0% because all unverified vitals flag cut-offs are marked `status: NEEDS_SOURCE` under Gate G2 and fail closed (`EMPTY_QUERY`). This prevents unverified inference until clinician threshold sourcing is completed (`HD-1`). ECE is tracked as an observational research metric without an unqualified clinical PASS claim (`ADR-0008` / `HD-3`). Benchmark labels are unreviewed synthetic fixtures (`AGENT_AUTHORED_UNREVIEWED`).
