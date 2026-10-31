# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** AUB Phase 2 (Patient-Aware Retrieval) completed on branch `aub/phase-2-patient-aware-retrieval`. Tasks T2.1 through T2.7 implemented, verified, and documented with ADR-0011 and updated status ledger. Overall Test Recall@1 = 71.43% (up from 39.29%), Test Recall@5 = 98.21% (up from 73.21%), Vitals-Only Recall@1 = 73.33% (up from 0.00%), Wrong-Protocol Rate = 0.0000. All 295 unit tests passing (294 passed, 1 xfailed for HD-6).
- **Verification:** All gates green:
  - **294 passed, 1 xfailed (HD-6 non-overridable overdose BLOCK), 0 failed** in Pytest test suite (including unit, integration, property, UI smoke, safety boundary, intake hardening, WP0–WP9 RAG suites, test isolation, route verification, differential engine, and Phase 2 suites).
  - **8/8 Vitest frontend unit & component tests green.**
  - **0 lint / format errors** (Python ruff check & format; 159 files checked).
  - **0 type errors** (Python mypy strict in `src/` & TypeScript `tsc --noEmit`).
  - **0 import isolation contract violations** (import-linter: 2 contracts kept, 0 broken).
  - **Vite production build succeeds** (bundle compiled in ~2s).
  - **Zero tracked report mutations**: Running `pytest` does not dirty git working tree.
  - **52/52 mutants killed** (100% kill score).
  - **65/65 Golden cases green** (100% recall on BLOCK and HIGH contraindications).
  - **19/19 Adversarial prompt injection attacks neutralized.**
  - **4-Arm Retrieval Ablation**: All 4 arms benchmarked across 224 cases with 0.0 wrong-protocol rate and 100% hard-negative abstention recall.

## AUB Phase 2 Deliverables Summary

1. **T2.1 / D2 — Structured Clinical Predicate Vocabulary (`af6a410`):**
   - 17 synthetic predicates (`data/retrieval/predicates.yaml`) with tri-state evaluation (`SATISFIED`, `UNSATISFIED`, `UNKNOWN`) in `src/triagerag/rag/predicates.py`. Strict clinical engine isolation upheld.
2. **T2.2 / D2 — Protocol Node Applicability Metadata (`93e5521`):**
   - 21 decision nodes catalogued in `data/retrieval/node_predicates.yaml` with `requires_predicates`, `contraindicated_by`, and `always_applicable`. Attached to `ProtocolChunk` during ingestion.
3. **T2.3 / HD-16 — Synthetic Retrieval Cues & Query Expansion (`e73e69b`):**
   - Mapped 17 patient predicates to protocol vocabulary in `data/retrieval/cues.yaml` and `src/triagerag/rag/cues.py`. Distinguished presenting findings (`syndrome_cue: true`) from qualifiers (`syndrome_cue: false`).
4. **T2.4 / AUB-RET-01 — Patient-Conditioned Retrieval Scoring (`5f26092`):**
   - Implemented linear scoring model $Score = BM25 + \lambda \times \text{matches} - \mu \times \text{conflicts}$ in `src/triagerag/rag/scoring.py` with deterministic tie-breaking sorted by `(-round(score, 4), chunk_id)`.
5. **T2.5 / AUB-RET-06 — Query and Index Token Hygiene (`dbe44bf`):**
   - Added `tokenize_raw` so BM25 document length strictly counts discriminative raw words, avoiding length normalisation penalties from synonyms/stems. Cleaned `indexed_text` and preserved `display_header` for citations.
6. **T2.6 / AUB-RET-02 — Score-Scale Integrity Across Retrieval Backends (`17b0d90`):**
   - Removed 1.5x reranker multiplier; bounded reranked score $\le$ base score; eliminated artificial RRF-to-BM25 rescaling; added $[0.0, 1.0)$ confidence normalization.
7. **T2.7 / HD-4 — Reachable Vitals-Only Syndrome Inference Path (`d27dc07`):**
   - Re-enabled vitals-only triage candidate retrieval using presenting vitals cues; implemented margin-based discrimination ($\ge 0.25$ required, else `AMBIGUOUS_MARGIN`); enforced HD-4 clinical confirmation gate in `orchestrator.py` capping all verified steps at `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION`.
8. **ADR-0011 & Documentation Ledger (`da14533`):**
   - Authored `docs/adr/0011-patient-aware-retrieval-scoring.md` and updated `docs/AUB_STATUS.md` and `CHANGELOG.md`.

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
