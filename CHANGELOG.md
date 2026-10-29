# Changelog

All notable changes to TriageRAG will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
