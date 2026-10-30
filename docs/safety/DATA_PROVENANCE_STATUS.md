# TriageRAG Clinical Data Provenance & Verification Governance

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## 1. Overview and Core Philosophy

In accordance with **Rule R3 (No invented clinical facts)** and **Rule R2 (Fail closed)**, TriageRAG enforces a formal cryptographic and structural provenance lifecycle for all clinical assets bundled into the repository, including formulary definitions, interaction and contraindication rules, early-warning physiological scoring tables, and synthetic protocol chunks.

Software and unit tests alone can prove software correctness, deterministic execution, and adherence to coded rules. However, **clinical validity cannot be manufactured by an LLM or software harness alone**; it requires formal clinical retrieval, licensing clearance, and human clinician verification.

---

## 2. Provenance Lifecycle State Machine

The provenance model enforces a 4-state lifecycle defined in `triagerag.contracts.enums.SourceStatus`:

```
                       ┌───────────────────────────────┐
                       │    PLACEHOLDER_UNRETRIEVED    │
                       │  (Initial agent/synthetic)    │
                       └───────────────┬───────────────┘
                                       │
                                       ▼ (source literature identified)
                       ┌───────────────────────────────┐
                       │     RETRIEVED_UNREVIEWED      │
                       │  (Doc cited, awaiting signoff)│
                       └───────┬───────────────┬───────┘
                               │               │
        (clinician verification│               │ (rejected / superseded)
         and license review)   │               │
                               ▼               ▼
           ┌───────────────────────┐       ┌───────────────────────┐
           │       REVIEWED        │       │       REJECTED        │
           │ (verified: true,      │       │ (deprecated or unsafe │
           │  reviewer ID bound)   │       │  rules excluded)      │
           └───────────────────────┘       └───────────────────────┘
```

### Lifecycle States:

1. **`PLACEHOLDER_UNRETRIEVED`**:
   - Initial synthetic baseline or agent hypothesis.
   - `verified` must be `False`.
   - `section_ref` is `TO_BE_RESOLVED`.
   - `content_origin` is `AGENT_DRAFT_UNSOURCED`.
   - Engine and UI badge all items with this status as **UNSOURCED DRAFT**.

2. **`RETRIEVED_UNREVIEWED`**:
   - Literature, clinical guideline, or formulary monograph has been retrieved and referenced (`source_doc` populated).
   - Awaiting clinical domain expert review and institutional license review.
   - `verified` remains `False`.

3. **`REVIEWED`**:
   - Formal peer review completed by an identified clinician reviewer.
   - Requires:
     - `verified == True`
     - Valid non-empty `reviewer` identifier (forbids `"TO_BE_RESOLVED"` or empty strings)
     - Valid resolved `section_ref` (forbids `"TO_BE_RESOLVED"`)
     - Non-empty `source_doc` and valid publication date/version
     - `content_origin` must NOT be `AGENT_DRAFT_UNSOURCED` (must be `HUMAN_AUTHORED` or `SOURCE_EXTRACT`)

4. **`REJECTED`**:
   - Proposed rule or limit determined invalid, unsafe, or superseded.
   - Never approved for production evaluation.

---

## 3. Structural Fail-Closed Schema Invariants

All clinical rules and formulary entries inherit from `triagerag.contracts.schemas.Provenance`. The schema enforces fail-closed validation at load time via Pydantic model validators:

- If `verified == True`:
  - Enforces `source_status == SourceStatus.REVIEWED`.
  - Enforces non-empty `reviewer`.
  - Enforces resolved `section_ref != "TO_BE_RESOLVED"`.
  - Enforces `content_origin != ContentOrigin.AGENT_DRAFT_UNSOURCED`.
- If `source_status == SourceStatus.PLACEHOLDER_UNRETRIEVED`:
  - Forbids `verified == True`. Any attempted claim of verification on an unretrieved draft raises a fatal validation error.

---

## 4. Current Repository Asset Inventory

As of git branch `hardening/engineering-excellence-implementation`:

| Category | Count | Current Status | Content Origin | Verified |
| :--- | :--- | :--- | :--- | :--- |
| **Formulary Drugs** | 8 | `PLACEHOLDER_UNRETRIEVED` | `AGENT_DRAFT_UNSOURCED` | `False` |
| **Clinical Interlock Rules** | 12 | `PLACEHOLDER_UNRETRIEVED` | `AGENT_DRAFT_UNSOURCED` | `False` |
| **Vitals Interlock Rules** | 50 | `PLACEHOLDER_UNRETRIEVED` | `AGENT_DRAFT_UNSOURCED` | `False` |
| **Scoring Tables** | 3 (Adult, Paediatric, Neonate) | `PLACEHOLDER_UNRETRIEVED` | `AGENT_DRAFT_UNSOURCED` | `False` |
| **Synthetic Protocols** | 6 | `PLACEHOLDER_UNRETRIEVED` | `AGENT_DRAFT_UNSOURCED` | `False` |
| **Acronym & Synonym Mappings** | 14 | `PLACEHOLDER_UNRETRIEVED` | `AGENT_DRAFT_UNSOURCED` | `False` |

---

## 5. Next Steps for Clinical Sourcing (Backlog Link)

Items queued in `BACKLOG.md`:
1. **Rule Sourcing Campaign:** Engage emergency medicine clinicians to review each of the 12 clinical rules against NHS/NICE and Resuscitation Council UK guidelines.
2. **Copyright & License Audit:** Ensure external guideline text ingested into RAG satisfies open access or educational fair use terms.
3. **Formulary Boundary Verification:** Cross-check formulary dosage ranges (`max_single_dose`, `max_daily_dose`) against BNF / BNFc monographs.

