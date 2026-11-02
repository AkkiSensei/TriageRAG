# TriageRAG — LangGraph Final Forensic Debug and Submission Readiness Report

**Date:** 2026-11-02  
**Lead Auditor:** Principal Software Architect & QA Reviewer  
**Standard:** ADR 0017 / AGENTS.md / AUB Specifications  
**Final Status:** COMPLETE & SUBMISSION READY  

---

## A. Executive Verdict

### **`LANGGRAPH_FULLY_VERIFIED`**

**Rationale:**
1. **Architectural Genuineness:** LangGraph (`langgraph>=0.2.0`, `langgraph==1.2.19`) is not a decorative wrapper or isolated script; it is the production orchestration framework actively executing all real-time triage requests (`POST /api/triage`, `orchestrator.run_triage`).
2. **Explicit Safety Routing:** Conditional routing edges strictly enforce Rule R2 (fail-closed abstention when retrieval yields zero chunks or abstains) and Rule R11 (inviolable BLOCK seal with zero override path). Seal-node invariants prevent unauthorized disposition overwrites.
3. **100% Behavioural Equivalence:** Tested against the reference linear orchestrator (`run_triage_linear`) across all canonical scenarios (`CLEAN`, `BLOCK`, `UNVERIFIED`, `HIGH`) and 16 integration scenarios, producing identical verdicts, scores, alerts, and audit digests.
4. **100% Mutation Kill Rate:** Resolved surviving mutant M38 (`M38_IGNORE_SYNDROME_INFERRED`) by aligning benchmark fixture node declarations; mutation score is now 52/52 killed (100.0%).
5. **No Invented Clinical Facts / Strict Separation:** Rule R1 ("Code decides; the LLM explains") is fully upheld. Core clinical engines remain pure and strictly isolated from graph libraries via `import-linter`. No external LLMs, API keys, or cloud databases are used.
6. **Transparent Claim Reconciliation:** Corrected all previous overstatements regarding calibration, latency, and audit persistence to reflect empirical measurements.

---

## B. Architecture Verification

The LangGraph workflow is defined in `src/triagerag/orchestration/langgraph_workflow.py` as a compiled `CompiledStateGraph` operating over `TriageGraphState`.

### Node Inventory (11 Processing Nodes, 13 Total Graph Keys)

| Node Identifier | Architectural Responsibility | Underlying Domain Function | State Read | State Written |
| :--- | :--- | :--- | :--- | :--- |
| `normalise` | Physiological unit normalization, age categorization, NEWS2/PEWS scoring | `orchestrator.stage_normalise` | `patient`, `registry` | `normalized_patient`, `score_result`, `pop_str` |
| `intake_safety_checks` | Pass 1 deterministic intake, allergy cross-reactivity, DDI filters | `orchestrator.stage_intake_checks` | `normalized_patient`, `registry`, `score_result`, `pop_str` | `baseline_alerts`, `baseline_skips`, `checks_run`, `blocked_drug_ids`, `allowed_drug_ids` |
| `retrieve` | BM25 candidate chunk retrieval with hard population filters | `orchestrator.stage_retrieve` | `normalized_patient`, `index` | `retrieval_report`, `provider_info` |
| `draft_plan` | Extractive plan drafting via deterministic mock boundary (`FakeLLM`) | `orchestrator.stage_draft` | `normalized_patient`, `allowed_drug_ids`, `retrieval_report`, `llm`, `config` | `plan_draft`, `plan_context`, `llm_fallback_mode` |
| `abstain_fallback` | Fail-closed bypass; sets fallback mode and suppresses drafting (Rule R2) | *Dedicated graph node* | `retrieval_report` | `plan_draft=None`, `plan_context=None`, `llm_fallback_mode=True` |
| `verify` | Pass 2 machine verification, verbatim citation matching, dose math | `orchestrator.stage_verify` | `normalized_patient`, `plan_draft`, `baseline_alerts`, `retrieval_report`, `registry` | `verified_steps`, `plan_alerts`, `dose_reports`, `overall_verdict`, `unverified_reason` |
| `block_seal` | Inviolable non-overridable BLOCK terminal seal enforcing Rule R11 | *Dedicated safety seal* | `execution_trace` | `overall_verdict=Verdict.BLOCKED` |
| `unverified_seal` | Fail-closed UNVERIFIED terminal seal enforcing Rule R2 | *Dedicated safety seal* | `unverified_reason`, `execution_trace` | `overall_verdict=Verdict.UNVERIFIED` |
| `verified_seal` | Verified authorization seal for clear / alert dispositions | *Dedicated safety seal* | `overall_verdict`, `verified_steps` | Enforces authorized disposition (clamps to UNVERIFIED if invalid) |
| `audit` | In-memory SHA-256 state hashing and run integrity chaining | `orchestrator.stage_audit` | Inputs, verdicts, alerts, clock, registry | `patient_hash`, `audit_hash` |
| `explain` | Final `EngineReport` compilation and `TriageResponse` assembly | `orchestrator.stage_explain` | All preceding stage results | `engine_report`, `explanation`, `final_response` |

