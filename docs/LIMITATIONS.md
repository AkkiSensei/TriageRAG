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

## 7. Retrieval & Grounding Scope Limitations (ADR 0006, ADR 0007, ADR 0008, ADR 0009)

- **Controlled Syndrome Vocabulary:** Protocol retrieval requires a recognized `suspected_syndrome` in `data/corpus/manifest.yaml` matching the patient's chronological `AgeGroup` population partition. Unmapped syndromes (e.g., `"kidney_stone"`) deterministically abstain (`AbstainCode.UNKNOWN_SYNDROME`) and trigger extractive/safety-only fallback (`llm_fallback_mode=True`).
- **Paediatric/Infant/Neonate Query Vitals Flags (HD-1):** All 50 vital-sign query flag thresholds in `data/retrieval/vitals_flags.yaml` are set to `status: NEEDS_SOURCE, threshold: null`. Retrieval without an explicit clinician `suspected_syndrome` fails closed to `UNVERIFIED` (`AbstainCode.NO_POPULATION_COVERAGE`). Zero thresholds are invented (Rule R3).
- **Inferred Syndrome Plan Safety (HD-4):** When a syndrome is inferred from vitals alone, any protocol steps generated cannot reach `APPROVED`; they carry `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION` and display a prominent warning banner.
- **Offline Stand-In Components (HD-5):** What was previously described as "Dense Retriever" is implemented offline as an L2-normalized token + character trigram TF-IDF cosine retriever (`CharNgramRetriever`), and the reranker is a token overlap ratio estimator (`LexicalOverlapReranker`). Neither utilizes a deep neural cross-encoder or transformer model in offline baseline mode.
- **ECE Research Diagnostic (HD-3):** Expected Calibration Error (observed test ECE = 0.1453) is reported as an observational research diagnostic under ADR 0008, not a clinical device calibration guarantee.

## 8. Open Human Decisions (HD-1 through HD-5)

The following architectural and clinical policy decisions require human clinical and product leadership sign-off and cannot be resolved by code alone (tracked in `BACKLOG.md`):
1. **HD-1:** Clinician-validated vital sign threshold values for age-stratified syndrome flags.
2. **HD-2:** Physiological discretization boundaries for paediatric age brackets (currently partitioned into neonate 0–28d, infant 29–365d, young child 1–5y, adolescent 6–17y).
3. **HD-3:** Acceptable ECE threshold and abstention-recall targets for clinical deployment.
4. **HD-4:** Policy for LLM protocol drafting under ambiguous or weakly-inferred syndromes.
5. **HD-5:** Decision criteria for bundling neural embedding models (license and latency trade-offs).

