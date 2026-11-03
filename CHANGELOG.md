# Changelog

All notable changes to TriageRAG will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - Decision Credibility Ledger, Deterministic Confidence Scoring & Data Quality Audit

### Added & Hardened
- **Live Evidence-Backed Process Graph & Real-Time Activity Feed (`web/src/features/execution/LiveProcessPanel.tsx`, `src/triagerag/orchestration/events.py`, `src/triagerag/api/routes/triage.py`):**
  - Implemented request-scoped Server-Sent Events (SSE) streaming endpoint `POST /api/triage/stream` emitting strictly typed `TriageLifecycleEvent`s (`stage.started`, `stage.completed`, `stage.skipped`, `stage.failed`, `run.completed`).
  - Added 11-node LangGraph execution tracking and router skip emission (`route_after_retrieve` emits `stage.skipped` for unselected fallback/plan drafting; `route_after_verify` emits `stage.skipped` for unselected seal branches).
  - Enforced strict privacy allowlist across all lifecycle events: zero patient identifiers, vitals, drugs, allergies, complaint narratives, or exception tracebacks in `safe_summary` or `data`.
  - Added request-scoped `ContextVar` isolation in `TriageEventSink`, verified via concurrent execution tests against cross-talk.
  - Implemented client disconnect cleanup ensuring background pipeline tasks do not hang upon dropped connections.
  - Built interactive `LiveProcessPanel` on `IntakePage` and `ReportPage` displaying dynamic 9-stage progression and real-time activity feed with monotonic sequence numbers, timestamps, and safe summaries.
  - Preserved presenter control on `IntakePage`: live graph runs step-by-step during evaluation, presenting a prominent "Run Complete · Verdict {verdict}" action button to inspect the full report when ready.
- **Stale Result Invalidation & Duplicate Submission Prevention (`web/src/context/TriageContext.tsx`, `web/src/features/intake/PatientIntakeForm.tsx`, `web/src/pages/ReportPage.tsx`):**
  - Implemented deterministic `computePatientFingerprint` hashing to invalidate mismatched session storage and immediately clear prior triage results upon new submission or patient detail edits.
  - Removed duplicate `onClick={handleSubmit}` on the submit CTA and added `if (isLoading) return` guard preventing double-dispatch.
- **Persistent "Try Demo" Action & Synthetic Clinical Scenario Flow (`web/src/components/layout/TryDemoButton.tsx`, `web/src/pages/IntakePage.tsx`, `web/src/lib/demoPatient.ts`):**
  - Added an accessible, responsive "Try Demo" button fixed to the bottom-left (`fixed z-40 left-4 bottom-4 sm:left-6 sm:bottom-6`) with mobile safe-area insets (`env(safe-area-inset-left/bottom)`).
  - Clicking navigates to `/intake` and pre-fills the form with the canonical synthetic reference patient (`BLOCK` 58yo male with acute ischemic chest pain who took Silagra / Sildenafil 50mg 12 hours ago).
  - Strictly preserves unknown values (capillary blood glucose and GCS remain `source: 'unknown'` and `value: null`) under Rules R2 and R4 fail-closed principles, never assuming safety or normal baselines.
  - Quarantines untrusted chief complaint text with `include_complaint_in_llm: false` (Rule R7).
  - Added an informative callout banner on `IntakePage` presenting a plain-language explanation of the contraindication, Rule R11 non-overridable BLOCK alert against Nitroglycerin, the core principle "Code decides; the LLM explains" (Rule R1), and the exact disclaimer: *"Research prototype. Synthetic data only. Not a medical device. Not for clinical use."*
  - Added one-click reset action ("Clear Demo / Reset") to restore blank form state.
  - Added dedicated Vitest test suite (`web/src/components/layout/TryDemoButton.test.tsx`) covering button visibility, accessibility attributes, navigation, synthetic data integrity, and banner lifecycle.
  - Hardened mobile screen layout (`bottom-28 sm:bottom-6` on `/intake`) preventing the floating demo button from obstructing the sticky primary submit CTA.
  - Hardened form reset lifecycle in `PatientIntakeForm.tsx` to restore baseline form state when demo is cleared, and preserved quarantined chief complaint text without HTML injection.
- **Withhold Steps Excluded from Medication Instructions (`src/triagerag/action_plan.py`, `tests/unit/test_action_plan.py`):**
  - Restricted `MedicationInstruction` generation in `_build_medications` strictly to approved, cited `ActionType.administer` steps.
  - Handled approved `withhold` steps exclusively as non-administration actions in `immediate_actions` (`WITHHOLD -- <drug_id>`), eliminating the possibility of a withhold directive rendering in the medication administration table.
  - Added unit regression test `test_action_plan_approved_withhold_step_excluded_from_medications`.
- **Truthful UI Confidence Badge & Dynamic Workflow Timeline (`web/src/features/results/ExplanationSection.tsx`):**
  - Replaced ambiguous "HIGH CONFIDENCE" badge on decisive blocks with explicit `DECISIVE SAFETY INTERLOCK` (and `FAIL-CLOSED (INSUFFICIENT DATA)` on unverified presentations), keeping adjacent 12-parameter case completeness prominent.
  - Dynamically derived 9-stage verification timeline statuses from actual execution state rather than static hardcoded claims: Stage 1 reflects `PARTIAL INTAKE` vs `VALIDATED` based on real measured counts, and Stage 8 reflects actual verdict outcome (`INTERLOCK ACTIVATED`, `FAIL-CLOSED`, `WARNINGS FLAGGED`, `CLEARED`).
  - Refined clinical claim from absolute "Zero LLM Hallucination" to precise factual description: "Orders Emitted Only for Approved, Citation-Verified Steps".
  - Added comprehensive frontend unit tests in `ExplanationSection.test.tsx` verifying badge and stage dynamics.
- **CI Dependency Configuration & Mypy Gating (`.github/workflows/ci.yml`, `pyproject.toml`):**
  - Resolved CI failure at mypy by adding `telemetry` extra to the CI install (`pip install -e ".[dev,api,telemetry]"`) in both `verify-and-eval` and `quickstart-smoke` workflows.
  - Added `"opentelemetry.*"` to `ignore_missing_imports = true` in `pyproject.toml` so type-checking passes cleanly in any environment lacking optional telemetry SDKs.
- **Removed Phantom Demo Defaults & Enforced Patient Honesty (`src/triagerag/orchestration/langgraph_workflow.py`, `src/triagerag/orchestrator.py`):**
  - Eliminated the background synthetic `apply_demo_defaults` invocation that discarded the defaulted patient while injecting phantom assumption tags into the report.
  - Ensured data quality and confidence strictly evaluate the patient data actually processed by the clinical engine (unmeasured parameters remain `MISSING`, never masquerading as assumed defaults).
- **Gated Medication Instructions on Step Approval & Verified Citations (`src/triagerag/action_plan.py`):**
  - Enforced that proposed steps MUST have `vs.status == StepStatus.APPROVED` and `vs.citation_verified is True` before becoming a `MedicationInstruction`.
  - Added `unapproved_draft_steps` to `ActionPlan` to isolate steps requiring clinician confirmation (`REQUIRES_CLINICIAN_CONFIRMATION`), flagged steps (`FLAGGED_HIGH`), blocked steps, and citation-unverified steps with explicit warnings: `Administration strictly prohibited`.
  - In `UNVERIFIED` or `BLOCKED` states, `medications` is strictly empty `[]`, preventing unverified draft content from being read as clinical instructions.
- **Truthful Evidence Status & Removal of Pseudo-Probabilities (`src/triagerag/action_plan.py`, `src/triagerag/contracts/schemas.py`):**
  - Added `rule_evidence` (certainty of specific triggered safety interlock, e.g. `DECISIVE_INTERLOCK`) and `case_completeness` (record completeness across 12 standard triage parameters).
  - Explicitly decoupled interlock confidence from case completeness: a `BLOCKED` presentation with missing vitals is labeled `"Safety Interlock Decisive: Contraindication Identified (Case Record Incomplete)"`, clearly stating that confidence is in the interlock, not overall clinical completeness.
  - Explicitly disclosed that numeric scores are heuristic completeness indices (0.00-1.00), not empirical or calibrated clinical probabilities.
- **Evidence-Grounded Explanations & Dose Derivation (`src/triagerag/action_plan.py`):**
  - Eliminated hardcoded drug-name string matching (`"epinephrine"`, `"ceftriaxone"`, `"nitroglycerin"`) in `_build_medications()`.
  - Derived `why_chosen` directly from verifier evidence artifacts (`vs.support_reason` and `draft.citations` with overlap scores).
  - Derived `why_not_alternatives` directly from other rejected/flagged steps and applicable baseline alerts in the presentation.
  - Derived `dose_computation_source` directly from verified patient weight provenance (`measured`, `estimated`, or `not documented`).
- **Explicit Data Quality Audit Scope (`src/triagerag/contracts/schemas.py`, `web/src/features/results/ExplanationSection.tsx`):**
  - Documented audit scope explicitly as the 12 standard triage parameters (HR, SBP, DBP, RR, SpO2, Temp, Consciousness/GCS, Weight, Allergies, Meds, Age, Sex).
  - Added `completeness_description` clarifying that assumed defaults do not count toward measured completeness.
- **Decision Credibility & Trust Layer (`src/triagerag/contracts/schemas.py`, `src/triagerag/action_plan.py`):**
  - Added strongly-typed Pydantic schemas:
    - `DataQualityReport`: audits measured vs assumed demo defaults vs missing parameters with exact parameter counts and completeness percentages.
    - `ConfidenceReport`: deterministic `HIGH`, `MEDIUM`, or `LOW` confidence rating with numerical scores and bulleted trust drivers explaining *why* the engine is confident or unverified.
    - Enriched `MedicationInstruction` with `why_chosen`, `why_not_alternatives`, and `dose_computation_source` to provide complete clinical evidence and dose derivation provenance.
    - Enriched `ActionPlan` with `why_decision` (human-readable clinical rationale), `confidence` report, `protocol_match_summary`, `unapproved_draft_steps`, and `rejected_alternatives`.
  - Added `confidence` and `data_quality` directly to `TriageResponse`.
- **Deterministic Action Planning Layer (`src/triagerag/contracts/schemas.py`, `src/triagerag/action_plan.py`):**
  - Added strongly-typed Pydantic schemas: `ActionPlan`, `ActionStep`, `MedicationInstruction`, `MonitoringStep`, and `EscalationStep` (`extra="forbid"` enforced).
  - Implemented pure deterministic `generate_action_plan()`:
    - Derives immediate steps (STOP on BLOCK, Escalate on UNVERIFIED, Caution on HIGH alerts, Proceed on CLEAR).
    - Inhibits all medications when the plan is in a BLOCKED or UNVERIFIED state (Rule R11, R2).
    - Converts verified approved plan steps to structured medication instructions with dose, route, timing, warnings, contraindication cross-references, rationale, and dose calculation origins.
    - Generates score-band-driven monitoring protocols and critical escalation routes without LLM hallucinations (Rule R1).
    - Computes plain-language `decision_summary` and `why_decision`.
