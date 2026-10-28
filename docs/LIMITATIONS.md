# TriageRAG — System Limitations & Safety Disclaimers

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

This document explicitly enumerates the architectural, clinical, and data limitations of the TriageRAG prototype.

---

## 1. Unsourced Draft Ruleset

All clinical rules, interaction tables, vitals interlocks, and formulary limits shipped in `data/` were authored as a structural exercise (`content_origin: AGENT_DRAFT_UNSOURCED`, `source_status: PLACEHOLDER_UNRETRIEVED`, `verified: false`). They have **not** been validated or signed off by licensed clinicians, pharmacologists, or toxicologists. They represent hypotheses for system design and test validation only.

## 2. Circular Golden Recall

Golden set evaluation (`data/golden/shipped_ruleset_cases.yaml`) tests that the deterministic engine correctly and faithfully executes the shipped ruleset as authored. **It does not prove clinical correctness or real-world safety.** A 100% pass rate indicates software implementation fidelity against our rule specifications, not that the rules themselves represent sound medical practice.

## 3. Score Band is Not a Triage Decision

The early-warning scores calculated by TriageRAG (such as Adult/Paediatric EWS) provide physiological risk stratification only (e.g., RED, ORANGE, YELLOW, GREEN). **An early-warning score band is not a triage category or disposition decision.** Clinical triage systems like ESI (Emergency Severity Index) or Manchester Triage System incorporate resource utilization, chief complaint acuity, and clinician gestalt, which are outside the scope of this physiological score calculation.

## 4. Synthetic-Only Corpus

All bundled emergency protocols in `data/protocols_synthetic/` are original synthetic markdown documents authored to test algorithmic parsing, chunking, and lexical retrieval. They contain **no numeric doses** and must never be referenced for actual patient treatment.

## 5. Not a Medical Device

TriageRAG is an academic and engineering research software artifact. It has not undergone regulatory clearance, clinical trials, or conformity assessment under EU MDR, US FDA SaMD, or UK MHRA regulations. It is strictly prohibited from being used in any clinical environment or with real patient data.

## 6. Known Clinical Coverage Gaps

The deterministic ruleset intentionally covers only specific explicit rules. The system does not currently verify:
- Dose-dependent drug interactions outside specified ranges.
- Herbal, dietary, over-the-counter, or food-drug interactions.
- Drug-disease contraindications beyond explicitly authored vitals interlocks.
- Hepatic and renal impairment dose adjustments.
- Off-label dosing or drugs absent from the skeleton formulary.
- Full pharmacogenomic interactions.

Whenever an entity, history, or threshold is unmapped or missing, the system adheres to **Rule R2: Fail Closed**, emitting `SkippedCheck` and setting the verdict to `UNVERIFIED`.

## 7. Retrieval & Grounding Scope Limitations (ADR 0006)

- **Controlled Syndrome Vocabulary:** Protocol retrieval requires a recognized `suspected_syndrome` in `data/retrieval/vitals_flags.yaml` matching the patient's chronological `AgeGroup` population partition. Unmapped syndromes (e.g., `"kidney_stone"`) deterministically abstain (`AbstainCode.UNKNOWN_SYNDROME`) and trigger extractive/safety-only fallback (`llm_fallback_mode=True`).
- **Paediatric/Infant/Neonate Query Vitals Flags:** Where age-stratified vital-sign query flag thresholds are unverified (`status: NEEDS_SOURCE` in `data/retrieval/vitals_flags.yaml`), the query builder omits those vital flag tokens and records them in `skipped_flags` rather than inventing cutoffs (Rule R3).
- **Deterministic Support Heuristic vs. Full NLI:** `verify_step_support()` enforces verbatim substring matching, lexical overlap ($\ge 0.08$), child-node specificity, drug/alias mention, and action-cue polarity (`administer` vs. `withhold`), which catches citation laundering and polarity inversions deterministically offline but is not a substitute for human clinical guideline review.
