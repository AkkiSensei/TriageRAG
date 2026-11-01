# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** AUB Phase 6 (Deterministic Engine, Schema V2, and Rule Expansion) completed on branch `aub/phase-6-engine-rules`. Tasks T6.0 through T6.6 implemented, verified, tested, and documented with ADR-0015 and updated status ledger (`docs/AUB_STATUS.md`).
- **Target Milestones Completed:**
  - **T6.0:** Trust policy (`TrustMode.STRICT`, `TrustMode.DEMO`), candidate rule unverified counters, UI/CLI badges (`TRUST_POLICY.md`).
  - **T6.1:** Schema V2 backward-compatible models (`ConditionContraindicationRule`, `LabInterlockRule`, `RouteConcentrationRule`, `OrganFunctionRule`, `CoAdministrationRule`, `RateLimitRule`, Patient conditions/labs/impairment, Step V2).
  - **T6.2:** Dose engine expansion: `calculate_administration_volume`, IM route volume limit (> 3.0 mL warning), `verify_dosing_intervals` step frequency and lookback, `verify_administration_rate`, `daily_max` mass semantics.
  - **T6.3:** Class taxonomy (~60 generics across Waves 1–3 from AUB §11), 34 Indian brand aliases (`data/aliases.yaml`), FDC multi-ingredient expansion, strength token stripping, LASA auto-resolve tripwire.
  - **T6.4:** Candidate rules batches 1, 2, 3 (40 candidate rules authored in `data/rules_candidates/` per AUB Part II - A).
  - **T6.5:** Rule coverage matrix and alert fatigue gate (`tools/rule_coverage.py`), golden suite expanded to 86 cases (100% green on all 12 shipped rules), 0.52 alerts/patient, 0.0% false-alert rate on negatives.
  - **T6.6:** Evidence-grounded candidate rule mining pipeline (`tools/mine_rules.py`), 5 deterministic integrity validators, 100% validator pass rate, 30-rule gold set benchmarking, clinician review queue published (`docs/REVIEW_QUEUE.md`).
- **Core Results & Verifications:**
  - **100% pass rate** on all 38 Phase 6 unit tests across 7 dedicated test modules (`test_aub_phase6_*.py`).
  - **100% pass rate** across entire test suite (468 passed, 1 xfailed under HD-6).
  - **0 lint / format errors** (Python ruff check & format across all 179 files).
  - **0 type errors** (Python mypy strict in `src/`, `tools/`, `eval/`, `tests/` & TypeScript `tsc --noEmit`).
  - **0 import isolation contract violations** (import-linter).
  - **Zero tracked report mutations**: Working tree leaves git status 100% clean.
  - **100% offline execution**: zero network calls.

## AUB Phase 6 Deliverables Summary

1. **T6.0 — Trust Policy & Verification Counters (`6f1e8ba`):**
   - Authored `docs/safety/TRUST_POLICY.md`.
   - Added `TrustMode` (`STRICT`, `DEMO`) in `src/triagerag/contracts/enums.py`.
   - `STRICT` mode excludes unverified candidate rules and surfaces unverified rule counts.
   - `DEMO` mode evaluates candidate rules with explicit `UNSOURCED DRAFT` disclosures in CLI and UI wristbands.
   - Added `tests/unit/test_aub_phase6_trust_policy.py` (6 tests).

2. **T6.1 — Schema V2 Rule Models & Patient Extensions (`e2d9d28`):**
   - Added 6 Schema V2 rule models in `src/triagerag/contracts/rules_schema.py`.
   - Extended `Patient` with `conditions`, `labs`, `renal_impairment`, `hepatic_impairment`.
   - Extended `PlanStepDraft` with concentration, diluent, rate, frequency, relative timing.
   - Preserved 100% backward compatibility for all 12 shipped rules.
   - Added `tests/unit/test_aub_phase6_schema_v2.py` (5 tests).

3. **T6.2 — Dose Engine Expansion (`299004e`):**
   - Added `calculate_administration_volume` computing volumes in mL with route tripwires (IM > 3.0 mL warning).
   - Added `verify_dosing_intervals` tracking repeat intervals across steps and absolute lookbacks against patient medication history.
   - Added `verify_administration_rate` and harmonized `daily_max` mass semantics.
   - Added `tests/unit/test_aub_phase6_dose_engine.py` (7 tests).