- **Conservative Demo Vital Policy (`src/triagerag/defaults.py`):**
  - Added `apply_demo_defaults()` providing conservative placeholder defaults by age group (`adult`, `paediatric`, `neonate`) for demo mode.
  - Strictly preserves clinical fail-closed boundary (Rule R2): defaults carry `source="estimated"`, never override measured values, and never auto-fill neurological/GCS consciousness.
  - Automatically tags all assumed defaults with `[ASSUMED DEMO DEFAULT] {vital}: {val} (not measured)` in `action_plan.assumptions`.
- **Workflow & Orchestrator Integration (`src/triagerag/orchestration/langgraph_workflow.py`, `src/triagerag/orchestrator.py`):**
  - Embedded `action_plan`, `confidence`, and `data_quality` evaluation in `explain_node`, `run_triage_graph()`, and `run_triage_linear()`.
  - Maintained architectural decomposition constraint (no function > 120 lines in `orchestrator.py`, verified by AST unit test).
- **CLI & Web User Experience (`src/triagerag/cli.py`, `web/src/features/results/ExplanationSection.tsx`):**
  - Added Rich formatted output panels for:
    - `INPUT DATA QUALITY AUDIT` (measured parameters, assumed defaults, missing fields, completeness %).
    - `DECISION CONFIDENCE` badge and trust driver bullet points.
    - `NON-APPROVED / PROHIBITED DRAFT STEPS` panel with explicit safety prohibition warnings.
    - `IMMEDIATE CLINICAL ACTIONS`, `MEDICATION ADMINISTRATION INSTRUCTIONS` (including clinical rationale, dose origin, and excluded alternatives), and `MONITORING & ESCALATION PROTOCOL`.
  - Added dedicated UI cards in `ExplanationSection.tsx`:
    - Top-level Confidence Badge (`HIGH`, `MEDIUM`, `LOW`) with Rule Interlock and Case Record chips.
    - Expandable Input Data Quality & Provenance Audit drawer with explicit 12-parameter scope disclosure.
    - Clinical Safety Rationale and Protocol Match Summary callouts.
    - Non-Approved / Prohibited Proposed Steps card for unverified/flagged draft steps.
    - Action Plan with Confidence Trust Drivers, immediate urgency badges, and expanded medication table with `Why Chosen / Derivation` and `Excluded Alternatives` columns (rendered only when approved medications exist).
    - Propagated `rejected_alternatives` into the "Why Alternative Paths Were Rejected" card.
  - Exported updated OpenAPI specification (`web/openapi/openapi.json`) and regenerated TypeScript bindings (`web/src/types/api.ts`).
- **Test Suite & CI Hardening:**
  - Added unit test suite `tests/unit/test_defaults.py` verifying demo defaults, non-override of measured values, and GCS protection.
  - Added unit test suite `tests/unit/test_action_plan.py` (12 tests) verifying data quality audits, confidence calculations, immediate actions, blocked medication inhibition, unapproved step isolation, and monitoring schedules across all lattice states.
  - Updated integration test `tests/integration/test_api_contract.py` scenario count assertion for the 5-case reference set (`{"BLOCK", "UNVERIFIED", "HIGH", "CLEAN", "ABSTAIN"}`).
  - Added frontend test in `ExplanationSection.test.tsx` verifying Action Plan and trust layer rendering.
  - Full test suites clean: 533 unit tests passed (1 xfailed), 64 integration tests passed, 44 frontend tests passed. All linters and typechecks exit 0.
  - Added unit test suite `tests/unit/test_defaults.py` verifying demo defaults, non-override of measured values, and GCS protection.
  - Added unit test suite `tests/unit/test_action_plan.py` verifying data quality audits, confidence calculations, immediate actions, blocked medication inhibition, and monitoring schedules across all lattice states.
  - Updated integration test `tests/integration/test_api_contract.py` scenario count assertion for the 5-case reference set (`{"BLOCK", "UNVERIFIED", "HIGH", "CLEAN", "ABSTAIN"}`).
  - Added frontend test in `ExplanationSection.test.tsx` verifying Action Plan and trust layer rendering.
  - Full test suites clean: 530 unit tests passed (1 xfailed), 64 integration tests passed, 44 frontend tests passed. All linters and typechecks exit 0.

## [0.4.1] - Evidence-First Decision Ledger & Stage Trace Presentation

### Added & Hardened
- **Canonical Decision Ledger & Primary Explainability (`src/triagerag/orchestrator.py`, `web/src/features/results/ExplanationSection.tsx`, `web/src/features/results/ResultsPane.tsx`):**
  - Elevated `ExplanationSection` to the primary canonical output rendered prominently immediately below the top-level `SafetyBanner`.
  - Added deterministic `rejected_paths` to `TriageExplanation` explaining why alternative verdict paths in the clinical safety lattice were rejected under Rules R1, R2, and R11.
  - Surfaced "Why Did I Get This Result?" (`outcome_reasons`), "Why Alternative Paths Were Rejected" (`rejected_paths`), and "Permitted Next Steps" (`permitted_ui_actions`).
- **Input Normalization Ledger:**
  - Added dedicated Input Normalization Ledger comparing input patient parameters against normalized entities: raw medications mapped to active ingredients and formulary strengths, raw allergies resolved to allergen IDs, demographics, and derived vitals flags.
  - Carried `input_patient` alongside normalized `patient` in `TriageResponse` to enable transparent before/after entity comparison.
- **Retriever Evidence & Plan Grounding Ledger:**
  - Surfaced protocol search query, backend (`BM25` / `CHAR_NGRAM`), partition filters, and abstention codes/reasons.
  - Exposed retrieved protocol chunks (rank, doc_id, section, score, text snippet) and mapped plan steps against citations with verification status and overlap scores.
- **8-Stage LangGraph Execution Decision Ledger:**
  - Carried `execution_trace: list[dict[str, Any]]` formally in `TriageResponse` schema, OpenAPI specification, and TypeScript client types.
  - Rendered complete 8-node LangGraph execution trace in both UI and CLI with live runtime stage durations in milliseconds and non-sensitive diagnostic details.
- **CLI Rich Output (`src/triagerag/cli.py`):**
  - Enhanced `triage run` command with formatted Rich tables and panels for the Canonical Decision Ledger, 8-Stage Execution Trace Table, Input Normalization Ledger, and Retriever Evidence Ledger.
- **Narrow Canonical Scenarios Set (`src/triagerag/contracts/scenarios.py`, `src/triagerag/api/routes/scenarios.py`):**
  - Added preloaded scenario `ABSTAIN` (neonatal population lacking protocol coverage triggering typed `NO_POPULATION_COVERAGE` abstention and safe extractive fallback) to complete the 5 canonical demo reference cases: `CLEAN`, `BLOCK`, `UNVERIFIED`, `HIGH`, and `ABSTAIN`.

## [Unreleased] - OpenTelemetry AI Workflow Observability & Distributed Tracing (v0.4.0)

### Added & Hardened
- **Vendor-Neutral OpenTelemetry Subsystem (`src/triagerag/orchestration/telemetry.py`):**
  - Integrated optional OpenTelemetry distributed tracing (`opentelemetry-api==1.45.1`, `opentelemetry-sdk==1.45.1`, `opentelemetry-exporter-otlp-proto-http==1.45.1`) under `[project.optional-dependencies] telemetry`.
  - Built internal pure-Python standard library `_NoOpSpan` and `_NoOpTracer` fallback, ensuring core TriageRAG runs cleanly with zero OpenTelemetry packages installed.
  - Implemented strict attribute allowlist `sanitize_span_attributes` dropping all PHI, patient demographics, vitals, weights, clinical scores, alert counts, medication details, and clinical verdicts.
  - Implemented local loopback endpoint validation (`validate_loopback_endpoint`) actively rejecting non-loopback cloud collectors under Rule R12.
  - Implemented fail-safe `TraceNodeContextManager` with `record_exception=False` and unconditional `__exit__ -> False`, guaranteeing telemetry errors never interrupt triage execution while application exceptions propagate.
- **LangGraph Workflow Tracing (`src/triagerag/orchestration/langgraph_workflow.py`):**
  - Instrumented `run_triage_graph` with fail-safe `langgraph.workflow.execution` root workflow span.
  - Instrumented all 11 registered nodes (`normalise`, `intake_safety_checks`, `retrieve`, `draft_plan`, `abstain_fallback`, `verify`, `block_seal`, `unverified_seal`, `verified_seal`, `audit`, `explain`) mapped to 8 generalized operational stages (`normalise`, `intake_safety_checks`, `retrieve`, `form_plan`, `verify`, `seal_decision`, `audit`, `explain`) to prevent clinical outcome inference from span names.
  - Instrumented conditional edges (`route_after_retrieve`, `route_after_verify`) emitting safe `routing.evaluated` span events with edge names only (no clinical targets or branch dispositions).
- **FastAPI Request Lifecycle & Middleware Integration (`src/triagerag/api/app.py`):**
  - Added async `app_lifespan` managing thread-safe idempotent `TelemetryManager` initialization and shutdown.
  - Implemented outer ASGI `tracing_middleware` managing `http.request` root spans, extracting incoming W3C `traceparent` headers, recording HTTP status codes, and injecting standard outgoing `traceparent` and `X-Trace-Id` headers.
  - Configured middleware execution order to ensure HTTP 413 (payload too large) and 422 (validation error) rejections short-circuit before workflow initialization, emitting zero internal graph spans.
- **Reproducible Performance Benchmarking & Developer Documentation:**
  - Implemented `tools/benchmark_telemetry.py` evaluating latency overhead across $N=100$ iterations.
  - Empirical results: Disabled baseline 11.057 ms mean / 18.307 ms p95; In-Memory tracing 14.901 ms mean (+3.844 ms) / 29.277 ms p95 (+10.970 ms overhead; 1.50 ms optimization target not met; p99/max 54.998 ms); Console exporter 24.284 ms mean / 75.219 ms p95 / 174.732 ms p99/max; OTLP exporter unmeasured due to local Docker unavailability. Output report written to `eval/reports/telemetry_benchmark.json`.
  - Documented residual timing and exceptional termination side-channel limitations in `docs/guides/TELEMETRY_GUIDE.md` and `docs/architecture/NEXT_ENGINEERING_ENHANCEMENT_PLAN.md`.
  - Authored comprehensive developer guide `docs/guides/TELEMETRY_GUIDE.md` detailing architecture, privacy invariants, non-interference guarantees, environment configuration, local Docker Jaeger instructions, and acceptance gates.
  - Implemented durable gate execution recording in `tools/tasks.py` persisting full verification output and exit codes to `eval/reports/verify_fast.log`.
  - Authored forensic investigation in `docs/final_audit/API_FAILURE_INVESTIGATION.md` reproducing PowerShell shell tokenization truncation (`b"{\\"`) on native `curl.exe` invocations.
  - Authored 33 automated tests across 4 test suites verifying all 12 Acceptance Gates, complete exported trace tree exception privacy, and API stability under malformed input.

## [Unreleased] - Backend Engineering Audit, Hardening & Out-of-Domain Gating

