# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** **Comprehensive Backend Engineering Audit & Hardening Complete**. LangGraph (`langgraph>=0.2.0`) is the production workflow orchestration framework powering the primary request path (`/api/triage`, `orchestrator.py`), maintaining 100% equivalence with the established clinical ruleset, zero external neural calls, sub-millisecond overhead, and full fail-closed out-of-domain abstention gating.
- **Target Milestones Completed:**
  - **Backend Engineering Audit & Hardening:**
    - Conducted comprehensive forensic audit of all 9 backend layers (`contracts`, `normalize`, `engine`, `rag`, `llm`, `verify`, `orchestration`, `audit`, `api`).
    - Remediated Ask-the-Corpus stop-word & out-of-domain vulnerability (`BE-AUDIT-01`), guaranteeing fail-closed abstention when questions have zero clinical content overlap.
    - Preserved patient vitals and weight in `TriageResponse` schema, fixing frontend Care Steps display data loss (`PROP-01`).
    - Authored comprehensive architectural documentation: `docs/architecture/BACKEND_DIRECTORY_MAP.md`, `docs/architecture/BACKEND_ENGINEERING_GUIDE.md`, and `docs/final_audit/BACKEND_ENGINEERING_AUDIT.md`.
- **Target Milestones Completed:**
  - **LangGraph Integration (ADR 0017):** Built `src/triagerag/orchestration/langgraph_workflow.py` with strongly-typed `TriageGraphState` (TypedDict) and 11 distinct processing nodes.
  - **Explicit Conditional Routing:** Built `route_after_retrieve` (fail-closed protocol abstention under Rule R2) and `route_after_verify` (Rule R11 non-overridable BLOCK seal, Rule R2 UNVERIFIED seal, and verified authorization seal).
  - **FastAPI Integration:** Primary endpoint `POST /api/triage` routes directly through `run_triage_graph(...)`. Added runtime introspection endpoint `GET /api/triage/workflow`.
  - **Testing & Equivalence:** 21 dedicated unit, routing, concurrency, determinism, and equivalence tests in `tests/unit/test_langgraph_orchestration.py`. Full test suite clean: 534 passed, 1 xfailed (HD-6).
  - **Phase 0–6 Forensic Reconciliation:** Reconciled candidate rule counts (40 authored + 9 mined = 49 total candidate rules in `data/rules_candidates/`), verified that 86 golden test scenarios govern the 12 active shipped rules, clarified 3.0 mL IM volume threshold with status `NEEDS_SOURCE`, added dedicated isolation tests for `CoAdministrationRule`, synchronized documentation metrics via `tools/gen_docs_metrics.py`.
  - **T7.1 — Controlled Query Expansion:** Implemented `data/retrieval/expansion_terms.yaml` and `src/triagerag/rag/query_expansion.py` (`QueryExpansionResult`, `build_expanded_query`, fail-closed refusal to expand unknown predicates, inspectable `expansion_trace` and `expansion_mode` in `RetrievalReport`).
  - **T7.2 — Local Neural Embedding & Cross-Encoder Interface:** Implemented `src/triagerag/rag/neural_interface.py` defining `EmbeddingModel`, `CrossEncoderModel`, `NeuralDenseRetriever`, and `NeuralCrossEncoderReranker`. Enforced Human Decision Gate **HD-10** (unapproved models raise `NeuralModelApprovalError` and remain `BLOCKED_EXTERNAL`).
  - **T7.3 — Visible RAG Evidence Experience:** Updated React/TypeScript web frontend with prominent generator badges (`MOCK` vs `REAL`), query expansion traces, and chunk license disclosures across `RetrievalView.tsx`.
  - **T7.4 — Alert Why Drawer & Ask-the-Corpus Console:** Created `src/triagerag/rag/alert_why.py` (structured explanation of triggered rule, matched patient facts, unmeasured vitals, Rule R11 non-overridable severity rationale) and `src/triagerag/rag/ask_corpus.py` (extractive verbatim question answering with exact chunk citations). Mounted API endpoints `POST /api/corpus/ask` and `POST /api/triage/alert-why`. Integrated interactive UI drawers in `AlertsList.tsx` and `AskCorpusSection.tsx`.
  - **T7.5 — Security and Operations:** Created `src/triagerag/api/security.py` with `SlidingWindowRateLimiter` (sliding-window 429 response with `Retry-After` header), API key and Bearer token authentication boundary, and exempt paths. Added `@app.command("security-audit")` in `tools/tasks.py` supporting `pip-audit` and `npm audit`.
  - **T7.6 — Inferred-Mode MMR, Nearest-Miss Diagnostics & HD-12 Refusal:** Created `src/triagerag/rag/diagnostics.py` implementing `apply_mmr_rerank` ($\lambda=0.7$), `calculate_nearest_misses`, and `explain_chunk_predicates`. Enforced Human Decision Gate **HD-12** in `eval/retrieval/calibrate.py` raising `CalibrationDataRefusalError` when isotonic/conformal calibration is requested without verified clinician labels.
  - **T7.7 — Local Provider Architecture & Cassette Replay:** Created `src/triagerag/llm/cassette.py` with `CassetteEntry`, `CassetteTape`, and `CassetteReplayProvider` matching on canonical SHA-256 hashes of context and prompts. Enforced Human Decision Gate **HD-14** in `ApprovedLocalProvider` raising `LLMProviderApprovalError` for unapproved live neural models.
  - **Cross-Phase Integration:** Comprehensive integration test suite in `tests/integration/test_aub_phase7_cross_phase_integration.py` exercising complete end-to-end flows.