4. **T6.3 — Class Taxonomy, Indian Aliases & FDC Resolution (`740aced`):**
   - Expanded `data/classes.yaml` with ~60 emergency generics across Waves 1–3 from AUB §11.
   - Added 34 Indian single- and multi-ingredient brand aliases to `data/aliases.yaml` (Augmentin, Dolo 650, Combiflam, Deriphyllin, etc.).
   - Added multi-ingredient FDC expansion, strength token stripping, and LASA auto-resolve protection (`LASA_PAIRS`).
   - Added `tests/unit/test_aub_phase6_classes_and_fdc.py` (6 tests).

5. **T6.4 — Source-Traceable Candidate Batches (`0c15b9e`):**
   - Authored 40 candidate rules across 3 batches adhering to AUB Part II - A:
     - `batch_1.yaml` (15 rules: CV-05, CV-12, CV-17, CNS-01, CNS-04, CNS-11, CNS-12, AC-01, AC-02, EN-01, EN-03, ID-01, DUP-03, DUP-04, AN-08)
     - `batch_2.yaml` (15 rules: CV-09, CV-10, CV-16, CV-18, AN-01, AN-02, AN-03, AC-06, EN-12, ID-19, VL-05, CV-14, CV-19, CNS-16, AN-09)
     - `batch_3.yaml` (10 rules: NE-01, NE-03, ID-10, EN-06, AC-08, AN-10, EN-11, EN-09, NE-02, CNS-14)
   - Every candidate rule carries `source_status: PLACEHOLDER_UNRETRIEVED`, `verified: false`, `reviewer: null`, `content_origin: AGENT_DRAFT_UNSOURCED`.
   - Added `tests/unit/test_aub_phase6_candidate_rules.py` (5 tests).

6. **T6.5 — Rule Coverage Matrix and Alert Fatigue Gate (`43e0f64`):**
   - Built `tools/rule_coverage.py` asserting every active rule has >= 3 positive, >= 3 negative, and >= 1 boundary cases passing in isolation (`only_rules`).
   - Expanded `data/golden/shipped_ruleset_cases.yaml` from 65 to 86 cases (100% green on all shipped rules).
   - Monitored alert fatigue: 0.52 alerts/patient, 0.0% false-alert rate on negatives.
   - Added `tests/unit/test_aub_phase6_rule_coverage.py` (3 tests).

7. **T6.6 — Evidence-Grounded Candidate Rule Mining (`94851e7`):**
   - Built `tools/mine_rules.py` ingesting Tier-2 regulatory SPL evidence chunks (`data/corpus/evidence_chunks.json`).
   - Enforced 5 deterministic validators: quote in chunk, numbers in quote, ids resolve, schema valid, no duplicate key.
   - 100% of auto-sourced rules passed all 5 validators.
   - Published clinician review queue `docs/REVIEW_QUEUE.md` under HD-7 dual-control governance.
   - Created 30-rule reference gold set `data/rules_candidates/mining_gold_set.yaml`.
   - Added `tests/unit/test_aub_phase6_mine_rules.py` (6 tests).

8. **ADR-0015 & Status Ledger (`docs/adr/0015-schema-v2-and-deterministic-rule-engine-expansion.md`):**
   - Authored ADR-0015 and updated `docs/AUB_STATUS.md`.

## Next Steps for Future Phase (Phase 7 Boundary)

- **Phase 7 Scope:** Research extensions and showcase (Tasks T7.1 through T7.7).
  - T7.1 Controlled query expansion from predicates to protocol vocabulary.
  - T7.2 Local neural embedder + cross-encoder behind existing protocols.
  - T7.3 Visible RAG UI: restore Evidence view tab in report.
  - T7.4 Surfaces R-2/R-3: alert "Why?" drawer from label chunks; extractive Q&A.
  - T7.5 Security/ops: API auth stub + rate limit.
  - T7.6 Calibration, MMR, diagnostics: conformal calibration, MMR.
  - T7.7 Optional real provider (HD-14): local model ablation across models with CIs.