### Added & Hardened
- **Fail-Closed Out-of-Domain Gating (BE-AUDIT-01 / Rule R2):**
  - Hardened `src/triagerag/rag/ask_corpus.py` with `_STOP_WORDS` filtering to prevent high-frequency English words (`how`, `do`, `i`, `a`) from triggering false-positive BM25 matches.
  - Replaced fallback to arbitrary protocol sentences with strict fail-closed abstention when queries have zero clinical content overlap.
  - Added unit regression test for out-of-domain and stop-word queries in `tests/unit/test_aub_phase7_why_and_ask_corpus.py`.
- **Complete Backend Architectural & Educational Documentation:**
  - Authored `docs/architecture/BACKEND_DIRECTORY_MAP.md`: exhaustive directory map detailing responsibilities, contracts, and test locations for every backend module.
  - Authored `docs/architecture/BACKEND_ENGINEERING_GUIDE.md`: comprehensive technical guide explaining the 5 foundations, request lifecycle, LangGraph StateGraph design, and presentation talking points.
  - Authored `docs/final_audit/BACKEND_ENGINEERING_AUDIT.md`: forensic audit report documenting layer purity, test evidence matrix, and research prototype limitations.
- **Patient Data Propagation & Care Steps UI Hardening:**
  - Preserved patient vitals and weight in `TriageResponse` schema (`patient: Patient | None`).
  - Corrected intake form sanitizers in `PatientIntakeForm.tsx` ensuring measured vitals propagate accurately through LangGraph into the Care Steps display.
  - Added full regression suite `tests/unit/test_patient_data_propagation.py` (6 tests) and frontend test suite `web/src/features/intake/PatientIntakeForm.test.tsx` (3 tests).

## [Unreleased] - LangGraph Deterministic Workflow Orchestration (ADR 0017)

### Added & Orchestrated
- **LangGraph StateGraph Integration:**
  - Integrated `langgraph>=0.2.0` (`langgraph==1.2.19`) into `pyproject.toml` and verified strict layer isolation via `import-linter`.
  - Built `src/triagerag/orchestration/langgraph_workflow.py` with strongly-typed `TriageGraphState` (TypedDict) preserving domain contracts.
  - Decomposed workflow into 11 distinct processing nodes: `normalise`, `intake_safety_checks`, `retrieve`, `draft_plan`, `abstain_fallback`, `verify`, `block_seal`, `unverified_seal`, `verified_seal`, `audit`, and `explain`.
- **Explicit Conditional Routing:**
  - Implemented `route_after_retrieve` for fail-closed protocol abstention under Rule R2 (`draft_plan` vs `abstain_fallback`).
  - Implemented `route_after_verify` for verdict lattice disposition: `block_seal` (Rule R11 non-overridable BLOCK), `unverified_seal` (Rule R2 fail-closed UNVERIFIED), and `verified_seal` (`CHECKED_CLEAR` / `CHECKED_ALERTS`).
- **FastAPI Real Application Integration:**
  - Updated `run_triage(...)` in `src/triagerag/orchestrator.py` to route all primary triage execution through `run_triage_graph(...)`.
  - Preserved `run_triage_linear` and `run_triage_legacy` as reference baselines.
  - Added introspection endpoint `GET /api/triage/workflow` returning node inventories and live Mermaid diagram syntax.
- **Verification, Testing & Documentation:**
  - Added dedicated test suite `tests/unit/test_langgraph_orchestration.py` (21 tests covering graph compilation, individual nodes, conditional routing, end-to-end paths, 100% equivalence, FastAPI integration, thread concurrency, and determinism).
  - Exported live Mermaid diagram `docs/architecture/triagerag_langgraph_workflow.mmd`.
  - Authored ADR 0017 (`docs/adr/0017-langgraph-deterministic-workflow-orchestration.md`).
  - Created full engineering audit report `docs/final_audit/LANGGRAPH_INTEGRATION_REPORT.md`.

## [Unreleased] - AUB Phase 7: Research Extensions, Showcase, and Forensic Closure

### Added & Hardened
- **Phase 0–6 Forensic Reconciliation & Defect Closure:**
  - Audited and reconciled 7 discrepancies identified during Phase 6 handoff.
  - Formally accounted for candidate rule inventory: 40 authored candidates (Batches 1–3) + 9 mined candidates (`auto_mined.yaml`) = 49 total candidate rules in `data/rules_candidates/`.
  - Clarified that the 86 golden test scenarios govern the 12 active shipped rules; candidate rules remain in unreviewed draft status pending clinician sign-off (HD-7).
  - Clarified 3.0 mL IM volume threshold as an illustrative boundary with status `NEEDS_SOURCE`.
  - Added dedicated isolation tests for `CoAdministrationRule` and synchronized documentation metrics via `tools/gen_docs_metrics.py`.
- **Controlled Query Expansion (T7.1):**
  - Implemented `data/retrieval/expansion_terms.yaml` with synthetic protocol synonym dictionaries and explicit provenance.
  - Built `src/triagerag/rag/query_expansion.py` providing deterministic `build_expanded_query`.
  - Enforced fail-closed behavior: unknown or indeterminate predicates are never expanded.
  - Integrated `expansion_trace` and `expansion_mode` into `RetrievalReport` and retrieval services. Unit tests in `tests/unit/test_aub_phase7_query_expansion.py` (5 tests).
- **Local Neural Interface & HD-10 Boundary (T7.2):**
  - Created `src/triagerag/rag/neural_interface.py` defining `EmbeddingModel`, `CrossEncoderModel`, `NeuralDenseRetriever`, and `NeuralCrossEncoderReranker`.
  - Enforced HD-10 gate: unapproved models raise `NeuralModelApprovalError` and remain marked `BLOCKED_EXTERNAL`.
  - Unit tests in `tests/unit/test_aub_phase7_neural_interface.py` (4 tests).
- **Visible RAG Evidence Experience & Why Drawer (T7.3, T7.4):**
  - Created `src/triagerag/rag/alert_why.py` explaining triggered rules, matched patient facts, unmeasured vitals, and Rule R11 non-overridable BLOCK severity rationale.
  - Created `src/triagerag/rag/ask_corpus.py` implementing extractive verbatim question answering over approved protocol chunks with `generator_badge="EXTRACTIVE_VERBATIM"`.
  - Mounted API routes `POST /api/corpus/ask` and `POST /api/triage/alert-why`.
  - Updated React frontend (`AlertsList.tsx`, `RetrievalView.tsx`, `AskCorpusSection.tsx`, `ResultsPane.tsx`) with:
    - Prominent generator badge (`DETERMINISTIC MOCK` vs `REAL PROVIDER`).
    - Query expansion term badges and trace drawer.
    - Protocol chunk license disclosures (`Open Government Licence v3.0 / Synthetic`).
    - Inline interactive "Why did this alert fire?" drawer.
    - "Ask the Corpus" query input with instant extractive answer card and clickable chunk citations.
  - Unit tests in `tests/unit/test_aub_phase7_why_and_ask_corpus.py` (5 tests).
- **API Security Gateway & Sliding-Window Rate Limiting (T7.5):**
  - Built `src/triagerag/api/security.py` with `SlidingWindowRateLimiter` and constant-time token comparison (`hmac.compare_digest`).
  - Configured authentication boundary via `TRIAGERAG_REQUIRE_AUTH` and `TRIAGERAG_API_KEY`.
  - Protected endpoints return `401 Unauthorized` with `WWW-Authenticate: Bearer` when credentials are missing or invalid; public health and docs endpoints remain exempt.
  - Per-client sliding-window rate limiter returns `429 Too Many Requests` with `Retry-After` header.
  - Added `@app.command("security-audit")` in `tools/tasks.py` supporting `pip-audit` and `npm audit`. Unit tests in `tests/unit/test_aub_phase7_security.py` (4 tests).
- **Inferred-Mode MMR, Nearest-Miss Diagnostics & HD-12 Refusal (T7.6):**
  - Implemented `src/triagerag/rag/diagnostics.py` with `apply_mmr_rerank`, `calculate_nearest_misses`, and `explain_chunk_predicates`.
  - Activated MMR when syndrome is inferred from vitals, balancing relevance and lexical token Jaccard diversity ($\lambda = 0.7$).
  - Populated `diagnostics` in `RetrievalReport` with nearest misses, deltas to threshold, and rejection reasons.
  - Preserved HD-12: Added `CalibrationDataRefusalError` in `eval/retrieval/calibrate.py` strictly refusing isotonic/conformal probability calibration when verified clinician annotations are missing. Unit tests in `tests/unit/test_aub_phase7_diagnostics_and_mmr.py` (6 tests).
- **Local Provider Architecture & Cassette Replay (T7.7):**
  - Built `src/triagerag/llm/cassette.py` with `CassetteEntry`, `CassetteTape`, and `CassetteReplayProvider`.
  - Replay matches on cryptographic SHA-256 hashes of canonical context and prompt strings.
  - Preserved HD-14: Created `ApprovedLocalProvider` raising `LLMProviderApprovalError` for unapproved live models. Unit tests in `tests/unit/test_aub_phase7_provider_cassettes.py` (4 tests).
- **Cross-Phase Integration & Architecture Decision Record:**
  - Added end-to-end integration suite `tests/integration/test_aub_phase7_cross_phase_integration.py` (6 tests).
  - Authored **ADR-0016** in `docs/adr/0016-phase-7-research-extensions-and-showcase.md`.

## [0.3.6] - AUB Phase 6: Deterministic Engine, Schema V2, and Rule Expansion

### Added & Hardened
- **Dual Trust Policy & Verification Counters (T6.0):**
  - Added `TrustMode` (`STRICT`, `DEMO`) in `src/triagerag/contracts/enums.py`.
  - In `STRICT` mode, unverified candidate rules are ignored, surfacing unverified counts.
  - In `DEMO` mode, candidate rules evaluate with visible `UNSOURCED DRAFT` disclosures in CLI and UI wristbands.
  - Codified policy in `docs/safety/TRUST_POLICY.md`. Unit tests in `tests/unit/test_aub_phase6_trust_policy.py` (6 tests).
- **Backward-Compatible Schema V2 (T6.1):**
  - Added 6 Schema V2 rule models in `src/triagerag/contracts/rules_schema.py`: `ConditionContraindicationRule`, `LabInterlockRule`, `RouteConcentrationRule`, `OrganFunctionRule`, `CoAdministrationRule`, `RateLimitRule`.
  - Extended `Patient` schema with structured `conditions`, `labs`, `renal_impairment`, `hepatic_impairment`.
  - Extended `PlanStepDraft` with `concentration_mg_per_ml`, `diluent`, `rate_mg_per_min`, `frequency_hours`, `relative_time_minutes`.
  - Preserved 100% backward compatibility for all 12 shipped rules. Unit tests in `tests/unit/test_aub_phase6_schema_v2.py` (5 tests).
- **Dose Engine Expansion & Interval Tracking (T6.2):**
  - Implemented `calculate_administration_volume` computing volumes in mL with route tripwires (IM > 3.0 mL warning).
  - Implemented `verify_dosing_intervals` tracking repeat intervals across planned steps and absolute lookbacks against patient medication history.
  - Implemented `verify_administration_rate` and harmonized `daily_max` mass semantics. Unit tests in `tests/unit/test_aub_phase6_dose_engine.py` (7 tests).
