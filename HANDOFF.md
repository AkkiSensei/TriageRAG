# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** AUB Phase 5 (Applicability-Aware Grounding and Qualifier Verification) completed on branch `aub/phase-5-applicability-grounding`. Tasks T5.1 through T5.4 implemented, verified, and documented with ADR-0014 and updated status ledger (`docs/AUB_STATUS.md`).
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
| **Golden Ruleset** | Shipped clinical cases & rule-isolation | 100% | 65/65 passed (100% in isolation) | PASS |
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