- **Rule of Governance:** One phase per session. Stop cleanly at Phase 6 boundary. Do not begin Phase 7 in this session.
- **No PRs:** Direct `git push origin aub/phase-6-engine-rules` only. Never create pull requests.
- **Target Defect Resolved:** **AUB-GRD-01** (Verifier approves clinically inapplicable protocol nodes because citation check only tested text presence, not patient applicability; "Administer immediately" dropping "repeat" qualifier).
- **Core Results & Verifications:**
  - **100% pass rate** on all 23 Phase 5 unit tests across 4 dedicated test modules (`test_aub_phase5_*.py`).
  - **100% pass rate** across entire test suite (431 passed, 1 xfailed under HD-6).
  - **0 lint / format errors** (Python ruff check & format).
  - **0 type errors** (Python mypy strict in `src/` & TypeScript `tsc --noEmit`).
  - **0 import isolation contract violations** (import-linter).
  - **Zero tracked report mutations**: Working tree leaves git status 100% clean.
  - **100% offline execution**: zero network calls.

## AUB Phase 5 Deliverables Summary

1. **T5.1 / AUB-GRD-01 — Patient Applicability Verification (`5f2f73a`, `78baa6d`):**
   - Authored `src/triagerag/verify/applicability.py`.
   - Evaluates cited protocol node preconditions (`requires_predicates`) and contraindications (`contraindicated_by`) against structured patient data with tri-state outcomes (`MET`, `NOT_MET`, `UNKNOWN`).
   - Supports both positional IDs and content-addressed IDs via bidirectional alias map with LRU caching (`load_node_aliases`, `load_reverse_node_aliases`).
   - Added `StepStatus.NOT_APPLICABLE` to backend enums and web client types.
   - Added `tests/unit/test_aub_phase5_applicability.py` (6 tests).

2. **T5.2 / AUB-GRD-01 — THEN-Clause Qualifier Verification (`8192d9f`, `78baa6d`):**
   - Authored `src/triagerag/verify/qualifiers.py`.
   - Detects conditional, temporal, and discretionary qualifiers ("repeat", "consider", "after", "following", "continue", "withhold", "until", "if") in source THEN clauses.
   - Refuses citations where essential qualifiers are dropped with `QUALIFIER_DROPPED: cited node contains '{qualifier}' qualifier ({description}) not present in drafted instruction`.
   - Added `tests/unit/test_aub_phase5_qualifiers.py` (11 tests).

3. **T5.3 / AUB-GRD-01 — Verdict Lattice Integration & Fail-Closed Safety (`87d5133`):**
   - Wired applicability and qualifier checks into `verify_plan` in `src/triagerag/verify/plan_verifier.py`.
   - Updated `orchestrator.py` so `has_unverified_steps` includes `NOT_APPLICABLE` and `REQUIRES_CLINICIAN_CONFIRMATION`.
   - Decisively fulfilled Reviewer B's core acceptance criterion: Normotensive vitals + anaphylaxis citing repeat node (`ANAPHYLAXIS_01_NODE_3`) resolves strictly to `Verdict.UNVERIFIED`, never `CHECKED_CLEAR`.
   - Added unit and FastAPI endpoint tests `tests/unit/test_aub_phase5_verdict.py` (3 tests).

4. **T5.4 / AUB-GEN-01 — Retrieval-Dependent FakeLLM Adversarial Profiles (`edab93a`):**
   - Extended `FakeLLMProfile` in `src/triagerag/llm/fake.py` with `RANKED_CHOICE`, `WRONG_BUT_MATCHING_CLAUSE`, and `QUALIFIER_DROP`.
   - `RANKED_CHOICE` dynamically drafts from top retrieved child chunk.
   - `WRONG_BUT_MATCHING_CLAUSE` cites an inapplicable clause, exercising the `NOT_APPLICABLE` verifier refusal path.
   - `QUALIFIER_DROP` cites a qualified node but drops the qualifier token, exercising the `QUALIFIER_DROPPED` / `CITATION_UNVERIFIED` verifier refusal path.
   - Added `tests/unit/test_aub_phase5_fake_llm.py` (3 tests).

5. **ADR-0014 & Status Ledger (`docs/adr/0014-applicability-aware-grounding-and-qualifier-verification.md`):**
   - Recorded architectural decisions, safety properties, and defect resolution in ADR-0014 and updated `docs/AUB_STATUS.md`.

## Next Steps for Future Phase (Phase 6 Boundary)

- **Phase 6 Scope:** Engine, schema v2 and rule expansion (Tasks T6.0 through T6.6).
- **Rule of Governance:** One phase per session. Stop cleanly at Phase 5 boundary. Do not begin Phase 6 in this session.