- **Class Taxonomy, Indian Aliases & FDC Expansion (T6.3):**
  - Expanded `data/classes.yaml` with ~60 emergency generics across Waves 1–3 from AUB §11.
  - Added 34 Indian single- and multi-ingredient brand aliases to `data/aliases.yaml` (Augmentin, Dolo 650, Combiflam, Deriphyllin, etc.).
  - Added multi-ingredient FDC expansion, strength token stripping, and LASA auto-resolve protection. Unit tests in `tests/unit/test_aub_phase6_classes_and_fdc.py` (6 tests).
- **Source-Traceable Candidate Batches (T6.4):**
  - Authored 40 candidate rules across 3 batches adhering to AUB Part II - A: `data/rules_candidates/batch_1.yaml` (15 rules), `batch_2.yaml` (15 rules), `batch_3.yaml` (10 rules).
  - Every rule carries strict provenance (`verified: false`, `source_status: PLACEHOLDER_UNRETRIEVED`, `reviewer: null`, `content_origin: AGENT_DRAFT_UNSOURCED`).
  - Unit tests in `tests/unit/test_aub_phase6_candidate_rules.py` (5 tests).
- **Rule Coverage Matrix and Alert Fatigue Gate (T6.5):**
  - Built `tools/rule_coverage.py` asserting every active rule has >= 3 positive, >= 3 negative, and >= 1 boundary cases passing in isolation (`only_rules`).
  - Expanded `data/golden/shipped_ruleset_cases.yaml` to 86 cases (100% green).
  - Monitored alert fatigue: 0.52 alerts/patient, 0.0% false-alert rate on negatives. Unit tests in `tests/unit/test_aub_phase6_rule_coverage.py` (3 tests).
- **Evidence-Grounded Rule Mining Pipeline (T6.6):**
  - Built `tools/mine_rules.py` ingesting Tier-2 regulatory SPL evidence chunks (`data/corpus/evidence_chunks.json`).
  - Enforced 5 deterministic validators (quote in chunk, numbers in quote, ids resolve, schema valid, no duplicate key).
  - 100% of auto-sourced rules passed all 5 validators.
  - Published clinician review queue `docs/REVIEW_QUEUE.md` under HD-7 dual-control governance. Unit tests in `tests/unit/test_aub_phase6_mine_rules.py` (6 tests).
- **Architecture Decision Record:**
  - Authored **ADR-0015** in `docs/adr/0015-schema-v2-and-deterministic-rule-engine-expansion.md`.

## [0.3.5] - AUB Phase 5: Applicability-Aware Grounding and Qualifier Verification

### Added & Hardened
- **Patient Applicability Verification Engine (T5.1 / AUB-GRD-01):**
  - Created `src/triagerag/verify/applicability.py` comparing cited protocol node preconditions (`requires_predicates`) and contraindications (`contraindicated_by`) against structured patient data (`evaluate_predicate`).
  - Added typed `ApplicabilityStatus` (`MET`, `NOT_MET`, `UNKNOWN`) and `NodeApplicabilityResult`.
  - Added `StepStatus.NOT_APPLICABLE` to backend contracts (`src/triagerag/contracts/enums.py`) and frontend definitions (`web/src/types/api.ts`, `VerifiedPlanView.tsx`).
  - Implemented bidirectional alias resolution supporting both positional and content-addressed node IDs.
  - Added unit test suite `tests/unit/test_aub_phase5_applicability.py` (6 tests).
- **THEN-Clause Qualifier Verification (T5.2 / AUB-GRD-01):**
  - Created `src/triagerag/verify/qualifiers.py` detecting conditional qualifiers ("repeat", "consider", "after", "following", "continue", "withhold", "until") in source THEN clauses.
  - Rejects drafted instructions that drop these qualifiers, refusing citations with `QUALIFIER_DROPPED: cited node contains '{qualifier}' qualifier ({description}) not present in drafted instruction`.
  - Added unit test suite `tests/unit/test_aub_phase5_qualifiers.py` (9 tests).
- **Verdict Lattice Integration & Fail-Closed Safety (T5.3 / AUB-GRD-01):**
  - Integrated applicability and qualifier verification into `verify_plan` in `src/triagerag/verify/plan_verifier.py`.
  - Updated `src/triagerag/orchestrator.py` to include `NOT_APPLICABLE` and `REQUIRES_CLINICIAN_CONFIRMATION` in `has_unverified_steps`.
  - Enforced lattice rule: `NOT_APPLICABLE` steps cannot be `APPROVED`; absence of approved steps forces `Verdict.UNVERIFIED`.
  - Verified Reviewer B's acceptance criterion: Normotensive anaphylaxis citing repeat-dose node (`ANAPHYLAXIS_01_NODE_3`) resolves strictly to `UNVERIFIED`, never `CHECKED_CLEAR`.
  - Added unit and FastAPI endpoint regression tests `tests/unit/test_aub_phase5_verdict.py` (3 tests).
- **Retrieval-Dependent FakeLLM Adversarial Profiles (T5.4 / AUB-GEN-01):**
  - Extended `FakeLLMProfile` in `src/triagerag/llm/fake.py` with `RANKED_CHOICE`, `WRONG_BUT_MATCHING_CLAUSE`, and `QUALIFIER_DROP`.
  - `RANKED_CHOICE` dynamically drafts from top retrieved child chunk in `context.retrieved_chunks`.
  - `WRONG_BUT_MATCHING_CLAUSE` cites an inapplicable clause, exercising the `NOT_APPLICABLE` verifier refusal path.
  - `QUALIFIER_DROP` cites a qualified node but drops the qualifier token, exercising the `QUALIFIER_DROPPED` / `CITATION_UNVERIFIED` verifier refusal path.
  - Added unit test suite `tests/unit/test_aub_phase5_fake_llm.py` (3 tests).
- **Architecture Decision Record:**
  - Authored **ADR-0014** in `docs/adr/0014-applicability-aware-grounding-and-qualifier-verification.md`.

## [0.3.4] - AUB Phase 4: Evaluation Rebuild and Research Validity

### Added & Hardened
- **Controlled 7-Arm Retrieval Ablation & Programmatic Decision Rule (T4.7 / AUB-EVL-01):**
  - Expanded `eval/run_retrieval_ablation.py` to evaluate seven controlled configurations: `bm25` (Production BM25 with calibrated predicates), `bm25_pure_lexical`, `char_ngram`, `hybrid_rrf`, `hybrid_rrf_rerank`, `bm25_contextual`, and `contextual_predicate`.
  - Added support for backend aliases and explicit `enable_predicate_scoring` toggle in `RetrievalService`.
  - Implemented `_compute_paired_differences()` calculating 95% bootstrap confidence intervals for paired differences vs baseline BM25 across 1,000 resamples.
  - Codified `decide_backend()`: strictly enforces hard safety invariants (FAR==0, WSR==0, HN==1, latency < 50ms) and adopts alternative candidates only with non-regressing Recall@5, test MRR gain $\ge +0.05$, and paired difference 95% bootstrap CI strictly excluding zero.
  - Retained `bm25` as default production backend after proving that contextual chunking's MRR advantage (`+0.0533`) has a 95% CI crossing zero (`[-0.0067, +0.1200]`).
  - Added comprehensive test suite `tests/unit/test_aub_phase4_ablation.py` (6 tests).
- **Hand-Computed Metric Verification Fixtures & Metric Reference (T4.6 / AUB-EVL-01):**
  - Authored `docs/evaluation/METRICS.md` documenting exact mathematical formulas, denominators, boundary conditions, and safety rationale for all metrics.
  - Authored `tests/unit/test_aub_phase4_metric_fixtures.py` verifying Recall@{1,3,5,10}, MRR, nDCG@{5,10}, FAR, WSR, legacy WPR, per-code abstention, Cohen's $\kappa$, and ECE against pencil-and-paper hand calculations (7 tests).
- **Benchmark Validity Self-Tests & Hard Performance Gates (T4.5 / AUB-EVL-01):**
  - Implemented `validate_benchmark_gate()` in `eval/run_retrieval.py` enforcing two automated validity self-tests: random candidate baseline Recall@5 must be $< 60.0\%$ (pool non-triviality) and position-prior Recall@1 must be lower than system Recall@1 with paired difference CI strictly excluding zero.
  - Automatically fails and labels benchmark collection `BENCHMARK_INVALID` on self-test violation.
  - Hard performance gates enforce: `false_accept_rate == 0.0`, `wrong_syndrome_rate == 0.0`, `wrong_protocol_rate == 0.0`, `abstain_recall_hard_negatives == 1.0`, syndrome-provided Recall@5 $\ge 95.0\%$, and bit-for-bit determinism.
  - Added unit test suite `tests/unit/test_aub_phase4_gates.py` (5 tests).
- **Honest Metrics, Granular Abstention, and Calibration (T4.4 / AUB-EVL-01 / AUB-ABS-02):**
  - Disentangled `wrong_protocol_rate` into `false_accept_rate` (FAR) and `wrong_syndrome_rate` (WSR).
  - Replaced artificial hardcoded confidence with genuine normalized retrieval scores in `_compute_ece()`.
  - Added `per_code_abstention` metrics recording precision, recall, and support per `AbstainCode`.
  - Extended reporting to Recall@{1, 3, 5, 10}, MRR, and graded nDCG@{5, 10}.
  - Implemented cluster-robust group (template-level) bootstrap 95% confidence intervals via `_group_bootstrap_ci95()`.
  - Added unit test suite `tests/unit/test_aub_phase4_metrics.py` (4 tests).
- **Random and Position-Prior Baselines (T4.3 / AUB-EVL-01):**
  - Implemented `PositionPriorRetriever` in `eval/run_retrieval.py` fitted strictly on development split data with deterministic tie-breaking.
  - Implemented `run_position_prior_baseline()` calculating paired difference 95% bootstrap CIs comparing system against position prior.
  - Answered Reviewer B's challenge question: Production BM25 test Recall@1 (54.00%) significantly beats label frequency prior (24.00%) with +30.00 pt advantage (95% CI `[12.0, 48.0]`).
  - Added unit test suite `tests/unit/test_aub_phase4_baselines.py` (5 tests).
- **Blinded Relevance Labels and Annotator Agreement Tooling (T4.2 / AUB-EVL-01):**
  - Authored `docs/evaluation/ANNOTATION_GUIDE.md` defining 3-level relevance grading rubric.
  - Authored schema `eval/annotations/schema.json` and export/agreement CLI `tools/export_annotations.py`.
  - Generated blinded export of 100 cases (`eval/annotations/blinded_cases.json`).
  - Recorded honest agreement status `BLOCKED_PENDING_INDEPENDENT_HUMAN_ANNOTATION` in `eval/annotations/agreement_status.json`.
  - Added unit test suite `tests/unit/test_aub_phase4_annotations.py` (6 tests).
