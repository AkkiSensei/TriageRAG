# TriageRAG User Output & Explainability Guide

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

---

## 1. Core Principle: Explainable Decision Support

When a clinician or researcher evaluates a patient case in TriageRAG, the system does not emit an unexplained black-box recommendation.

Instead, TriageRAG answers **six core questions** for every triage submission:

```
+---------------------------------------------------------------------------------------------------+
|                                  SIX CORE USER QUESTIONS                                         |
+------------------------------------+--------------------------------------------------------------+
| 1. What did I submit?              | Exact request echo with measured/estimated vital signs,      |
|                                    | confirmed medication lists, and complaint isolation state.   |
+------------------------------------+--------------------------------------------------------------+
| 2. What did the system process?    | Stage-by-stage execution pipeline timeline showing vitals   |
|                                    | scoring, DDI screening, retrieval, drafting, and verification.|
+------------------------------------+--------------------------------------------------------------+
| 3. What information did retrieval  | Transparent evidence cards with doc ID, section ref, chunk   |
|    find?                           | ID, text excerpt, and explicit BM25 lexical ranking disclosure.|
+------------------------------------+--------------------------------------------------------------+
| 4. Why did the system produce      | Grounded outcome reasons explaining the exact rule triggers, |
|    this result?                    | score thresholds, or abstention gates that drove the outcome.|
+------------------------------------+--------------------------------------------------------------+
| 5. What was successfully checked?  | Explicit inventory of evaluated safety rules, allergy cross- |
|                                    | reactivity checks, and weight-based dose tripwires.          |
+------------------------------------+--------------------------------------------------------------+
| 6. What could not be established?  | Fail-closed disclosure of missing vitals, unresolved entities,|
|                                    | and documented ruleset coverage gaps.                        |
+------------------------------------+--------------------------------------------------------------+
```

---

## 2. The 6-Question Architecture in Detail

### Question 1: "What did I submit?"
* **UI Location:** Top of Intake Station and Results Summary Header.
* **Component:** `PatientIntakeForm` and `ReportPage` Request Echo.
* **Guarantees:**
  - **Tri-State Physiological Parameters:** Every vital sign and weight is badged as `measured`, `estimated`, or `unknown`.
  - **Medication & Allergy History:** Badged as `confirmed_none`, `confirmed_nkda`, `confirmed_list`, `incomplete`, or `unknown_unobtainable`.
  - **Untrusted Chief Complaint Isolation (Rule R7):** Displays the entered text, but explicitly confirms whether the narrative was excluded from drafting or passed inside a delimited block (off by default).
  - **Clinical Syndrome Selection (Finding A):** Reflects explicit clinician selection; untrusted complaint text never mutates or overrides syndrome routing via substring searching.

### Question 2: "What did the system process?"
* **UI Location:** `Execution Pipeline & Decision Path` collapsible section on Report Page.
* **Component:** `ExplanationSection` (Pipeline Timeline).
* **Guarantees:**
  - Displays the 9 deterministic stages of the TriageRAG pipeline:
    1. Input Validation & Tri-State Normalization
    2. Physiological Early Warning Scoring (NEWS2 / PEWS)
    3. Baseline Rule & Contraindication Screening
    4. Clinical Syndrome Routing & Partitioning
    5. Guideline Corpus Retrieval (BM25 / Hybrid RRF)
    6. Retrieval Abstention & Safety Gating
    7. Plan Generation (Deterministic Offline Mock Provider)
    8. Machine Verification & Citation Matching
    9. Final Verdict Lattice Resolution (`BLOCKED` > `UNVERIFIED` > `CHECKED_ALERTS` > `CHECKED_CLEAR`)

### Question 3: "What information did retrieval find?"
* **UI Location:** `Retrieved Protocol Evidence` Tab.
* **Component:** `RetrievalView`.
* **Guarantees:**
  - **Lexical Ranking Disclosure (Rule R3 / Finding D):** Explicitly states: *"BM25 score is a lexical ranking metric based on term frequency and token matching against a controlled synthetic vocabulary. It is NOT a clinical confidence score or diagnostic probability."*
  - **Corpus Provenance (Rule R9 / Finding F):** Every evidence card is prominently tagged with a `SYNTHETIC CORPUS` badge indicating that protocols are non-clinical synthetic text with zero numeric dosing.
  - **Traceable Identifiers:** Document ID (`PROTO_*`), Section Name, Chunk ID, and Exact Text Excerpt are visible and expandable.
  - **Abstention Transparency:** If retrieval abstains (e.g. `EMPTY_QUERY`, `LOW_SIMILARITY`), the exact gate and reason are rendered in high contrast with guidance.