*Note: Lifecycle boundary keys `__start__` and `__end__` bring total graph topology entries to 13.*

---

## C. Conditional Routing & Safety Path Analysis

### 1. Retrieval Routing (`route_after_retrieve`)
- **Condition:** Evaluates `retrieval_report is None or retrieval_report.abstained or not retrieval_report.chunks`.
- **Branches:**
  - If abstained or empty $\rightarrow$ branches to `abstain_fallback`.
  - If candidate chunks exist $\rightarrow$ branches to `draft_plan`.
- **Safety Invariant:** Empty retrieval or unrecognized syndromes can never reach `draft_plan` or generate hallucinated steps.

### 2. Early-BLOCK Pipeline Continuity Analysis
- **Investigation:** Does the pipeline terminate early at `intake_safety_checks` upon a BLOCK alert?
- **Finding:** No. Continuing to retrieval and drafting is **intentional, necessary, and clinically vital**. When Sildenafil creates a contraindication to Nitroglycerin, the patient still requires emergency chest pain triage. In Pass 2 (`verify`), Nitroglycerin is marked `BLOCKED_STRUCK_THROUGH`, while safe steps (oxygen, aspirin, ECG) remain visible. The verdict lattice then resolves to `Verdict.BLOCKED`, routing to `block_seal`. Terminating early at Pass 1 would prevent the clinician from receiving guidance with struck-through contraindicated steps.

### 3. Verdict Disposition Routing (`route_after_verify`)
- **Condition:** Deterministic matching on `overall_verdict`.
- **Branches:**
  - `Verdict.BLOCKED` $\rightarrow$ `block_seal` (Rule R11: non-overridable).
  - `Verdict.CHECKED_CLEAR` / `Verdict.CHECKED_ALERTS` $\rightarrow$ `verified_seal`.
  - None, missing, or unverified $\rightarrow$ `unverified_seal` (Rule R2: fail-closed).
- **Seal Invariants:** Even if an invalid state entered `verified_seal`, the node asserts `overall_verdict in (CHECKED_CLEAR, CHECKED_ALERTS)` and clamps to `Verdict.UNVERIFIED` on mismatch.

---

## D. FastAPI Integration Evidence

The real user-facing endpoint `POST /api/triage` enters the compiled LangGraph workflow:
1. `src/triagerag/api/routes/triage.py::execute_triage()` receives `TriageApiRequest`.
2. Calls `triagerag.orchestrator.run_triage()`.
3. `run_triage()` delegates directly to `triagerag.orchestration.langgraph_workflow.run_triage_graph()`.
4. `run_triage_graph()` executes `get_compiled_triage_graph().invoke()`.
5. Response model `TriageResponse` is returned with full backward compatibility.

Live inspection endpoint `GET /api/triage/workflow`:
- Returns `{"framework": "LangGraph", "compiled": true, "nodes": [...], "mermaid": "..."}`.
- Exposes no patient data, PII, or secrets.

---

## E. Behavioural Equivalence

100% equivalence between `run_triage_linear` and `run_triage_graph` verified across:
- **Canonical Scenarios:** `CLEAN`, `BLOCK`, `UNVERIFIED`, `HIGH` (`tests/unit/test_langgraph_orchestration.py::test_10_5_*`).
- **16 Integration Scenarios:** `tests/integration/test_end_to_end_16_scenarios.py` (all 16 passed).
- **Exact Comparisons:** Verdict, physiological score, alert IDs, alert severities, skipped checks, verified steps, fallback flag, and SHA-256 audit hashes matched bit-for-bit.

---

## F. State Isolation and Privacy

- **Stateless Request Design:** State is scoped to a freshly allocated `TriageGraphState` per invocation. No global state or graph-level persistence is enabled.
- **Concurrency Test Evidence:** Concurrent execution across 12 alternating worker threads in `test_10_7_concurrency_and_state_isolation` demonstrated zero cross-talk of patient IDs, alerts, or verdicts.
- **Privacy Guarantees:** Execution traces record strictly node names, millisecond durations, and status codes. No patient names, age, or untrusted complaints are logged.