- **Template-Grouped Dataset Splits with Hash Lock (T4.1 / AUB-EVL-01):**
  - Implemented `derive_template_id()` and `stratified_template_group_split()` in `eval/retrieval/build_dataset.py`.
  - Grouped all 224 cases by clinical scenario template across 55 groups (42 dev, 13 test) with 0 template leakage and 0 target node-set leakage.
  - Generated `eval/retrieval/dataset.lock` and `eval/retrieval/split_manifest.json`.
  - Added unit test suite `tests/unit/test_aub_phase4_splits.py` (4 tests).
- **Architecture Decision Record:**
  - Authored **ADR-0013** in `docs/adr/0013-evaluation-rebuild-and-validity-gates.md`.

## [Unreleased] - AUB Phase 3: Corpus Growth and Evidence Ingestion

### Added & Hardened
- **Tier-2 openFDA Regulatory Drug Label Evidence Pipeline (T3.6 / AUB-COR-01):**
  - Built `tools/fetch_openfda_labels.py` and `src/triagerag/rag/evidence.py` to ingest, cache, and chunk openFDA SPL drug labels into Tier-2 evidence chunks for clinical citation verification and rule grounding.
  - Ingested 688 section chunks across 62 generics in Waves 1–2 into `data/corpus/evidence_chunks.json`.
  - Chunks organized by canonical SPL sections (Boxed Warning, Contraindications, Warnings and Precautions, Drug Interactions, Specific Populations, Dosage/Administration, Overdosage, Adverse Reactions).
  - Explicit fail-closed handling for Indian-only formulations (`deriphyllin`, `etofylline`): recorded in `unretrieved_generics` with `no_evidence_chunk=True`, preventing fabricated FDA facts (Rule R3).
  - Recorded CC0 / public domain `license_tag='public_domain'` and full Provenance on every chunk.
  - Established offline recorded test fixtures in `tests/fixtures/openfda/`; added test suite `tests/unit/test_aub_phase3_openfda.py` (6 tests).
- **Contextual Chunking Research Arm (T3.5 / AUB-COR-03):**
  - Implemented `extract_if_condition` in `src/triagerag/rag/chunking.py` and updated `build_contextual_header` to optionally prepend root governing conditions (`Governing Context: <condition>`) to dependent child nodes (`idx > 1`) in `indexed_text`.
  - Preserved verbatim `chunk.text` and `content_hash` 100% untouched for exact span citation verification.
  - Added `contextual_chunking: bool = False` configuration flag in `data/retrieval/config.yaml` and `RetrievalConfig`.
  - Added `bm25_contextual` arm to `eval/run_retrieval_ablation.py` evaluated under deterministic `decide_backend()`.
  - Added test suite `tests/unit/test_aub_phase3_contextual_chunking.py` (8 tests).
- **Document Licensing Tags and Provenance Strictness (T3.4 / HD-9):**
  - Added `license_tag: Literal["synthetic", "public_domain", "cc_by_nc_sa", "restricted"]` to `ProtocolFrontmatter`, `ProtocolChunk`, `RetrievedChunk`, and `CorpusManifestEntry`.
  - Updated all 65 protocol frontmatters and `data/corpus/manifest.yaml` with `license_tag: synthetic`.
  - Hardened `.gitignore` to strictly exclude non-synthetic raw evidence (`data/evidence_raw/*`), restricted clinical guidelines (`data/protocols_restricted/*`), and local dense indexes (`data/indexes_local/*`).
  - Added test suite `tests/unit/test_aub_phase3_licensing.py` (4 tests).
- **Content-Addressed Node Identifiers and Dual-Key Aliases (T3.3 / AUB-COR-02):**
  - Implemented `canonicalize_node_text` (NFKC normalization, list prefix stripping, LF newline normalization, line trim) and `compute_node_hash`: `{chunk_id}_{hash8(canonical_text)}`.
  - Node IDs are completely invariant to line reordering, node insertion, and list renumbering.
  - Built dual-key backward compatibility: `ProtocolChunk` and `RetrievedChunk` store canonical `chunk_id` and `legacy_id` (`{chunk_id}_NODE_{i}`).
  - Created `data/corpus/node_aliases.yaml` (552 aliases) and `src/triagerag/rag/aliases.py` with transparent resolution across citation verification, evaluation benchmarks, and API responses. 0 collisions across corpus.
  - Added test suite `tests/unit/test_aub_phase3_content_ids.py` (6 tests).
- **Deterministic Synthetic Protocol Generator (T3.2):**
  - Created `tools/generate_synthetic_protocols.py` featuring bit-for-bit seeded determinism (`seed: 42`), template variation, and non-overwriting manual protocol protection.
  - Strictly enforced Rule R9 (zero numeric doses in any synthetic protocol markdown).
  - Added test suite `tests/unit/test_aub_phase3_generator.py` (4 tests).
- **Synthetic Protocol Corpus Expansion Across 36 Syndromes (T3.1 / AUB-COR-01):**
  - Expanded synthetic protocol coverage from 6 to 65 documents (6 manual baselines + 59 generated) across 36 controlled syndromes.
  - Generated 617 total structured chunks with 8–10 decision nodes per syndrome.
  - Added neonate and second paediatric protocols (`neonate_hypoglycemia_protocol.md`, `paediatric_asthma_protocol.md`, `neonate_jaundice_protocol.md`).
  - Injected cross-syndrome vocabulary distractors and alternative protocol versions.
  - Candidate pools exceed $k=5$ across all partitions; ingestion report shows 0 quarantined files and 100% round-trip invariant verification.
  - Added test suite `tests/unit/test_aub_phase3_corpus.py` (7 tests).
- **Architecture Decision Record:**
  - Authored **ADR-0012** in `docs/adr/0012-corpus-growth-and-content-addressed-nodes.md`.

## [Unreleased] - AUB Phase 2: Patient-Aware Retrieval

### Added & Hardened
- **Reachable Vitals-Only Syndrome Inference Path & HD-4 Confirmation Gate (T2.7 / HD-4):**
  - Resolved unreachable vitals-only syndrome inference (where 0/56 cases previously reached candidate search, failing closed under `EMPTY_QUERY`).
  - Synthesized candidate queries for unrouted presentations (`suspected_syndrome is None`) from acute presenting vitals cues (`syndrome_cue: true` in `data/retrieval/cues.yaml`).
  - Expanded candidate search pool across protocols and applied predicate-conditioned rescoring to identify winning syndrome candidates.
  - Implemented margin-based discrimination: requires relative margin $\ge 0.25$ between top distinct syndromes; cleanly abstains with `AbstainCode.AMBIGUOUS_MARGIN` on ambiguous vitals presentations.
  - When candidate margin is clear, returns `AbstainCode.SYNDROME_INFERRED` with candidate chunks restricted strictly to the winning inferred syndrome.
  - Enforced HD-4 clinical confirmation gate in `orchestrator.py` / `plan_verifier.py`: all verified plan steps generated under `SYNDROME_INFERRED` are capped at `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION` (inferred syndromes never auto-approve plan steps).
  - Added unit test suite `tests/unit/test_aub_phase2_inference.py` (7 tests).
  - Authored **ADR-0011** in `docs/adr/0011-patient-aware-retrieval-scoring.md`.
- **Score-Scale Integrity Across Retrieval Backends (T2.6 / AUB-RET-02):**
  - Hardened `LexicalOverlapReranker` in `src/triagerag/rag/hybrid.py`: removed arbitrary 1.5x score inflation (`1 + 0.5 * overlap`); scores are now bounded by `base_score * (1.0 - boost * (1.0 - overlap_ratio))` such that maximum score never exceeds unreranked base score.
  - Eliminated artificial RRF-to-BM25 rescaling (`max_bm25 / max_rrf`) in `HybridRRFRetriever.search`: hybrid retrievers now emit authentic, unmanipulated Reciprocal Rank Fusion scores.
  - Separated ranking scores from abstention confidence scores; introduced backend-specific confidence normalization contracts in `src/triagerag/rag/abstain.py` mapping raw backend scores onto a calibrated $[0.0, 1.0)$ scale:
    - BM25: $s / (s + 1.0)$
    - Hybrid RRF: $s / \text{max\_theoretical\_rrf}$
    - Char-Ngram: $s / (k_1 + 1.0)$
  - Threaded `backend` identity to `evaluate_abstention_with_code` from `retrieve_protocol_chunks`.
  - Added unit test suite `tests/unit/test_aub_phase2_scale_integrity.py` (4 tests) verifying uninflated reranker scores, authentic RRF output, confidence normalization contracts, and cross-backend threshold stability.
- **Query and Index Token Hygiene (T2.5 / AUB-RET-06):**
  - Enhanced `ClinicalTokenizer` in `src/triagerag/rag/index.py` with `tokenize_raw` (extracting clean raw words without stem/synonym expansions) and `tokenize_query_weighted` (emitting deduplicated tokens with explicit class weights).
  - Configured explicit token class weights in `data/retrieval/config.yaml`: `raw_token_weight: 1.0`, `stem_token_weight: 0.8`, `synonym_token_weight: 0.6`, `cue_token_weight: 0.7`.
  - Fixed BM25 document length statistics in `_PopulationBM25Stats` and `BM25ClinicalIndex`: document length (`dl`) now strictly counts discriminative raw words, preventing multi-word stems, synonyms, and acronyms from inflating document length or penalizing documents during length normalisation.
  - Stripped non-discriminative header fragments (redundant syndrome tokens, `'node'`, and positional digits) from `chunk.indexed_text` in `build_contextual_header`, while preserving full display headers on `chunk.display_header`.
  - Added unit test and ablation suite `tests/unit/test_aub_phase2_hygiene.py` (5 tests) demonstrating query token deduplication, class weighting, document length ablation before vs after, header fragment stripping, and zero degradation across golden syndrome retrieval fixtures.
- **Patient-Conditioned Retrieval Scoring (T2.4 / AUB-RET-01):**
  - Implemented `src/triagerag/rag/scoring.py` with `calculate_node_predicate_score` and `rescore_chunks_with_patient_predicates`.
  - Defined deterministic scoring model: $Score = BM25 + \lambda \cdot \text{satisfied\_matches} - \mu \cdot \text{active\_conflicts}$, calibrated with $\lambda=1.0, \mu=2.0$ in `data/retrieval/config.yaml`.
  - Added deterministic tie-breaking sorted by `(-round(score, decimals), chunk_id)` for rock-solid stability across repeat runs.
  - Connected scoring into `src/triagerag/rag/retrieve.py` (`RetrievalContext`, `build_retrieval_query` with synthetic cues, and rescoring pipeline).
  - Maintained fail-closed handling of uncertainty: `UNKNOWN` patient predicates add 0 match and 0 conflict.
  - Added unit test suite `tests/unit/test_aub_phase2_scoring.py` (9 tests) verifying hand-computed scores, deterministic tie-breaking, and paired-patient top-node flips across all 6 syndromes (`chest_pain`, `anaphylaxis`, `altered_mental_status`, `hypoglycemia`, `paediatric_sepsis`, `severe_asthma`).
