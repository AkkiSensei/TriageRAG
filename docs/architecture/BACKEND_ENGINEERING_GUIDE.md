# TriageRAG Backend Engineering Guide

> **Clinical Research Prototype Disclaimer**  
> Synthetic data only. Not a medical device. Not for clinical use.

---

## 1. Architectural Philosophy & The 5 Foundations

TriageRAG is a research prototype of deterministic emergency-triage clinical decision support. It is built upon five non-negotiable architectural foundations:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       THE FIVE FOUNDATIONS OF TRIAGERAG                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Code Decides; LLM Explains (Rule R1)                                     │
│    Clinical verdicts, dose ceilings, interlocks, and scores are calculated  │
│    strictly by pure deterministic Python. The LLM only proposes plan drafts │
│    which must pass machine verification.                                    │
│                                                                             │
│ 2. Fail-Closed Boundary (Rule R2)                                           │
│    Missing, unknown, or unverified data results in UNVERIFIED, never clear. │
│    "No rule fired" means no rule in this ruleset fired, not "patient safe". │
│                                                                             │
│ 3. Decimal-Only Clinical Math (Rule R8)                                     │
│    Floating-point representations are forbidden in clinical math. All       │
│    weights, vitals, and dosages use exact Python Decimal with magnitude    │
│    tripwires (10x / 1000x guardrails).                                      │
│                                                                             │
│ 4. Inviolable BLOCK Interlock (Rule R11)                                    │
│    No code path, configuration flag, or clinician override can approve a   │
│    step with a BLOCK alert. BLOCK is a permanent hard ceiling.               │
│                                                                             │
│ 5. Untrusted Narrative Isolation (Rule R7)                                  │
│    Free-text patient complaints are untrusted input. They are excluded by   │
│    default from LLM prompts, retrieval queries, and engine rulesets.        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. End-to-End Request Lifecycle

The diagram below traces the end-to-end journey of an emergency triage request:

```mermaid
sequenceDiagram
    autonumber
    actor Clinician as Clinician / Frontend UI
    participant API as FastAPI Boundary
    participant Graph as LangGraph Orchestrator
    participant Normal as Normalise & Scoring
    participant Engine1 as Pass 1 Safety Interlocks
    participant RAG as Retrieval & Abstention
    participant LLM as Plan Drafter (FakeLLM)
    participant Verify as Pass 2 Machine Verifier
    participant Audit as Cryptographic Audit Chain

    Clinician->>API: POST /api/triage (Patient JSON)
    API->>API: Validate Pydantic Schemas & Sanitize
    API->>Graph: run_triage_graph(patient, registry)
    
    rect rgb(240, 248, 255)
        Note over Graph, Normal: Stage 1: Normalisation
        Graph->>Normal: normalize_patient() & calculate_early_warning_score()
        Normal-->>Graph: Normalized Patient & EWS Band
    end

    rect rgb(255, 240, 245)
        Note over Graph, Engine1: Stage 2: Pass 1 Baseline Interlocks
        Graph->>Engine1: evaluate_baseline(patient, registry)
        Engine1-->>Graph: Baseline Alerts, Skips, Blocked Drug Set
    end

    rect rgb(245, 255, 240)
        Note over Graph, RAG: Stage 3: Calibrated Retrieval
        Graph->>RAG: retrieve_protocol_chunks(patient, index)
        RAG-->>Graph: RetrievalReport (Chunks or Calibrated Abstain)
    end

    alt Retrieval Abstained (Rule R2 Fail-Closed)
        Graph->>Graph: Route to abstain_fallback node (Skip LLM)
    else Retrieval Successful
        Graph->>LLM: draft_plan_safe(patient, chunks, allowed_drugs)
        LLM-->>Graph: PlanDraft (Proposed Care Steps)
    end

    rect rgb(255, 250, 240)
        Note over Graph, Verify: Stage 5: Pass 2 Machine Verification
        Graph->>Verify: verify_plan(patient, draft, alerts, chunks)
        Verify-->>Graph: VerifiedSteps, PlanAlerts, Verdict Lattice
    end

    rect rgb(245, 240, 255)
        Note over Graph: Conditional Edge 2: Verdict Lattice Seal
        alt Verdict is BLOCKED
            Graph->>Graph: Route to block_seal (Rule R11 Inviolable)
        alt Verdict is UNVERIFIED
            Graph->>Graph: Route to unverified_seal (Rule R2 Fail-Closed)
        else Verdict is CHECKED_CLEAR / CHECKED_ALERTS
            Graph->>Graph: Route to verified_seal
        end
    end

    rect rgb(240, 255, 255)
        Note over Graph, Audit: Stage 6 & 7: Audit & Explanation
        Graph->>Audit: append_audit_entry() (SHA-256 Hash Chain)
        Audit-->>Graph: audit_hash
        Graph->>Graph: Compile EngineReport & Explanation
    end

    Graph-->>API: TriageResponse (Engine + Plan + Audit + Trace)
    API-->>Clinician: HTTP 200 OK (JSON Response)
```

