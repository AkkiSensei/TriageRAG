# Changelog

All notable changes to TriageRAG will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - AUB Phase 1: Trust and Honesty of Outputs

### Fixed & Hardened
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