- **Synthetic Retrieval Cues and Vocabulary Expansion (T2.3 / HD-16):**
  - Created `data/retrieval/cues.yaml` mapping 17 structured patient predicates to explicit protocol vocabulary terms.
  - Implemented `src/triagerag/rag/cues.py` with typed models (`PredicateCueMapping`, `RetrievalCuesConfig`) and deterministic term deduplication.
  - Added `expand_predicates_to_cues` for deterministic query bridging without uncontrolled synonym expansion.
  - Enforced strict architectural isolation: verified clinical rule engine (`triagerag.engine`) never imports from `cues.py` or references `cues.yaml`.
  - Integrated cues schema validation into `tools/validate_data.py`.
  - Added unit test suite `tests/unit/test_aub_phase2_cues.py` (5 tests).
- **Patient-Aware Node Predicates and Applicability Metadata (T2.2 / D2):**
  - Created `data/retrieval/node_predicates.yaml` providing sidecar applicability metadata for all 21 IF/THEN decision nodes across the 6 synthetic protocols.
  - Supported `requires_predicates`, `contraindicated_by`, `always_applicable`, and `predicate_review_required`.
  - Enforced that every active decision node declares at least one valid predicate or explicit `always_applicable: true`.
  - Extended `ProtocolChunk` in `src/triagerag/rag/chunking.py` and connected ingestion in `src/triagerag/rag/ingest.py` to attach predicate declarations without altering verbatim node text or violating the line-based round-trip invariant.
  - Implemented typed validator in `src/triagerag/rag/node_predicates.py` and integrated into `tools/validate_data.py`.
  - Added unit test suite `tests/unit/test_aub_phase2_node_predicates.py` (6 tests).
- **Structured Retrieval Predicate Vocabulary (T2.1 / D2):**
  - Created `data/retrieval/predicates.yaml` containing 17 typed retrieval predicates with explicit `source_status: SYNTHETIC_AUTHORED` provenance.
  - Implemented `src/triagerag/rag/predicates.py` with typed Pydantic models (`PredicateDefinition`, `PredicateVocabularyConfig`).
  - Enforced strict target field validation against real `Patient` schema fields (`vitals.*`, `age.*`, `medications`, `allergies`, etc.); rejected invalid fields, unsupported operators, and duplicate predicate IDs.
  - Implemented tri-state evaluation semantics (`SATISFIED`, `NOT_SATISFIED`, `UNKNOWN`); unknown, missing, or unobtainable patient data strictly evaluates to `UNKNOWN` and never silently becomes `False`.
  - Added `SourceStatus.SYNTHETIC_AUTHORED` and `ContentOrigin.AGENT_DRAFT_SYNTHETIC` to contracts enum.
  - Verified architectural isolation: clinical rule engine (`triagerag.engine`) never imports or reads retrieval predicates.
  - Added unit test suite `tests/unit/test_aub_phase2_predicates.py` (7 tests).
  - Integrated predicate validation into `tools/validate_data.py`.

## [0.3.1] - 2026-10-31 - AUB Phase 1: Trust and Honesty of Outputs

### Fixed & Hardened
- **Frontend Component Test Expansion and Scope Rendering (T1.7 / AUB-UX-03):**
  - Expanded Vitest component test suite from 8 tests to 36 tests (+28 tests):
    - `ExplanationSection.test.tsx` (10 tests): headline and summary, UNVERIFIED retrieval abstention display, BLOCKED / CHECKED_ALERTS styling, absence of bare CLEAR, completed vs unresolved checks, collapsible 9-stage execution timeline, generation disclosure.
    - `RetrievalView.test.tsx` (8 tests): chunk listings, abstention banner with gate codes (`NO_POPULATION_COVERAGE`, `NO_RESULTS`, `LOW_CONFIDENCE`), fallback mode alert, "How Retrieval Worked" mechanics toggle, lexical ranking disclosure.
    - `VerifiedPlanView.test.tsx` (6 tests): empty state, badges for `APPROVED`, `BLOCKED_STRUCK_THROUGH`, `FLAGGED_HIGH`, `REQUIRES_CLINICIAN_CONFIRMATION`, and expandable citation quoted spans.
    - `SkippedChecksList.test.tsx` (4 tests): empty state, total unverified count with Fail-Closed notice, rule IDs and types, missing field badges, and intake callback.
  - Rendered explicit "Completed Checks" vs "Unresolved Checks & Scope" cards in `ExplanationSection.tsx`.
  - Added missing `REQUIRES_CLINICIAN_CONFIRMATION` to TypeScript `StepStatus` schema in `web/src/types/api.ts`.
- **Pipeline Decomposition into Seven Typed Stages (T1.6 / AUB-OPS-02):**
  - Refactored monolithic `run_triage` in `src/triagerag/orchestrator.py` into 7 typed, pure pipeline stages:
    1. `stage_normalise`: Patient data normalization, age categorization, and physiological scoring.
    2. `stage_intake_checks`: Pass 1 baseline clinical rules, fail-closed coverage gaps, and formulary filters.
    3. `stage_retrieve`: Guarded candidate chunk retrieval and abstention handling.
    4. `stage_draft`: Fault-isolated mock LLM drafting with fallback coordination.
    5. `stage_verify`: Pass 2 verification, structured repair loop, logged overrides (R11 block protection), and verdict lattice.
    6. `stage_audit`: Cryptographic tamper-evident audit logging.
    7. `stage_explain`: EngineReport compilation and user-facing explanation assembly.
  - Introduced typed result dataclasses (`NormaliseStageResult`, `IntakeChecksStageResult`, `RetrieveStageResult`, `DraftStageResult`, `VerifyStageResult`, `AuditStageResult`, `ExplainStageResult`).
  - Enforced that no function in `src/triagerag/orchestrator.py` exceeds 120 lines (verified via programmatic AST inspection).
  - Added unit test suite `tests/unit/test_aub_phase1_orchestrator_pipeline.py`.
- **Fail-Closed Citation Child-Node Verification (T1.5 / AUB-GRD-02):**
  - Eliminated fail-open `except Exception: pass` during corpus re-ingestion for child node checks in `src/triagerag/verify/citations.py`.
  - Enforced fail-closed rejection returning `(False, 0.0, reason)` and logging structured error details if corpus ingestion fails.
  - Ensured plan verifier marks steps `CITATION_UNVERIFIED` and retains structured rejection reasons when corpus checks encounter IO/runtime exceptions.
  - Added unit regression tests in `tests/unit/test_aub_phase1_citations.py`.
- **Accurate Population-Coverage vs No-Results Abstention Semantics (T1.4 / AUB-ABS-01):**
  - Added `NO_RESULTS` to `AbstainCode` enum in `src/triagerag/contracts/enums.py`.
  - Disentangled population availability from retrieval match failure in `src/triagerag/rag/abstain.py`:
    - `not population_available` strictly returns `AbstainCode.NO_POPULATION_COVERAGE`.
    - `not scored_chunks` with `population_available=True` strictly returns `AbstainCode.NO_RESULTS`.
    - Low-scoring chunks below calibrated threshold return `AbstainCode.LOW_CONFIDENCE`.
  - Added unit test suite `tests/unit/test_aub_phase1_abstention.py` covering all outcome codes and backward-compatible tuple.
- **Canonical Shared Verdict Wording Contract and Ellipsis Correction (T1.3 / AUB-UX-02):**
  - Created canonical JSON contract `data/wording/verdicts.json` mirrored to `web/src/lib/wording.json` as the authoritative source of verdict copy.
  - Implemented `src/triagerag/contracts/wording.py` to provide typed access to shared labels, displays, badges, headlines, summaries, and actions.
  - Removed "order administration" from clear-state action recommendations across API and web.
  - Corrected `evidence_summary` ellipsis behaviour: `...` is appended only when text is genuinely truncated (> 140 chars).
  - Added snapshot and byte-for-byte drift tests in `tests/unit/test_aub_phase1_wording.py`.
- **Truthful Execution Explanations and Timeline Stage Accuracy (T1.2 / AUB-UX-01):**
  - Dynamically derived `completed_checks` from `checks_run - checks_skipped` and confirmed patient parameters; omitted false claims of completed allergy, DDI, and weight checks in the UNVERIFIED preset and when inputs are unknown.
  - Constrained machine-verified step counts in `completed_checks` to strictly count `APPROVED` steps, excluding struck-through, citation-unverified, and missing-data steps.
  - Enriched `unresolved_checks` with explicit line items for unverified and struck-through proposed steps as well as retrieval abstentions.
  - Updated `ExplanationSection.tsx` timeline stages: stage 2 reflects unmapped entities, stage 4 reflects skipped checks rather than false 'CLEAR', and stage 7 reflects real step approval statuses (`VERIFIED`, `PARTIALLY VERIFIED`, `UNVERIFIED`).
  - Added unit regression tests in `tests/unit/test_aub_phase1_explanations.py`.
- **Retrieval-Dependent Verdict Resolution and Non-Clear Headline Enforcement (T1.1 / AUB-VRD-01):**
  - Added `resolve_verdict_with_reason` in `src/triagerag/engine/verdict.py` accepting `retrieval_report` and `has_approved_steps`.
  - Added `unverified_reason: str | None = None` to `EngineReport` data contract.
  - Fail closed to `Verdict.UNVERIFIED` whenever retrieval abstains (`abstained=True` or `abstain_code != NONE`) or when zero steps achieve `APPROVED` status, prohibiting false `CHECKED_CLEAR` results.
  - Preserved strict lattice priority: `BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR`.
  - Enforced that verdict headlines for non-clear outcomes never contain the word "CLEAR", specializing headlines to `UNVERIFIED: Protocol Retrieval Abstained (<CODE>)` upon retrieval abstention.
  - Added comprehensive test suite `tests/unit/test_aub_phase1_verdict.py` (18 tests) parametrized over every `AbstainCode`.

## [0.3.2] - AUB Phase 0: Re-baseline and Hygiene

### Added
- **Validated Retrieval Backend Enum and Explain Route Support (T0.9 / AUB-OPS-01):**
  - Added `RetrievalBackend(StrEnum)` to `src/triagerag/contracts/enums.py` (`bm25`, `char_ngram`, `hybrid_rrf`, `hybrid_rrf_rerank`, and deprecated aliases).
  - Strongly typed `retrieval_backend` on `TriageApiRequest` and `ExplainApiRequest`, returning HTTP 422 for unrecognized backends rather than unhandled 500 exceptions.
  - Wired requested `retrieval_backend` through `/triage/explain` diagnostic route and included `backend` in trace payload.
  - Added API contract regression tests `test_invalid_retrieval_backend_returns_422` and `test_explain_route_honors_requested_retrieval_backend`.
- **Automated Documentation Metrics Generator and Drift Detection (T0.6 / AUB-DOC-01 / AUB-DOC-02):**
  - Created `tools/gen_docs_metrics.py` reading canonical JSON reports (`eval/reports/*.json`) and injecting exact values between `<!-- AUTOGEN:start:<tag> -->` and `<!-- AUTOGEN:end:<tag> -->` markers in `README.md`, `HANDOFF.md`, and `docs/evaluation/ENGINEERING_FINAL_RESULTS.md`.
  - Added `--check` flag to verify documentation numbers in CI.
  - Synchronized `pyproject.toml` version to `0.3.1`, corrected `dose.py` path to `dose_engine.py`, and eliminated ungrounded manual metric claims.
  - Added regression test `tests/unit/test_docs_drift.py`.
