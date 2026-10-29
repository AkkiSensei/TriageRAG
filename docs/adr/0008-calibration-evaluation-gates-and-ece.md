# ADR 0008: Retrieval Evaluation Gates, Calibration Record, and ECE Target Policy (HD-3)

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Status
Accepted (2026-10-29) — Fix Gate G4 (`FG-06`, `FG-07`, `HD-3`)

## Context
Audit flags `FG-06` and `FG-07` identified two critical evaluation flaws:
1. **Benchmark Vacuity (`FG-06`):** The initial 160-case benchmark provided `suspected_syndrome` in 94 of 102 positive cases. With hard syndrome filtering narrowing candidate nodes to 3–5 items, Recall@5 = 100% was mathematically guaranteed by construction, masking vitals-only retrieval behaviour and ranking quality.
2. **Calibration Integrity & ECE Claims (`FG-07`, `HD-3`):** `data/retrieval/config.yaml` cited a phantom calibration run (`CALIB_WP5_SYNTHETIC_DEV_SPLIT_V1`) without committed grid records or an automated dev sweep script. Furthermore, Expected Calibration Error (ECE ≈ 0.15–0.19) was labeled with an unqualified "PASS" in reports despite having no formal clinical calibration baseline or pre-agreed acceptance threshold.

## Decision
1. **Independent Evaluation Dataset & Frozen Labels (`FG-06`):**
   - The evaluation corpus was expanded to 224 cases (136 dev [61%], 88 test [39%]), adding 44 vitals-only positive cases without clinician-supplied syndromes, 24 conflicting syndrome-vs-vitals cases, and 20 near-duplicate hard negatives.
   - All labels were authored under the fail-closed policy (`reviewed_by: "AGENT_AUTHORED_UNREVIEWED"`) and frozen in dedicated git commit `69fa952b4921e649450a49c46b9927fcca2fe53d` recorded in `eval/retrieval/LABELS_FROZEN_AT`.
   - CI asserts that `eval/retrieval/dataset.yaml` cannot change without an ADR (`test_dataset_matches_frozen_commit`).

2. **Node-Level Recall Metrics & Stratified Reporting (`FG-06`):**
   - Retrieval evaluation reports **Recall@1**, **Recall@3**, and **Recall@5** at node level, alongside MRR, nDCG@5, and 95% bootstrap confidence intervals (1,000 resamples).
   - Metrics are reported strictly stratified by **`syndrome_provided`** vs **`vitals_only`**.
   - Under Gate G2 / `HD-1`, all vitals flag thresholds are `status: NEEDS_SOURCE`, causing no vitals flags to fire. As a result, vitals-only queries fail closed to `EMPTY_QUERY` (Recall@1 = 0.0%). Per `fixgate_spec.md` and R10, this lower honest number is reported directly with its 95% CI rather than hidden behind an aggregate 100% figure.

3. **Deterministic Dev-Split Sweep (`eval/retrieval/calibrate.py`, `FG-07`):**
   - Grid sweep over candidate thresholds (`calibrated_threshold` ∈ [0.05, 0.25], `syndrome_inferred_threshold` ∈ [0.20, 0.50], `min_syndrome_margin` ∈ [0.10, 0.30]).
   - Emits an immutable JSON record to `eval/reports/calibration_run_<id>.json` capturing all trials, safety constraints, and selection rationale.
   - `data/retrieval/config.yaml::calibration_run_id` links directly to `CALIB_FG4_DEV_SWEEP_V1`.

4. **Safety Invariants and ECE Policy (`HD-3`):**
   - **Hard Safety Gates on Held-Out Test Split:**
     - `wrong_protocol_rate == 0.0` (zero wrong-syndrome protocol contamination permitted).
     - `abstain_recall_hard_negatives == 1.0` (100% of out-of-scope / adversarial distractors must abstain).
     - `syndrome_provided.recall_at_5 >= 95.0%` for clinician-confirmed syndromes.
     - `deterministic == True` across repeat runs.
   - **Permutation Sanity Check:** Shuffling node labels must collapse Recall@1 to near zero (< 0.05), verifying metric sensitivity.
   - **ECE Policy (`HD-3`):** Because synthetic data cannot establish real-world calibration, ECE is reported as an observational research metric. Reports and automated gates MUST NOT display an unqualified clinical "PASS" for ECE without prospective clinical trial data.

## Consequences
- Evaluation is falsifiable: changes that disrupt node ranking or protocol boundaries immediately fail CI.
- Full provenance chain connects production config (`config.yaml`) to the dev sweep record (`calibration_run_CALIB_FG4_DEV_SWEEP_V1.json`).
- Open clinical decisions (`HD-1`, `HD-3`) remain transparently recorded in `BACKLOG.md`.
