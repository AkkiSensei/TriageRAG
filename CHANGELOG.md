# Changelog

All notable changes to TriageRAG will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
