# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** AUB Phase 3 (Corpus Growth and Evidence Ingestion) completed on branch `aub/phase-3-corpus-expansion`. Tasks T3.1 through T3.6 implemented, verified, and documented with ADR-0012 and updated status ledger. Corpus expanded from 6 to 65 protocol documents (617 total chunks across 36 controlled syndromes), content-addressed node IDs deployed with zero collisions, dual-key legacy alias map established (552 aliases), licensing tags enforced, experimental contextual chunking arm added, and 688 Tier-2 openFDA regulatory evidence chunks ingested with strict Provenance. All 35 Phase 3 unit tests passing in 2.88s. All 295 prior unit tests passing (294 passed, 1 xfailed for HD-6).
- **Verification:** All gates green:
  - **100% pass rate** on all unit, integration, property, and RAG suites.
  - **0 lint / format errors** (Python ruff check & format).
  - **0 type errors** (Python mypy strict in `src/` & TypeScript `tsc --noEmit`).
  - **0 import isolation contract violations** (import-linter: 2 contracts kept, 0 broken).
  - **Zero tracked report mutations**: Running tests leaves git working tree clean.
  - **0 quarantined documents** during protocol ingestion; 100% round-trip invariant verified.
  - **0 numeric clinical doses** in any synthetic protocol markdown (Rule R9 verified).
  - **100% offline execution**: zero network calls during automated testing.

## AUB Phase 3 Deliverables Summary

1. **T3.1 / AUB-COR-01 — Synthetic Corpus Expansion Across 36 Syndromes (`85d0985`):**
   - Expanded protocol coverage from 6 to 65 documents (6 manual baseline documents, 57 adult protocols, 6 paediatric protocols, 2 neonatal protocols) across 36 controlled syndromes.
   - Generated 617 total structured chunks with 8–10 decision nodes per syndrome.
   - Candidate pools exceed $top\_k = 5$ across all partitions; ingestion report shows 0 quarantined files and 100% round-trip invariant verification. Added `tests/unit/test_aub_phase3_corpus.py` (7 tests).
2. **T3.2 — Deterministic Synthetic Protocol Generator Tooling (`6f49916`):**
   - Built `tools/generate_synthetic_protocols.py` featuring bit-for-bit seeded determinism (`seed: 42`), template variation, and non-overwriting manual protocol protection.
   - Enforced Rule R9: zero numeric dosages in synthetic protocol text. Added `tests/unit/test_aub_phase3_generator.py` (4 tests).
3. **T3.3 / AUB-COR-02 — Content-Addressed Node Identifiers and Dual-Key Aliases (`92f3b5d`):**
   - Implemented `canonicalize_node_text` (NFKC normalization, list prefix stripping, LF newline normalization, line trim) and `compute_node_hash`: `{chunk_id}_{hash8(canonical_text)}`.
   - Node identifiers are 100% invariant to line reordering, node insertion, and list renumbering.
   - Built dual-key backward compatibility: `ProtocolChunk` and `RetrievedChunk` store canonical `chunk_id` and `legacy_id` (`{chunk_id}_NODE_{i}`).
   - Created `data/corpus/node_aliases.yaml` (552 aliases) and `src/triagerag/rag/aliases.py` with transparent resolution across citation verification, evaluation benchmarks, and API responses. 0 collisions across corpus. Added `tests/unit/test_aub_phase3_content_ids.py` (6 tests).
4. **T3.4 / HD-9 — Document Licensing Tags and Source Provenance (`8b20795`):**
   - Added `license_tag: Literal["synthetic", "public_domain", "cc_by_nc_sa", "restricted"]` to `ProtocolFrontmatter`, `ProtocolChunk`, `RetrievedChunk`, and `CorpusManifestEntry`.
   - Updated all 65 protocol frontmatters and `data/corpus/manifest.yaml` with `license_tag: synthetic`.
   - Hardened `.gitignore` to strictly exclude non-synthetic raw evidence (`data/evidence_raw/*`), restricted clinical guidelines (`data/protocols_restricted/*`), and local dense indexes (`data/indexes_local/*`). Added `tests/unit/test_aub_phase3_licensing.py` (4 tests).
5. **T3.5 / AUB-COR-03 — Contextual Chunking Research Arm (`a9c741f`):**
   - Implemented `extract_if_condition` in `src/triagerag/rag/chunking.py` and updated `build_contextual_header` to optionally prepend root governing conditions (`Governing Context: <condition>`) to dependent child nodes (`idx > 1`) in `indexed_text`.
   - Preserved verbatim `chunk.text` and `content_hash` 100% untouched for exact span citation verification.
   - Added `contextual_chunking: bool = False` configuration flag in `data/retrieval/config.yaml` and `RetrievalConfig`.
   - Added `bm25_contextual` arm to `eval/run_retrieval_ablation.py` evaluated under deterministic `decide_backend()`. Added `tests/unit/test_aub_phase3_contextual_chunking.py` (8 tests).
6. **T3.6 — Tier-2 openFDA Regulatory Evidence Ingestion Pipeline (`ac21b62`):**
   - Built `tools/fetch_openfda_labels.py` and `src/triagerag/rag/evidence.py` to ingest, cache, and chunk openFDA SPL drug labels into Tier-2 evidence chunks for clinical citation verification and rule grounding.
   - Ingested 688 section chunks across 62 generics in Waves 1–2 into `data/corpus/evidence_chunks.json`.
   - Chunks organized by canonical SPL sections (Boxed Warning, Contraindications, Warnings and Precautions, Drug Interactions, Specific Populations, Dosage/Administration, Overdosage, Adverse Reactions).
   - Explicit fail-closed handling for Indian-only formulations (`deriphyllin`, `etofylline`): recorded in `unretrieved_generics` with `no_evidence_chunk=True`, preventing fabricated FDA facts (Rule R3).
   - Recorded CC0 / public domain `license_tag='public_domain'` and full Provenance on every chunk.
   - Established offline recorded test fixtures in `tests/fixtures/openfda/`; added test suite `tests/unit/test_aub_phase3_openfda.py` (6 tests).
7. **ADR-0012 & Documentation Ledger:**
   - Authored `docs/adr/0012-corpus-growth-and-content-addressed-nodes.md` and updated `docs/AUB_STATUS.md` and `CHANGELOG.md`.

## Next Session Focus: AUB Phase 4 — Evaluation Rebuild

The next engineer will execute **AUB Phase 4: Evaluation Rebuild (AUB-EVL-01)**:
- **T4.1 Template-grouped splits**: Split by scenario template/node-set, not random rows; freeze via dataset hash (`dataset.lock`).
- **T4.2 Labels with agreement**: Double-annotate a ~100-case subset; report Cohen's kappa; mark single-annotated labels clearly.
- **T4.3 Baselines**: Add position-prior per syndrome (always return the most frequent grade-2 node) next to random; report with paired CIs.
- **T4.4 Honest metrics**: Split `wrong_protocol_rate` into `false_accept_rate` and `wrong_syndrome_rate`; use real confidences for ECE; report Recall@{1,3,5,10}, MRR, nDCG@10; report abstention precision/recall per abstain code.
- **T4.5 Gate that can fail**: PASS requires vitals-only Recall@k >= stated threshold; validity self-test: random baseline Recall@5 < 0.6 and position-prior R@1 < system R@1 by a CI-excluding margin.
- **T4.6 Hand-computed fixtures** for each metric function; document in `docs/evaluation/METRICS.md`.
- **T4.7 Arms re-run** on the rebuilt benchmark (char_ngram, BM25, RRF, +lexical rerank, ±contextual headers, ±predicate scoring); re-run `decide_backend()`.

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