---

## 3. LangGraph Orchestration Architecture

TriageRAG uses **LangGraph `StateGraph`** (`src/triagerag/orchestration/langgraph_workflow.py`) as its central workflow orchestration engine.

### 3.1 Node Inventory

The workflow is composed of 11 processing nodes and 2 conditional routing edges:

| Node Name | Category | Primary Function | Safety Invariant |
| :--- | :--- | :--- | :--- |
| `normalise` | Preparation | Normalizes demographics, unit bounds, calculates EWS score. | Exact Decimal vitals; no NaN or null corruption. |
| `intake_safety_checks` | Pass 1 Engine | Evaluates contraindications, allergies, DDIs, formulary rules. | Unverified allergy status triggers `UNVERIFIED`. |
| `retrieve` | Protocol Grounding | Hard population/syndrome filtered chunk retrieval. | Calibrated confidence gate ($< 0.15$ triggers abstention). |
| `draft_plan` | Plan Generation | Prompts LLM using approved protocol text and allowed drug list. | Blocked drugs cannot be passed in allowed drug list. |
| `abstain_fallback` | Fail-Closed Fallback | Activated when retrieval abstains; safely sets fallback mode. | Skips LLM execution entirely (Rule R2). |
| `verify` | Pass 2 Verification | Verifies steps, runs dose checks, scans drug leaks, resolves verdict. | No step can be approved if blocked (Rule R11). |
| `block_seal` | Invariant Seal | Terminal disposition seal for BLOCKED cases. | Hard lock: overrides and approvals impossible. |
| `unverified_seal` | Invariant Seal | Terminal disposition seal for UNVERIFIED cases. | Missing data cannot be bypassed. |
| `verified_seal` | Invariant Seal | Terminal disposition seal for verified clear/alert cases. | Asserts that verdict is truly authorized. |
| `audit` | Cryptographic Log | Appends execution record to tamper-evident SHA-256 hash chain. | Exclusive cross-platform advisory file lock. |
| `explain` | Explanation Engine | Assembles deterministic `EngineReport` and `TriageExplanation`. | Plain-language disclosure of clinical provenance. |

### 3.2 State Immutability & Thread Safety

The workflow state is defined as `TriageGraphState` (a typed dictionary). Each invocation creates an isolated state instance. The compiled graph (`CompiledStateGraph`) is instantiated once and safely shared across requests via thread-safe read locks.

---

## 4. Deterministic Clinical Safety & Two-Pass Interlocks

### 4.1 Pass 1: Baseline Safety Evaluation
Before any treatment is retrieved or drafted, the engine evaluates the patient's existing state:
1. **Allergy History Interlocks:** If allergy status is `unknown` or `unresolved`, the engine flags an unverified history skip, forcing the verdict lattice to `UNVERIFIED`.
2. **Drug-Drug Interactions (DDIs):** Current medications are cross-checked against registered interaction rules.
3. **Formulary Population Rules:** Identifies drugs prohibited for the patient's age category (e.g., pediatric vs. adult).
4. **Physiological Interlocks:** Evaluates vitals contraindications (e.g., beta-blockers in severe bradycardia).