- **Hermetic Evaluation Dataset Lock (T0.1 / AUB-EVL-03):**
  - Added `eval/retrieval/dataset.lock` storing LF-normalized SHA-256 (`fdce9c040a0b...`) of `eval/retrieval/dataset.yaml`.
  - Refactored `tests/unit/test_fg4_eval_and_calibration.py` to verify against `dataset.lock` without invoking `git cat-file`, enabling hermetic execution in `.git`-less copies, archives, and container builds.
  - Added `test_dataset_lock_fails_on_tampered_dataset` regression test.

### Fixed & Hardened
- **Cryptographic Audit Chain Anchoring and Tail-Truncation Defense (T0.10 / AUB-OPS-03):**
  - Added `write_head_anchor()` to export current head hash to `.head` anchor files.
  - Extended `verify_audit_chain()` with `expected_head_hash` and `anchor_path` checks to verify final head match and detect tail truncation.
  - Added optional HMAC-SHA256 support via `hmac_key` in `compute_canonical_hash`, `append_audit_entry`, and `verify_audit_chain`.
  - Added unit regression tests in `tests/unit/test_audit.py`: `test_audit_chain_unanchored_tail_truncation_vulnerability`, `test_audit_chain_head_anchor_detects_truncation`, and `test_audit_chain_hmac_key_verification`.
- **Non-Mutating Evaluation Runners by Default (T0.8 / AUB-EVL-02):**
  - Updated `eval/run_retrieval.py`, `eval/run_retrieval_ablation.py`, and `eval/run_latency_benchmark.py` to default to `write_reports=False` / `write_report=False`.
  - Added explicit `--write` CLI flag and `eval-write` task in `tools/tasks.py`.
  - Prohibited automatic re-writing of `retrieval_baseline.json` on missing file checks.
  - Added regression test `test_eval_retrieval_leaves_tracked_reports_unmodified` verifying git working tree remains 100% clean when running evaluations.
- **Honest Architecture Descriptions and README Terminology (T0.7 / AUB-GEN-01 / AUB-DOC-03):**
  - Updated `README.md` to plainly qualify plan drafting as an offline deterministic mock generator (`FakeLLM`) implementing the `LLMProvider` contract.
  - Reconciled system descriptions to accurately characterize the audit log as a sequential SHA-256 hash chain and protocol search as lexical retrieval.
  - Added regression test `tests/unit/test_docs_honesty.py` forbidding "Merkle", "dense", and unqualified "LLM explains" claims in user documentation.
- **Strict Corpus Manifest Enforcement and Fail-Closed Ingestion (T0.5 / AUB-COR-04):**
  - Removed silent fallback manifest derivation and hardcoded `paediatric_sepsis_screen` alias in `load_corpus_manifest()`.
  - Ingestion now strictly fails closed, quarantining all protocol files when `manifest.yaml` is absent unless `derive_manifest=True` is explicitly passed.
  - Added CLI `--derive-manifest` flag to `corpus validate` and `corpus report`.
  - Added regression test `test_missing_manifest_quarantines_all_documents`.
- **Honest Retrieval Terminology (`char_ngram` Primary) (T0.4 / AUB-RET-05 / D6):**
  - Renamed internal attributes from `self.dense` to `self.char_ngram` in `HybridRRFRetriever`.
  - Added runtime `DeprecationWarning` when querying deprecated `HybridRRFRetriever.dense` or requesting backend `"dense"`.
  - Reconciled docstrings in `rag/hybrid.py`, `rag/index.py`, `cli.py`, and `docs/ARCHITECTURE.md` to consistently refer to character n-gram lexical retrieval rather than neural dense retrieval.
  - Added regression test `test_char_ngram_primary_and_dense_deprecation_warning`.
- **Threaded Explicit Configuration and Fail-Closed Config Resolution (T0.3 / AUB-RET-04):**
  - Updated `CharNgramRetriever` and `HybridRRFRetriever` to accept explicit `config`, `retrieval_context`, `synonyms`, and `data_dir` without hidden global fallbacks.
  - Removed unparameterized `load_retrieval_config()` calls inside `search()` methods, using bound instance config.
  - Made `load_retrieval_config()` strictly fail-closed (raising `FileNotFoundError` if config is missing in an explicit `data_dir`).
  - Added multi-environment isolation test `test_hybrid_retrievers_thread_explicit_config_and_data_dir`.
- **Removed Unused BM25 Parameters & Corrected Documentation (T0.2 / AUB-RET-03):**
  - Removed dead `global_idf` and `global_avgdl` parameters from `_PopulationBM25Stats.__init__` in `src/triagerag/rag/index.py`.
  - Reconciled docstrings in `index.py` with ADR-0009: population partitions strictly compute local non-negative smoothed IDF for population score invariance.
  - Added `test_population_bm25_stats_has_no_unused_parameters` regression test.

## [0.3.1] - 2026-10-30

### Added
- **Grounded Triage Explanation Layer (`TriageExplanation`):**
  - Implemented typed, deterministic explanation schema answering the six core user questions ("What did I submit?", "What did the system process?", "What information did retrieval find?", "Why did the system produce this result?", "What was successfully checked?", "What could not be established?").
  - Added `ExplanationSection.tsx` with executive verdict banners, plain language summaries, itemized rule consequences, permitted next steps, and a 9-stage execution pipeline timeline.
  - Authored comprehensive explainability documentation in `docs/USER_OUTPUT_GUIDE.md`.

### Fixed & Hardened
- **Clinical Syndrome Inference Hardening (Finding A, ADR-0007):**
  - Removed substring-based syndrome inference from `triage.py` and `PatientIntakeForm.tsx`.
  - Enforced that explicit clinician selection takes precedence; unconfirmed vitals-based candidate inference strictly caps verified steps at `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION`.
  - Added optional client-side suggestion chips requiring explicit clinician confirmation before applying.
- **Untrusted Chief Complaint Isolation (Finding B, Rule R7):**
  - Fixed route handler in `triage.py`: `include_complaint_in_llm` is strictly opt-in (default `False`). The presence of narrative text never automatically passes it to the LLM.
  - Chief complaint text is completely excluded from guideline retrieval queries and index filters.
- **Intake State & Reference Presets (Finding C):**
  - Initial patient intake form state is clean and unpopulated (unknown vitals, unknown history, empty syndrome, empty narrative).
  - Added 1-Click Reference Case Presets (`ScenarioSelector.tsx`) for `BLOCK`, `HIGH`, `UNVERIFIED`, and `CHECKED_CLEAR` test scenarios with prominent demo badges and a "Clear to Blank" reset action.
- **Evidence Cards & Ranking Disclosure (Finding D & F):**
  - Added explicit BM25 lexical ranking disclosure to evidence cards clarifying that BM25 scores reflect keyword overlap against controlled vocabulary, not clinical confidence or probability.
  - Added prominent `SYNTHETIC CORPUS` badges to evidence cards and disclosures of synthetic-only text without numeric doses.
- **Evaluation Documentation Reconciliation (Finding E):**
  - Reconciled `docs/evaluation/ENGINEERING_FINAL_RESULTS.md` with exact values from machine-readable JSON artifacts (`eval/reports/retrieval_ablation.json`, `latency_benchmark.json`, `mutation.json`, `adversarial.json`).

## [0.3.0] - 2026-10-30

### Fixed & Hardened
- **Complete Removal of External LLM Integrations (Rule R1, R5):**
  - Completely removed external API provider dependencies, network adapters, and live cloud harnesses.
  - Standardized the generation layer on pure offline deterministic mock generation (`FakeLLM`) with all 7 test profiles preserved.
  - Eliminated silent fallbacks; application and API contracts explicitly report `generation_mode: "deterministic_mock"`.
- **Test Suite Report Mutation Isolation (WP E, WP K):**
  - Refactored `eval/run_latency_benchmark.py`, `eval/run_retrieval_ablation.py`, and `tools/gate_report.py` to accept output destinations and conditional report writing (`write_report=False`).
  - Isolated test fixtures in `tests/unit/test_rag_wp9_ops.py`, `tests/unit/test_rag_wp7_hybrid.py`, and `tests/unit/test_report_integrity.py` to write strictly to `tmp_path`.
  - Added `tests/integration/test_test_isolation.py` cryptographically verifying that test execution leaves git-tracked reports 100% byte-identical.
- **Provider Transparency & Observability (WP B, WP G):**
  - Introduced provider-neutral `ProviderMetadata` schema tracking `generation_mode`, `requested_profile`, `repair_attempted`, `repair_cycles`, and `retrieval_backend`.
  - Added `provider_info` to `TriageResponse`, API responses, and frontend observability strips.
- **Production Hybrid Retrieval Routing (WP A, WP D):**
  - Wired `HybridRRFRetriever` into production `RetrievalService` factory, `config.get_retrieval_backend()`, and API request schemas.
  - Implemented secondary tie-breaking on RRF scores (`(-score, chunk_id)`), ensuring deterministic ranking.
- **Security & Prompt Injection Hardening (WP H):**
  - Sanitized XML tag breakout patterns (`</untrusted_patient_reported_complaint>`) in patient-reported chief complaint prompt framing.
  - Updated pattern detectors and prompt sanitizers to strip hostile markup before protocol plan drafting.
- **Clinical Data Provenance State Machine (WP I):**
  - Formalized 4-state lifecycle (`PLACEHOLDER_UNRETRIEVED`, `RETRIEVED_UNREVIEWED`, `REVIEWED`, `REJECTED`).
  - Strengthened Pydantic validator `validate_verified_provenance` enforcing non-empty reviewer, resolved section ref, and valid source document for any verified claim.
  - Authored comprehensive governance specification `docs/safety/DATA_PROVENANCE_STATUS.md`.
- **Frontend Usability & Navigation Debloat (WP J):**
  - Debloated navigation: Removed Audit Chain, Red Team, Evidence, and 1-Click Reference Cases from active clinical workflow.
  - Re-framed text input as "Chief Complaint & Clinical Presentation" with active syndrome auto-routing and protocol plan shaping.
  - Added observability pills (Deterministic Mock, Hybrid RRF vs BM25) in navbar and clinical report.

## [0.2.2] - 2026-10-30

