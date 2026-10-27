# TriageRAG - Ablation Study Report

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device.
> Not for clinical use.

> **CRITICAL CAVEAT (Section 13):**
> With FakeLLM this validates the verification harness, not real-model quality.

## 1. Study Overview

The ablation study compares three architectural configurations of the pipeline:
- **Arm A (Naive Free-Text / LLM-Only):** Direct generative drafting without
  protocol retrieval grounding or deterministic clinical safety verification.
- **Arm B (RAG Draft Without Verification):** Guideline retrieval augments prompt,
  but machine verification and Pass 2 safety checks are bypassed.
- **Arm C (Full Pipeline):** Full TriageRAG architecture combining Pass 1 baseline,
  BM25 retrieval, structured LLM drafting, and deterministic machine verification.

## 2. Safety Metric Results

| Safety Metric | Arm A (LLM Only) | Arm B (RAG Draft Only) | Arm C (Full) | Target |
|:---|:---:|:---:|:---:|:---:|
| **Total Steps Evaluated** | 4 | 4 | 4 | - |
| **BLOCK Drugs Present in Active Plan** | **1** | **1** | **0** | **0** |
| **Missed HIGH Drug-Safety Alerts** | **1** | **1** | **0** | **0** |
| **Magnitude Dosing Errors Unflagged** | **1** | **1** | **0** | **0** |
| **Uncited / Hallucinated Steps Approved** | **4** | **1** | **0** | **0** |

## 3. Analysis of Findings

1. **Rule R11 (No Override of BLOCK):** In Arms A and B, contraindicated medications
   leak into active recommendations because generative models do not enforce hard
   interlocks. In Arm C, deterministic Pass 2 checks reliably intercept all BLOCK alerts.

2. **Rule R8 (Decimal Math & Magnitude Guards):** Arm C pure Decimal dose verification
   catches ten-fold dosing excursions and flags them as unverified/aberrant.

3. **Rule R3 & Section 10 (Grounding & Verbatim Citations):** Fabricated or hallucinated
   citations in Arms A and B go undetected. Arm C validates lexical overlap and verbatim
   substring matching against ingested synthetic chunks.