### 4.2 Pass 2: Machine Plan Verification
Every step proposed by the LLM undergoes rigorous machine verification:
1. **Formulary Drug ID Check:** Ensures the drug exists in the verified formulary registry.
2. **Route Validity:** Checks proposed route against approved routes in `FormularyDrug.routes`.
3. **Prose Drug Leak Scan:** Scans free-text instructions for hidden or unlisted drug names using `scan_narrative_for_drug_leaks`.
4. **Citation Grounding:** Requires exact chunk ID citations with minimum lexical overlap ($\ge 0.35$).
5. **Applicability Predicates:** Ensures conditional protocol clauses (e.g., "IF systolic BP < 90") match patient vitals.
6. **Dosage Verification:** Evaluates per-dose and daily dosage ceilings using exact Decimal arithmetic.

---

## 5. Developer Guide: How to Extend TriageRAG

### 5.1 Adding a New Clinical Rule
To maintain clinical provenance and prevent fabricated rules (Rule R3), clinical rules are added using the dedicated rule tool:

```bash
python tools/add_rule.py \
  --rule-id "DDI_WARFARIN_ASPIRIN_BLEED" \
  --rule-type "pair" \
  --drug-ids "warfarin,aspirin" \
  --severity "HIGH" \
  --consequence "Significantly increased risk of major gastrointestinal hemorrhage" \
  --action "Avoid co-administration or initiate gastroprotection"
```

Rules authored in this manner automatically carry:
- `source_status: PLACEHOLDER_UNRETRIEVED`
- `verified: false`
- `reviewer: null`
- `content_origin: AGENT_DRAFT_UNSOURCED`

### 5.2 Adding a New LangGraph Processing Node
1. Define the node function in `src/triagerag/orchestration/langgraph_workflow.py`:
   ```python
   def my_custom_node(state: TriageGraphState) -> dict[str, Any]:
       # Perform deterministic operation
       return {"custom_output_key": value}
   ```
2. Register the node in `build_triage_graph()`:
   ```python
   builder.add_node("my_custom_node", my_custom_node)
   ```
3. Wire the appropriate incoming and outgoing edges:
   ```python
   builder.add_edge("previous_node", "my_custom_node")
   builder.add_edge("my_custom_node", "next_node")
   ```
4. Update `TriageGraphState` with the new state key and add unit test coverage in `tests/unit/test_langgraph_orchestration.py`.

---

## 6. Verification & Quality Gates

Run the verification suite before any commit:

```bash
# Fast verification: Linters, Types (mypy), Layer Isolation (import-linter), Data Validation, Rule Coverage, Unit Tests
.venv/Scripts/python.exe tools/tasks.py verify-fast

# Full comprehensive verification (includes property-based Hypothesis and full integration suites)
.venv/Scripts/python.exe tools/tasks.py verify
```

---

## 7. Viva & Technical Presentation Talking Points

When presenting TriageRAG to professors or technical evaluators:

1. **Why not just prompt GPT-4 to do triage directly?**  
   *Answer:* LLMs are non-deterministic, prone to hallucination, cannot guarantee decimal mathematical accuracy, and lack hard safety guarantees. In TriageRAG, code decides; the LLM merely drafts. If the LLM proposes a lethal drug combination, the deterministic engine strikes it through before any clinician sees it.

2. **How is LangGraph used?**  
   *Answer:* LangGraph provides deterministic, stateful workflow orchestration. Instead of a brittle single script, the lifecycle is structured as an explicit state graph with conditional routing, fail-closed abstention paths, and dedicated disposition seals (`block_seal`, `unverified_seal`, `verified_seal`).

3. **Why do you use `Decimal(str(...))` instead of `float`?**  
   *Answer:* Floating-point numbers introduce binary rounding inaccuracies (e.g., $0.1 + 0.2 = 0.30000000000000004$). In clinical pharmacology, a rounding error can trigger an erroneous dose ceiling breach. Rule R8 mandates exact Decimal arithmetic everywhere.

4. **What does "Fail-Closed" mean?**  
   *Answer:* In clinical safety, absent data must never be assumed benign. If a patient's allergy status or weight is unknown, the system fails closed by assigning the verdict `UNVERIFIED`. The system only grants `CHECKED_CLEAR` when positive verification has been established.
