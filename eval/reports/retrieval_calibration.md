# Retrieval Calibration & Evaluation Report (WP5)

> Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

- **Dataset:** `eval/retrieval/dataset.yaml` (160 cases: 98 dev [60%], 62 test [40%])
- **Corpus Hash:** `591c6cd10f3067be`
- **Index Version:** `2.0.0`
- **Config Hash:** `b1efcb3502204f8d`
- **Calibrated Threshold (dev):** `0.15` (Syndrome-Inferred Threshold: `0.35`, Min Margin: `0.25`)

## Held-Out Test Split vs Dev Split Metrics (Node-Level)

| Metric | Dev Split (n=98) | Held-Out Test Split (n=62) | 95% Bootstrap CI (Test) |
|:---|---:|---:|---:|
| **Node Recall@5** | 100.00% | **100.00%** | [100.00%, 100.00%] |
| **Node MRR** | 0.8995 | **0.8590** | [0.7821, 0.9316] |
| **Node nDCG@5** | 0.9305 | **0.9140** | [0.8776, 0.9476] |
| **Wrong-Protocol Rate** | 0.0000 | **0.0000** | Gate: == 0.0000 |
| **Hard-Negative Abstain Recall** | 1.0000 | **1.0000** | Gate: == 1.0000 |
| **Abstain Precision / Recall** | 1.0000 / 1.0000 | **1.0000 / 1.0000** | - |
| **Expected Calibration Error (ECE)** | 0.1577 | **0.1456** | - |
| **Latency p50 / p95 (ms)** | 11.629 / 14.119 | **11.128 / 11.651** | Budget: p95 < 50 ms |