### Question 4: "Why did the system produce this result?"
* **UI Location:** `Executive Triage Verdict` and `Why Did I Get This Result?` Cards.
* **Component:** `ExplanationSection` (Verdict Banner & Outcome Reasons).
* **Guarantees:**
  - **Clear Headlines:**
    - `BLOCKED: Absolute Safety Interlock Triggered` (Rule R11: Non-overridable contraindication or lethal DDI).
    - `UNVERIFIED: Insufficient or Unresolved Clinical Data` (Rule R2: Fail-closed on missing vitals or unknown history).
    - `CHECKED WITH ALERTS: Clinical Warnings Require Review` (Moderate interaction, high-risk flag, or elevated score).
    - `CHECKED CLEAR: No Configured Safety Rules Triggered` (All rules fired clear in the active prototype ruleset).
  - **Grounded Reasons:** Every reason links back to a specific `rule_id`, involved `drug_ids`, and clinical consequences.

### Question 5: "What was successfully checked?"
* **UI Location:** `Checks Completed by Decision Engine` List.
* **Component:** `ExplanationSection` & `ResultsPane`.
* **Guarantees:**
  - Lists the count of registered rules evaluated across the clinical registry.
  - Confirms deterministic contraindication screening, allergy cross-reactivity interlocks, and weight-based dose tripwires (including 10x/1000x magnitude protection).
  - Confirms machine verification of each proposed protocol step.

### Question 6: "What could not be established?"
* **UI Location:** `Unresolved Checks & Ruleset Gaps` List.
* **Component:** `ExplanationSection` & `SkippedChecksList`.
* **Guarantees:**
  - **No Silent Passes:** Missing vitals (e.g., consciousness, supplemental O2) that cause score calculation skips are individually itemized.
  - **Unresolved Entities:** Any medication or substance that failed ontology mapping is explicitly surfaced.
  - **Known Ruleset Coverage Gaps:** Documented gaps (e.g., pediatric dose titration, renal/hepatic clearance adjustments) are permanently disclosed.

---

## 3. UI Component Mapping & Visual Design

```
+---------------------------------------------------------------------------------------------------+
|  web/src/pages/ReportPage.tsx                                                                     |
|  +---------------------------------------------------------------------------------------------+  |
|  | ExplanationSection.tsx (Executive Verdict Banner + Plain Language Summary)                  |  |
|  | - Headline & High-Contrast Verdict Pill                                                      |  |
|  | - Core Plain Language Summary grounded in engine output                                     |  |
|  | - Interactive Metrics Badges (Alerts, Steps Checked, Mode)                                  |  |
|  +---------------------------------------------------------------------------------------------+  |
|  | ExplanationSection.tsx (Why Did I Get This Result? + Permitted Next Actions)                |  |
|  | - Itemized Rule Triggers & Clinical Consequences                                            |  |
|  | - Actionable, safety-compliant clinical next steps                                          |  |
|  +---------------------------------------------------------------------------------------------+  |
|  | ExplanationSection.tsx (Collapsible 9-Stage Execution Pipeline Timeline)                     |  |
|  +---------------------------------------------------------------------------------------------+  |
|  | Tab 1: Verified Clinical Plan (VerifiedPlanView.tsx)                                        |  |
|  | - Step-by-step status: Passed / Blocked / Warning / Requires Clinician Confirmation         |  |
|  | - Quoted protocol citations & rejection reasons                                             |  |
|  +---------------------------------------------------------------------------------------------+  |
|  | Tab 2: Retrieved Protocol Evidence (RetrievalView.tsx)                                      |  |
|  | - Evidence cards with BM25 Lexical Ranking Disclosure & Synthetic Badge                     |  |
|  | - Collapsible "How Retrieval Works" Drawer                                                  |  |
|  +---------------------------------------------------------------------------------------------+  |
|  | Tab 3: Deterministic Engine Audit (ResultsPane.tsx / ScoreCard.tsx / SkippedChecksList.tsx)  |  |
|  | - Complete transparent audit trail with SHA-256 provenance hashes                           |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

## 4. Preset Scenarios for Instant Demonstration

To verify system behavior across all four verdict categories, four reference test cases are available via 1-click preset buttons on the Intake Station (`ScenarioSelector.tsx`):

1. **BLOCK Preset (`SCENARIO_BLOCK_01`):**
   - *Presentation:* Chest pain in a patient with active Sildenafil therapy.
   - *Outcome:* `BLOCKED`. Sildenafil + Nitroglycerin fatal DDI detected. Overrides strictly prohibited under Rule R11.
2. **HIGH ALERT Preset (`SCENARIO_HIGH_01`):**
   - *Presentation:* Suspected sepsis with confirmed Penicillin allergy.
   - *Outcome:* `CHECKED_ALERTS`. Ceftriaxone cross-reactivity warning. Requires logged clinician override justification.
3. **UNVERIFIED Preset (`SCENARIO_UNVERIFIED_01`):**
   - *Presentation:* Incomplete vital signs and unknown medication history.
   - *Outcome:* `UNVERIFIED`. Early warning score skipped due to missing vitals; fail-closed under Rule R2.
4. **CHECKED CLEAR Preset (`SCENARIO_CLEAR_01`):**
   - *Presentation:* Acute anaphylaxis with complete vitals and confirmed NKDA.
   - *Outcome:* `CHECKED_CLEAR`. All configured prototype rules evaluated without alerts.