### Fixed
- **Engine Defect Sweep & Deterministic Safety Interlocks (WP-0: ENG-01..ENG-08):**
  - **ENG-01 (Lookback Precedence):** In `ClassInteractionRule` lookback loops, confirmed in-window triggers (`lookback_triggered`) strictly take precedence and emit `Severity.BLOCK` alerts. Timestamp evaluation evaluates all medications/ingredients first; missing timestamps only emit `SkippedCheck` if no confirmed trigger fired.
  - **ENG-02 (Plan Alert Identity & Deduplication):** `evaluate_plan` deduplicates alerts on `(rule_id, frozenset(alert.drug_ids))`. A baseline hit no longer hides a newly proposed drug matching the same rule, ensuring contraindications strike proposed plan steps.
  - **ENG-03 (Exhaustive Dose Status Handling):** Handled all dose statuses in `evaluate_plan` and `verify_plan`: `BELOW_MINIMUM` and `MAGNITUDE_WARNING` emit alerts and flag steps (`DOSE_BELOW_MIN` and `DOSE_MAGNITUDE_WARNING`); `UNVERIFIED_MISSING_CAP` fails closed to `SkippedCheck`.
  - **ENG-04 (Gross Overdose Policy):** Documented and preserved strict `xfail` regression test pending human clinical decision `HD-6` (hard-ceiling multiple for non-overridable BLOCK).
  - **ENG-05 (Step-Keyed Dose Reports):** Added `step_number` to `CalculatedDoseReport` and `Alert`. Keyed dose evaluations in `verify_plan` on `(step.step_number, step.drug_id)`, preventing multi-step collisions when repeat doses of the same drug are administered.
  - **ENG-07 (Relevance-Gated Rule Skips):** Gated plan-evaluation rule skips via `_is_rule_relevant`, preventing baseline DDI or intake skips from clumping unrelated plan steps (e.g. dextrose) and reducing alert fatigue.
  - **ENG-08 (Lookback In-Class Omission Guard):** Added fail-closed `SkippedCheck` when an in-class drug lacks an entry in `lookback_hours_by_ingredient`, and added data-lint in `tools/validate_data.py` enforcing lookback coverage for all class members.
  - **Allergy Precedence Fix:** Confirmed IgE anaphylaxis alerts take strict precedence over unknown reaction types on secondary class allergens.

  - **Formulary Route Validation:** `verify_plan` in `plan_verifier.py` strictly validates proposed administration routes against the drug's formulary-approved route options (`drug.routes`), flagging unapproved administration routes as `FLAGGED_HIGH`.
  - **Candidate-Pool Random Baseline:** Added `run_candidate_pool_random_baseline()` to `eval/run_retrieval.py` providing a true candidate-pool random ranking baseline (21.37% R@1, 79.92% R@5 on 4–6 candidate pools).
  - **Empirical Metrics Alignment:** Updated `README.md` to accurately disclose current benchmark results (73.21% test / 69.86% overall Recall@5, 100% routed / 0% unrouted under HD-1, 19/19 adversarial, 52/52 mutants killed, SHA-256 hash-chained audit log, and 10x tripwire `Severity.HIGH` qualification).

### Added
- **WP-0 Evaluation & Verification Hardening:**
  - **Rule-Isolation Harness:** Added `only_rules` isolation harness to `eval/run_golden.py`. Evaluates all 65 golden cases in complete isolation from redundant rules (100% pass).
  - **Differential Property Testing:** Implemented independent reference interpreter and Hypothesis test suite in `tests/property/test_engine_differential.py` running 1,000 synthetic patient permutations with 0 divergences.
  - **Route Verification Suite:** Added `tests/unit/test_route_and_verification_hardening.py` testing route validation and order completeness.
  - **ADR-0010:** Documented architectural decisions in `docs/adr/0010-engine-defect-sweep-and-rule-isolation.md`.
  - **Audit Regressions Suite:** Added `tests/unit/test_audit_regressions.py` covering ENG-01..ENG-08.

## [0.2.1] - 2026-10-29

### Fixed
- **Hard BLOCK Rule Check & Fail-Closed Safety Interlock (Rule R11, R2):**
  - Resolved `AllergyCrossReactivityRule` alert mapping: populates `Alert.drug_ids` with all active/proposed medications in `rule.target_class`, ensuring contraindications properly strike proposed administer steps.
  - Resolved `ClassInteractionRule` alert mapping: populates `Alert.drug_ids` with all active/proposed medications in `rule.class_a` or `rule.class_b`.
  - Resolved `DuplicationRule` alert mapping: cross-checks proposed plan administer steps against active medications to catch multi-agent class duplication.
  - Enforced `Verdict.BLOCKED` on unapproved formulary drugs: generates a synthetic `Severity.BLOCK` alert for unknown formulary agents in `plan_verifier.py`, forcing the lattice priority to `BLOCKED`.
  - Hardened `has_block` resolution in `orchestrator.py`: accounts for `BLOCKED_STRUCK_THROUGH` verified steps alongside alerts.
  - Strictly eliminated any override path for `BLOCK`: raises `PermissionError` when clinician overrides are attempted on `BLOCK` severity rules or blocked steps.
  - Added `ClinicalRegistry.get_rule(rule_id)` helper for rule lookup.
- **Missing, Unknown & Unresolved Data Fail-Closed Safety (Rule R2):**
  - Fail closed on missing/unscored vitals: when vital signs are missing or unscored in EWS scoring, `orchestrator.py` generates a `SkippedCheck` for physiological scoring and forces `Verdict.UNVERIFIED` (preventing false clearances).
  - Fail closed on unknown intake status: patient history with `medication_history_status` or `allergy_history_status` in (`"incomplete"`, `"unknown_unobtainable"`) generates explicit `SkippedCheck` entries and forces `Verdict.UNVERIFIED`.
  - Fail closed on unknown pregnancy in female/other patients: generates `INTAKE_PREGNANCY_STATUS` `SkippedCheck` and forces `Verdict.UNVERIFIED`.
  - Fail closed on unknown patient weight: unmeasured weight generates `INTAKE_PATIENT_WEIGHT` `SkippedCheck` and forces `Verdict.UNVERIFIED`.
  - Fail closed on unknown allergy reaction types: documented allergies with `reaction_type="unknown"` emit a `SkippedCheck` and resolve to `Verdict.UNVERIFIED`.
  - Fail closed on unresolved clinical entities: unmapped medications and allergens generate explicit `SkippedCheck` records and force `Verdict.UNVERIFIED`.
  - Fail closed on documented organ impairment coverage gaps: documented renal or hepatic impairment emits explicit `SkippedCheck` coverage gap records (`COVERAGE_GAP_RENAL_IMPAIRMENT`, `COVERAGE_GAP_HEPATIC_IMPAIRMENT`) and forces `Verdict.UNVERIFIED`.
  - Fail closed on ungrounded/unverified plan steps: `has_unverified_steps` checks for `CITATION_UNVERIFIED` and `UNVERIFIED_MISSING_DATA` steps, guaranteeing plan ungroundedness forces top-level `Verdict.UNVERIFIED`.
  - Accumulated plan skips from initial and repaired drafts into `checks_skipped` in `EngineReport`.
  - Enhanced UI transparency: Streamlit `render_unverified_section` explicitly enumerates all skipped checks with their rule ID, rule type, clinical reason, and missing fields.
- **Test Suite:**
  - Added comprehensive fail-closed regression tests in `tests/unit/test_fail_closed_checks.py` (13 tests). Total pytest suite passes at 213/213 (100% green).
- **Plan Grounding & Citation Verification Hardening:**
  - Case-preserving verbatim substring verification: eliminates case-insensitive bypasses so citations must match chunk text exactly.
  - Corpus-wide parent-only citation rejection: rejects parent whole-document citations even if child decision nodes are omitted from the retrieved subset.
  - Fail-closed drug action-cue binding: missing `drug_id` on administer/withhold steps immediately yields `MISSING_DRUG_ID` (`CITATION_UNVERIFIED`).
- **Test Suite:**
  - Added comprehensive test coverage in `tests/unit/test_block_and_citations_fixes.py` (7 tests). Total suite passes at 200/200.

## [0.2.0] - 2026-10-27

### Added
- **Part A (Debugging & Hardening Complete):**
  - Expanded mutation testing to 40 mutants (12 rule + 28 code-level) with 100.0% kill score.
  - Bounded 1-attempt LLM repair loop with untrusted text stripping (`src/triagerag/llm/repair.py`).
  - Strict Decimal clinical math scaling with 10x/1000x magnitude tripwires for pediatric weight-based dosing.
  - Pure clocks and frozen `OrchestratorConfig` guaranteeing pure deterministic evaluation (R12).
  - High-concurrency cryptographic audit logging with multiprocessing file locks and tamper detection.
- **Part B (TriageRAG Console — React Frontend with React Bits):**
  - FastAPI presentation adapter in `src/triagerag/api/` with typed Pydantic models matching core schemas.
  - Complete Single-Page Application in `web/` using React 18, Vite, TypeScript, and Tailwind CSS.
  - React Bits UI animations (`Particles`, `SplitText`, `BlurText`, `ShinyText`, `Magnet`, `SpotlightCard`, `CountUp`, `ClickSpark`).
  - Inviolable UX Safety rules (S1–S8): Static un-animated safety banners, alerts, blocked drugs, and skipped checks.
  - Fail-closed `ErrorBoundary` preventing inconsistent clinical state rendering on unexpected exceptions.
  - Mandatory clinical disclaimer banner on all pages and persistent in layout footer.
  - Interactive Golden Scenario loader (`BLOCK`, `UNVERIFIED`, `HIGH`, `CLEAN`) with 1-click live auto-run.
  - Debloated navigation: consolidated fragmented secondary technical views into unified `ClinicalIntelligencePage`.
  - Enforced biological invariant: male pregnancy is strictly locked to 'No' (Not Applicable) and auto-resets on sex toggles.
  - Streamlined intake flow: reduced 5 tabs to 2 intuitive steps with an All-in-One toggle and quick drug/allergy chips.
  - Auto-run on mount: Console initializes with active live clinical analysis rather than empty placeholders.
  - Red-Team Security Lab with adversarial prompt injection presets and engine isolation verification.
  - Interactive Registries & Audit chain viewer with client-side verification trigger.
  - ADR 0005: "Clinical UX Safety Architecture — UI Displays Decisions, Never Computes or Conceals Them".

## [0.1.0] - 2026-10-26

### Added
- Initial project scaffold and core architecture rules (AGENTS.md, .agent/rules/triagerag.md).
- Strict layer isolation contracts via import-linter.
- Frozen Pydantic v2 schemas: Provenance, Measured[T], Age, Patient, Vitals, ExplicitDose, PlanDraft, EngineReport.
- Four-state Verdict lattice: BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.
- Decimal-only numeric loader for YAML with 10x/1000x magnitude tripwires.
- Pure functional RuleEngine and DoseEngine with immutable registry.
- Synthetic guideline corpus with no numeric doses.
- Offline BM25 protocol index with acronym expansion and hard population filter.
- Verified plan pipeline with token scanning, verbatim citation checking, and repair loop.
- Cryptographic SHA-256 audit chain with file locking and tamper detection.
- Streamlit clinical UI (fixed banner, no bare CLEAR, 4 scenarios) and Typer CLI tools.
- Metamorphic testing suite (3 transformations: brand/generic, reordering, equivalent units).
- Adversarial prompt injection suite (9 combinations: isolated, delimited, drug-hijack neutralization).
- Mutation testing runner (12 critical BLOCK/HIGH rules tested with 100.0% kill score).
- Retrieval benchmark suite (32 pairs: 100.0% Recall@5, 0.896 MRR, 100.0% Abstain Accuracy).
- Multi-arm ablation study harness comparing Arm A, Arm B, and Arm C to `eval/reports/ablation.md`.
- Automated gating and cross-platform task runner via `tools/tasks.py`.
