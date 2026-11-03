# TriageRAG Clinical Relevance Annotation Guide

> **Research prototype. Synthetic data only. Not a medical device. Not for clinical use.**

## 1. Overview and Purpose

This document specifies the clinical relevance grading ontology and procedure for evaluating TriageRAG's protocol retrieval subsystem. Independent clinical annotators review blinded synthetic patient cases and assign relevance grades to candidate protocol chunks.

The objective is to establish an objective, reproducible gold-standard test collection with quantified inter-annotator agreement (Cohen's $\kappa$).

---

## 2. Three-Level Relevance Grading Ontology

Every candidate protocol node is assigned an integer grade in $\{0, 1, 2\}$ based strictly on clinical utility and protocol applicability for the given synthetic patient presentation.

### Grade 2: Directly Actionable Node (Primary Evidence)
- **Definition:** The node contains immediate, life- or stability-critical clinical instructions that directly address the patient's acute syndrome and vital sign derangements.
- **Criteria:**
  - The IF condition of the node is satisfied by the patient's vitals, age group, or clinical presentation.
  - The THEN action specifies the first-line intervention, urgent diagnostic step, or critical escalation indicated for this specific condition.
- **Examples:**
  - *Anaphylaxis:* Intramuscular epinephrine administration node when patient presents with hypotension, stridor, or wheezing.
  - *Severe Asthma:* Inhaled short-acting beta-agonist plus systemic corticosteroid node for acute bronchospasm with tachypnoea.
  - *Hypoglycaemia:* Rapid oral or intravenous glucose administration node for severe symptomatic neuroglycopenia ($< 55\text{ mg/dL}$).

### Grade 1: Supporting Node (Contextual / Secondary Evidence)
- **Definition:** The node belongs to the correct clinical syndrome or guideline, but provides secondary monitoring, supportive care, subsequent reassessment criteria, or conditional escalation rather than the immediate primary action.
- **Criteria:**
  - The node is clinically relevant to the patient's underlying condition, but is not the single most urgent or initial intervention.
  - The node provides essential monitoring guidance (e.g., "reassess blood pressure every 5 minutes", "prepare airway equipment if stridor progresses").
- **Examples:**
  - Continuous cardiac monitoring or IV access establishment in acute coronary syndrome while primary antiplatelet/nitrate therapy is pending.
  - Monitoring response 15 minutes after initial bronchodilator delivery in acute asthma.

### Grade 0: Irrelevant / Non-Indicated / Contraindicated Node
- **Definition:** The node does not provide clinically valid guidance for the patient's acute condition.
- **Criteria:**
  - Addresses an entirely different, unrelated clinical syndrome (e.g., sepsis resuscitation for an isolated opioid overdose).
  - The IF clause is explicitly violated or non-applicable (e.g., paediatric-specific dosing node presented for an adult patient).
  - Specifies an action that would be contraindicated or hazardous given the patient's vital signs or stated history (e.g., beta-blockers in acute decompensated heart failure with shock).

---

## 3. Ambiguity and Boundary Decision Rules

### 3.1 Multi-Syndrome or Conflicting Presentations
When a synthetic case presents conflicting findings (e.g., hypotension with suspected sepsis vs cardiogenic shock):
1. Grade 2 is reserved for nodes addressing the most life-threatening acute threat indicated by vitals (e.g., profound shock requiring fluid challenge or vasopressor support).
2. Plausible differential diagnosis protocols that require urgent bedside evaluation are graded 1 (supporting).
3. Non-emergent or unindicated protocols are graded 0.

### 3.2 Vitals-Only Presentations (Unspecified Syndrome)
For cases where no suspected syndrome is provided in the intake:
1. Candidate nodes that correctly identify the derangement (e.g., severe refractory hypotension $\to$ shock resuscitation protocol) and specify first-line stabilization are graded 2.
2. Nodes describing broad supportive care for unstable vitals are graded 1.
3. Disease-specific protocols without supporting vital sign patterns are graded 0.

### 3.3 Expected Abstention Cases
Certain benchmark cases are designed as negative controls (e.g., out-of-scope conditions, missing critical vitals preventing safe triage, or non-acute presentations):
- For expected abstention cases, **all** retrieved candidate nodes must be graded 0.
- A well-calibrated triage retrieval engine is expected to abstain rather than retrieve non-indicated protocol steps.

---

## 4. Annotation Procedure and Blinding

1. **Blinded Export:** Annotators receive cases exported via `tools/export_annotations.py export`.
   - Cases contain: `case_id`, `age`, `population`, `vitals`, `presentation_notes`, and a randomised list of candidate node IDs with their text.
   - **Blinded fields:** Annotators never see system ranks, retrieval scores, predicted syndromes, or other raters' labels.
2. **Independent Scoring:** Each annotator independently records their rating (`0`, `1`, or `2`) and an optional clinical rationale per candidate node.
3. **Submission Format:** Completed ratings are saved according to `eval/annotations/schema.json`.
4. **Agreement Analysis:** Inter-rater reliability is computed via `tools/export_annotations.py agreement --file-a <file> --file-b <file>`, outputting Cohen's $\kappa$ and confusion matrices.
5. **Human Dependency Notice:** In this research prototype, until two independent human clinical annotators complete double-annotation of the blinded pool, benchmark labels remain formally marked as `AGENT_AUTHORED_UNREVIEWED`. No artificial or fabricated human agreement claims are permitted.
