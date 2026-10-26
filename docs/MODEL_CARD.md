# TriageRAG — Model Card & System Evaluation

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## System Overview

TriageRAG decouples deterministic decision logic from statistical language generation:
- **Deterministic Engine:** Python algorithms execute physiological early-warning scoring, drug-drug interaction interlocks, allergy cross-reactivity mapping, and dosage verification.
- **Language Model:** Generates proposed plan drafts (`PlanDraft`) with required citations against retrieved synthetic protocol chunks.
- **Machine Verifier:** Validates that proposed actions adhere to deterministic engine alerts, contain verbatim citations, and do not introduce ungrounded medication entities.

## Intended Use

- **Intended Purpose:** Algorithmic research on safety-critical LLM verification architectures in healthcare scenarios.
- **Out-of-Scope:** Clinical deployment, emergency department operational triage, prescribing, or any real-world patient care.

## Primary Limitations

1. **Synthetic Training & Corpus:** Protocols and golden cases are entirely synthetic.
2. **Deterministic Ruleset Gaps:** Drug interaction coverage is limited to explicit YAML rule entries.
3. **Language Model Grounding:** LLM generation can hallucinate instructions or cite inapplicable spans; all steps must pass through the `plan_verifier` and will be marked `BLOCKED_STRUCK_THROUGH` or `CITATION_UNVERIFIED` upon failure.