## Next Session Focus: AUB Phase 6 — Engine, Schema V2 and Rule Expansion

The next engineer will execute **AUB Phase 6: Engine, Schema V2 and Rule Expansion**:
- **T6.0 Pre-Implementation Review & Rule Expansion Scoping**: Audit candidate rules and formulary drugs.
- **T6.1 Schema V2 Migration**: Implement Patient schema v2 with tri-state temporal lookbacks, explicit renal/hepatic status, and strict provenance.
- **T6.2 Engine Rule Expansion**: Ingest and verify new clinical rules across DDI, allergy, duplicate therapy, and formulary bounds.
- **T6.3 Candidate Rule Ingestion Pipeline**: Ingestion tooling enforcing `source_status: PLACEHOLDER_UNRETRIEVED, verified: false, content_origin: AGENT_DRAFT_UNSOURCED`.
- **T6.4 Integration & Regression**: Full test coverage, golden suite expansion, and zero BLOCK override verification.

## Prior Phase Deliverables Summary (Phase 3)

1. **T3.1 / AUB-COR-01 — Synthetic Corpus Expansion Across 36 Syndromes (`85d0985`):**
   - Expanded protocol coverage from 6 to 65 documents (617 total chunks across 36 controlled syndromes). Added `tests/unit/test_aub_phase3_corpus.py` (7 tests).
2. **T3.2 — Deterministic Synthetic Protocol Generator Tooling (`6f49916`):**
   - Built `tools/generate_synthetic_protocols.py` featuring bit-for-bit seeded determinism (`seed: 42`). Added `tests/unit/test_aub_phase3_generator.py` (4 tests).
3. **T3.3 / AUB-COR-02 — Content-Addressed Node Identifiers and Dual-Key Aliases (`92f3b5d`):**
   - Implemented `{chunk_id}_{hash8(canonical_text)}` content hashes and `data/corpus/node_aliases.yaml` (552 aliases). Added `tests/unit/test_aub_phase3_content_ids.py` (6 tests).
4. **T3.4 / HD-9 — Document Licensing Tags and Source Provenance (`8b20795`):**
   - Added `license_tag` across schemas and docs. Added `tests/unit/test_aub_phase3_licensing.py` (4 tests).
5. **T3.5 / AUB-COR-03 — Contextual Chunking Research Arm (`a9c741f`):**
   - Built contextual header prepending. Added `tests/unit/test_aub_phase3_contextual_chunking.py` (8 tests).
6. **T3.6 — Tier-2 openFDA Regulatory Evidence Ingestion Pipeline (`ac21b62`):**
   - Ingested 688 section chunks across 62 generics in Waves 1–2. Added `tests/unit/test_aub_phase3_openfda.py` (6 tests).
7. **ADR-0012 & Documentation Ledger:**
   - Authored `docs/adr/0012-corpus-growth-and-content-addressed-nodes.md`.

## Prior Architecture Highlights

1. **Part A: Master Debugging & Mutation Hardening (tagged `debug-complete`):**
   - 40-mutant kill suite (`eval/run_mutation.py`) covering verdict lattice, lookbacks, withhold exemptions, citation groundings, drug-scan tokens, population filters, BLOCK override guards, dose math, and cryptographic audit.
   - Bounded 1-attempt LLM repair loop (`src/triagerag/llm/repair.py`).
   - Deterministic execution with pure clocks (`src/triagerag/orchestrator.py`).
   - Strict Decimal math with 10x/1000x tripwires (`src/triagerag/engine/dose_engine.py`).

