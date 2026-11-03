# ADR 0014: Applicability-Aware Grounding, THEN-Clause Qualifier Verification, and Verdict Lattice Safety

## Context
Prior to AUB Phase 5, TriageRAG's citation verification suffered from a critical clinical grounding loophole identified in **AUB-GRD-01**:
1. **Text Presence vs. Clinical Applicability**: Citation verification (`verify_citation` in `triagerag.verify.citations`) evaluated lexical overlap, verbatim whitespace-normalized substring presence, and THEN-clause token coverage. It never evaluated whether the cited protocol node's IF-clause preconditions actually applied to the patient.
2. **False Clear Assurance**: For example, `ANAPHYLAXIS_01_NODE_3` states:
   `"IF signs of systemic hypoperfusion, compensatory tachycardia, or refractory shock continue after initial therapy: THEN repeat administration of intramuscular epinephrine and establish wide-bore vascular access."`
   When a normotensive patient with normal vitals (SBP 125 mmHg, HR 75 bpm) presented with an allergic reaction, a plan drafting epinephrine citing `ANAPHYLAXIS_01_NODE_3` passed citation verification because the word "epinephrine" was in the text and the quoted span was verbatim. Consequently, the step was marked `APPROVED`, and the orchestrator emitted an overall verdict of `CHECKED_CLEAR`!
3. **Qualifier Laundering**: Conditional, temporal, and discretionary qualifiers ("repeat", "consider", "after", "following", "continue", "withhold", "until") present in protocol THEN clauses were not required in drafted instructions. A drafted step could order "Administer epinephrine IM immediately" while citing a repeat-dose refractory clause, effectively laundering second-line or escalated therapies into unconditional first-line orders.
4. **Mock Generator Limitations**: `FakeLLM` previously used static, hand-written per-syndrome scripts rather than retrieving from the actual ranking, and lacked profiles exercising verifier refusal paths for clinical inapplicability and qualifier dropping.

## Decision

1. **Patient Applicability Verification (`verify_node_applicability`, T5.1 / AUB-GRD-01)**:
   - Authored `src/triagerag/verify/applicability.py`.
   - Compares cited protocol node preconditions (`requires_predicates`) and contraindications (`contraindicated_by`) from `data/retrieval/node_predicates.yaml` against structured patient vitals, medications, allergies, and age using the unified predicate vocabulary (`evaluate_predicate`).
   - Supports both legacy positional identifiers (e.g. `ANAPHYLAXIS_01_NODE_3`) and content-addressed identifiers via bidirectional alias resolution (`load_node_aliases`).
   - Defined typed tri-state `ApplicabilityStatus`:
     - `MET`: All required preconditions are satisfied by patient data, and no contraindications are triggered.
     - `NOT_MET`: Patient data violates one or more preconditions or triggers a contraindication. The step status is set to `StepStatus.NOT_APPLICABLE`.
     - `UNKNOWN`: Required precondition data is missing or unmeasured in the patient record. The step status is set to `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION`.
   - Non-decision / parent chunks without IF-clause preconditions evaluate to `MET`.
   - Decision nodes missing predicate declarations fail closed to `UNKNOWN`.

2. **THEN-Clause Qualifier Verification (`verify_step_qualifiers`, T5.2 / AUB-GRD-01)**:
   - Authored `src/triagerag/verify/qualifiers.py`.
   - Detects controlled qualifier categories in cited THEN clauses:
     - `repeat` (`repeat`, `repeated`, `re-administer`) -> must retain `repeat`, `second`, `subsequent`, `further`, or `escalated`.
     - `consider` (`consider`, `considering`, `trial of`) -> must retain `consider`, `trial`, `discretion`, `evaluate for`.
     - `after` (`after`, `following`, `subsequent to`) -> must retain post-condition or temporal prerequisite wording.
     - `continue` (`continue`, `maintain`, `prolong`) -> must retain maintenance or ongoing wording.
     - `withhold` (`withhold`, `avoid`, `hold`) -> must reflect withholding / avoidance directives.
     - `until` (`until`, `only when`, `only if`) -> must retain boundary limits.
   - If an essential qualifier in the cited THEN clause is missing from the drafted instruction, the citation fails closed with `QUALIFIER_DROPPED: cited node contains '{qualifier}' qualifier ({description}) not present in drafted instruction`.
   - Step status resolves to `StepStatus.CITATION_UNVERIFIED`.

3. **Verdict Lattice Integration and Fail-Closed Guarantees (T5.3 / AUB-GRD-01)**:
   - Added `NOT_APPLICABLE` to `StepStatus` in backend and frontend contracts (`web/src/types/api.ts`, `VerifiedPlanView.tsx`).
   - Wired applicability and qualifier checks into `verify_plan` in `src/triagerag/verify/plan_verifier.py`.
   - Updated `src/triagerag/orchestrator.py` so `has_unverified_steps` includes `NOT_APPLICABLE` and `REQUIRES_CLINICIAN_CONFIRMATION`.
   - Precedence: `BLOCKED_STRUCK_THROUGH` > `NOT_APPLICABLE` > `FLAGGED_HIGH` > `FLAGGED_MODERATE` > `REQUIRES_CLINICIAN_CONFIRMATION` > `CITATION_UNVERIFIED` > `APPROVED`.
   - If a step is `NOT_APPLICABLE`, it cannot be `APPROVED`.
   - If no steps are `APPROVED`, `has_approved_steps` is `False`.
   - Resolves Reviewer B's core acceptance criterion: Normotensive vitals + anaphylaxis citing `ANAPHYLAXIS_01_NODE_3` resolves strictly to `Verdict.UNVERIFIED`, never `CHECKED_CLEAR`.

4. **Retrieval-Dependent FakeLLM Adversarial Profiles (T5.4 / AUB-GEN-01)**:
   - Extended `FakeLLMProfile` in `src/triagerag/llm/fake.py` with three deterministic profiles:
     - `RANKED_CHOICE`: Dynamically extracts action and citations from the top retrieved child chunk in `context.retrieved_chunks` rather than static per-syndrome scripts.
     - `WRONG_BUT_MATCHING_CLAUSE`: Selects a verbatim span from a node whose preconditions are unmet for the patient, exercising the `NOT_APPLICABLE` verifier refusal path.
     - `QUALIFIER_DROP`: Selects a valid qualified node (e.g. repeat-dose) but strips the qualifier token from the drafted instruction, exercising the `QUALIFIER_DROPPED` / `CITATION_UNVERIFIED` verifier refusal path.
   - Verified that each profile exercises a distinct verifier path with dedicated automated tests.

## Status
Accepted and verified in Phase 5. All 21 Phase 5 unit and API integration tests pass with 0 warnings, strict static type checking (mypy), and zero lint errors (ruff).