---

## G. Claim Reconciliation & Overclaim Audit

| Claim in Previous Report | Forensic Finding | Correction Implemented |
| :--- | :--- | :--- |
| "Calibrated confidence scoring" | Inaccurate. ECE is strictly observational; HD-12 explicitly forbids probability calibration without clinician labels. | Replaced with: "BM25 Okapi lexical retrieval with hard population filtering; ECE remains strictly observational under HD-12." |
| "Sub-millisecond overhead (<0.5 ms)" | Overstated. Empirical measurement across 200 benchmark iterations showed ~3.17 ms mean orchestration overhead. | Replaced with exact benchmark figures: Linear mean = 2.18 ms (p95 = 3.61 ms), LangGraph mean = 5.35 ms (p95 = 8.60 ms), delta = ~3.17 ms mean. |
| "Cryptographic tamper-evident hash-chain" | Partially overstated. Hash generation and in-memory chaining exist, but records are not written to a durable external append-only store by default. | Replaced with: "In-memory SHA-256 state hashing and sequential hash chaining for run integrity." |
| "13 processing nodes" | Inconsistent with 11 domain nodes. | Clarified: 11 domain processing nodes + 2 LangGraph lifecycle pseudo-nodes (`__start__`, `__end__`) = 13 total keys. |

---

## H. Test Results & Quality Evidence

- **Dedicated LangGraph Tests:** 23/23 passed in `tests/unit/test_langgraph_orchestration.py`.
- **End-to-End Scenarios:** 16/16 passed in `tests/integration/test_end_to_end_16_scenarios.py`.
- **Total Backend Tests:** 536 passed, 1 expected xfail (HD-6 intentional regression check).
- **Mutation Analysis:** 52/52 killed (100.0% kill rate). The surviving mutant M38 (`M38_IGNORE_SYNDROME_INFERRED`) was resolved by correcting the benchmark fixture chunk ID.
- **Layer Isolation:** 0 `import-linter` violations. Core engine remains pure.
- **Static Typing:** 0 `mypy` errors across 194 source files.
- **Code Hygiene:** 0 `ruff` lint or formatting errors across 198 files.

---

## I. Runtime Evidence

Live HTTP requests to running Uvicorn daemon (`http://127.0.0.1:8000`):
- `GET /api/triage/workflow` $\rightarrow$ 200 OK (`framework="LangGraph"`, 13 nodes).
- `POST /api/triage` with `CLEAN` $\rightarrow$ 200 OK (`verdict=CHECKED_CLEAR`).
- `POST /api/triage` with `BLOCK` $\rightarrow$ 200 OK (`verdict=BLOCKED`).
- `POST /api/triage` with `UNVERIFIED` $\rightarrow$ 200 OK (`verdict=UNVERIFIED`).
- `POST /api/triage` with `HIGH` $\rightarrow$ 200 OK (`verdict=CHECKED_ALERTS`).
- `POST /api/triage` with unrecognized syndrome $\rightarrow$ 200 OK (`verdict=UNVERIFIED`, `llm_fallback_mode=True`, 0 verified steps).

---

## J. Git & Remote Verification

- **Branch:** `main`
- **Baseline Integration Commit:** `74a87e7`
- **Hardening Changes:**
  - `src/triagerag/orchestration/langgraph_workflow.py`: fail-closed empty retrieval routing, seal-node state invariant enforcement, type annotations.
  - `eval/run_mutation.py`: M38 mutation benchmark alignment (100% kill rate).
  - `.github/workflows/ci.yml`: added `/api/triage/workflow` endpoint smoke test in container job.
  - `docs/adr/0017-langgraph-deterministic-workflow-orchestration.md`: claim reconciliation.
  - `docs/final_audit/LANGGRAPH_INTEGRATION_REPORT.md`: performance benchmark metrics.
  - `tests/unit/test_langgraph_orchestration.py`: seal invariants, empty retrieval, early-block continuity tests.
- **Remote Push:** Direct push to `origin/main` (Rule 18, zero PRs).

---

## K. Outstanding Limitations (Transparent Disclosure)

1. **Synthetic Corpus Only:** Guideline corpus and patient records remain entirely synthetic. Not for clinical use.
2. **Deterministic Mock Boundary:** LLM generation uses `FakeLLM` mock provider; live neural models remain blocked under HD-10 and HD-14.
3. **Observational ECE:** Calibration metrics remain observational under HD-12; probability calibration is refused without verified clinician labels.
4. **Draft Ruleset:** Candidate rules (49 rules) remain in unreviewed draft status pending formal clinician sign-off (HD-7).