## Core Results & Verifications

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
| **Frontend Tests** | Vitest unit & component specs | 100% | 8/8 files, 52/52 tests passed | PASS |
| **Production Build** | Vite production bundle | < 2 MB | ~293 KB | PASS |
<!-- AUTOGEN:end:verification-metrics -->

- **100% pass rate** on all Phase 7 unit and integration tests across 6 dedicated test modules:
  - `tests/unit/test_aub_phase7_query_expansion.py` (5 tests)
  - `tests/unit/test_aub_phase7_neural_interface.py` (4 tests)
  - `tests/unit/test_aub_phase7_why_and_ask_corpus.py` (5 tests)
  - `tests/unit/test_aub_phase7_security.py` (4 tests)
  - `tests/unit/test_aub_phase7_diagnostics_and_mmr.py` (6 tests)
  - `tests/unit/test_aub_phase7_provider_cassettes.py` (4 tests)
  - `tests/integration/test_aub_phase7_cross_phase_integration.py` (6 tests)
- **100% pass rate** across full frontend suite (`vitest run` 52/52 tests passed across 8 test suites, TypeScript clean, Vite production bundle clean).
- **0 lint / format errors** (Python ruff check & format across codebase).
- **0 type errors** (Python mypy strict in `src/`, `tools/`, `eval/`, `tests/` & TypeScript `tsc --noEmit`).
- **0 import isolation contract violations** (import-linter).
- **Zero tracked report mutations**: Working tree leaves git status 100% clean.
- **100% offline execution**: zero network calls.

## Whole-Project Architecture & Human Decision Gates

Every Human Decision Gate from AUB.md is strictly preserved:
- **HD-1 / HD-2:** Paediatric age classification and vitals rule sourcing boundaries preserved.
- **HD-4:** Syndrome-inferred triage steps capped at `REQUIRES_CLINICIAN_CONFIRMATION`.
- **HD-6:** Overdose hard-ceiling multiple remains open; strict xfail ceiling tests preserved.
- **HD-7:** Candidate rules (49 total) remain in `data/rules_candidates/` under unreviewed draft status until human clinician sign-off.
- **HD-10:** Neural embedding/reranker models blocked offline (`BLOCKED_EXTERNAL`), raising `NeuralModelApprovalError`.
- **HD-12:** Isotonic/conformal probability calibration refused without verified clinician annotations (`CalibrationDataRefusalError`).
- **HD-14:** FakeLLM remains default offline generator; live neural models blocked (`BLOCKED_EXTERNAL`), raising `LLMProviderApprovalError`.
- **HD-15:** Fail-closed regulatory drug label evidence ingestion.
- **HD-16:** Retrieval cues remain strictly segregated from clinical rules.

## Git Rules (Rule 18)
- **Single branch:** Only `main` exists locally and on remote.
- **Direct push:** All commits are pushed directly (`git push origin main`). No pull requests are created.
- **Linear history:** Complete 70+ commit linear git history preserved without running `git init`.