2. **Part B: TriageRAG Console (tagged `fe-gate-1` through `fe-gate-7`):**
   - **FastAPI Presentation Adapter (`src/triagerag/api/`):** REST API with typed Pydantic models matching core domain contracts, exact string Decimal preservation, and OpenAPI schema generation (`web/openapi/openapi.json`).
   - **Modern Clinical Console (`web/`):** Built with React 18, TypeScript, Tailwind CSS, Vite, Lucide React, and React Query.
   - **React Bits Integration with Strict Safety UX Boundaries (ADR 0005):**
     - Decorative/educational micro-animations (`Particles`, `SplitText`, `BlurText`, `ShinyText`, `Magnet`, `SpotlightCard`, `CountUp`, `ClickSpark`) used in hero, navigation, and metrics.
     - **Inviolable S1 UX Guard:** Safety banners, alerts, blocked drugs, skipped checks, and disclaimers are **NEVER** animated, delayed, or obscured.
     - **Accessibility Guard:** `prefers-reduced-motion` and global user toggle (`useMotionOk()`, `<Motion>`) disable all animations instantly.
   - **Clinical Features:**
     - `PatientIntakeForm`: Tri-state uncertainty inputs (`measured`, `estimated`, `unknown`), golden scenario loader, and quarantined untrusted complaint box.
     - `SafetyBanner`: Static high-contrast banner with qualified wording (`CHECKED CLEAR (ruleset coverage: N active rules)`); never renders bare "CLEAR".
     - `ScoreCard`: Physiological early warning score with exact subscores and clinical band enums (`RED`, `ORANGE`, `YELLOW`, `GREEN`, `UNSCORED`).
     - `AlertsList`: Visual severity hierarchy, strikethrough for blocked drugs, and strict prohibition of BLOCK overrides.
     - `OverrideModal`: Audit-logged justification workflow for HIGH alerts requiring >= 15 character rationale.
     - `RedTeamPage`: Adversarial testing playground simulating prompt injections and demonstrating R7 engine isolation and R1 plan verification.
     - `RulesetPage` & `ProtocolsPage`: Searchable registries with provenance drawers and synthetic corpus watermarks.
     - `EvidencePage`: Live metrics dashboard displaying mutant matrices and ablation results.
     - `AuditPage`: SHA-256 sequential hash-chained audit trail viewer with one-click cryptographic chain verification.
     - `ErrorBoundary`: Fail-closed React component boundary preventing inconsistent clinical UI rendering upon unexpected exceptions.

## Verification Metrics Summary

<!-- AUTOGEN:start:verification-metrics -->
| Verification Suite | Scope | Target | Result | Status |
|:---|:---|:---:|:---:|:---:|
| **Python Linters** | Ruff check & format | 0 warnings | Clean | PASS |
| **Python Typing** | Mypy strict mode | 0 errors | Clean | PASS |
| **Layer Contracts** | Import-linter | 0 violations | Clean | PASS |
| **Backend Tests** | Pytest unit, integration, property | 100% | 236 passed, 1 xfailed (HD-6) | PASS |
| **Safety Boundary Tests** | AST scans & rule checks | 100% | 4/4 passed | PASS |
| **Golden Ruleset** | Shipped clinical cases & rule-isolation | 100% | 86/86 passed (100% in isolation) | PASS |
| **Mechanics Suite** | Edge cases & unit trips | 100% | 41/41 passed | PASS |
| **Metamorphic Suite** | Equivalence transformations | 100% | 3/3 passed | PASS |
| **Adversarial Suite** | Prompt injection attacks | 100% | 19/19 passed | PASS |
| **Mutation Testing** | Code & rule mutant kill rate | 100% | 52/52 killed | PASS |
| **Retrieval Benchmark** | 224-case node-level (136 dev / 88 test) | R@5 >= 65%, WrongProto == 0 | 73.21% Test R@5, 0.0 WrongProto | PASS |
| **Scale Latency** | 10,000-chunk lexical search | p95 < 50 ms | p95 = 6.69 ms | PASS |
| **Frontend Linters** | ESLint with strict safety rules | 0 warnings | Clean | PASS |
| **Frontend Typing** | TypeScript (`tsc --noEmit`) | 0 errors | Clean | PASS |
| **Frontend Tests** | Vitest unit & component specs | 100% | 8/8 passed | PASS |
| **Production Build** | Vite production bundle | < 2 MB | ~293 KB | PASS |
<!-- AUTOGEN:end:verification-metrics -->

## Verification & Execution Commands

```bash
# Full backend & evaluative verification
python tools/tasks.py verify

# Full frontend verification (lint, typecheck, vitest, build)
python tools/tasks.py web-verify

# Run mutation testing suite (40 mutants)
python eval/run_mutation.py

# Launch FastAPI backend API (port 8000)
python tools/tasks.py api

# Launch React frontend dev server (port 5173)
python tools/tasks.py web-dev

# Launch Streamlit fallback UI
python tools/tasks.py ui
```
