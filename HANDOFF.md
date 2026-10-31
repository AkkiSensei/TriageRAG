# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** AUB Phase 4 (Evaluation Rebuild and Research Validity) completed on branch `aub/phase-4-evaluation-rebuild`. Tasks T4.1 through T4.7 implemented, verified, and documented with ADR-0013 and updated status ledger. Rebuilt benchmark features template-grouped splits (55 groups, 0 leakage), blinded clinical annotation tooling with honest agreement provenance, candidate random and position-prior baselines directly answering Reviewer B's challenge question (+30 pt BM25 R@1 advantage over label frequency), honest metric decomposition (FAR vs WSR, real-confidence ECE, cluster-robust group bootstrap CIs), automated benchmark validity self-tests with strict performance gates, hand-computed verification fixtures, and a 7-arm factorial ablation study with paired difference bootstrap CIs confirming `bm25` (with calibrated predicates) as the default production backend.
- **Verification:** All gates green:
  - **100% pass rate** on all 37 Phase 4 unit tests across 7 dedicated test modules.
  - **0 lint / format errors** (Python ruff check & format).
  - **0 type errors** (Python mypy strict in `src/` & TypeScript `tsc --noEmit`).
  - **0 import isolation contract violations** (import-linter: 2 contracts kept, 0 broken).
  - **Zero tracked report mutations**: Running tests and benchmark evaluations leaves git working tree clean by default (`--write` required for report regeneration).
  - **0 quarantined documents** during protocol ingestion; 100% round-trip invariant verified.
  - **0 numeric clinical doses** in any synthetic protocol markdown (Rule R9 verified).
  - **100% offline execution**: zero network calls during automated testing and benchmark runs.

## AUB Phase 4 Deliverables Summary

1. **T4.1 / AUB-EVL-01 — Template-Grouped Dataset Splits (`aad9f4a`):**
   - Implemented `derive_template_id()` and `stratified_template_group_split()` in `eval/retrieval/build_dataset.py`.
   - Partitioned 224 cases by clinical scenario template across 55 groups (42 dev groups with 143 cases; 13 test groups with 81 cases).
   - Generated `eval/retrieval/dataset.lock` and `eval/retrieval/split_manifest.json` recording SHA-256 hashes of dataset and corpus, seed 42, group counts, zero template group leakage, and zero target node-set leakage between dev and test. Added `tests/unit/test_aub_phase4_splits.py` (4 tests).

2. **T4.2 / AUB-EVL-01 — Blinded Annotation Protocol & Agreement Tooling (`e2a750f`):**
   - Authored `docs/evaluation/ANNOTATION_GUIDE.md` establishing 3-level relevance grading rubric (Grade 2 = Directly Actionable, Grade 1 = Supporting Context, Grade 0 = Irrelevant / Contraindicated).
   - Created JSON schema `eval/annotations/schema.json` and export/agreement CLI `tools/export_annotations.py`.
   - Exported 100 blinded candidate cases (`eval/annotations/blinded_cases.json`).
   - Authored `eval/annotations/agreement_status.json` recording honest status: `BLOCKED_PENDING_INDEPENDENT_HUMAN_ANNOTATION` (no fabricated agreement claims). Added `tests/unit/test_aub_phase4_annotations.py` (6 tests).

3. **T4.3 / AUB-EVL-01 — Random & Position-Prior Baselines (`640ff87`):**
   - Implemented `PositionPriorRetriever` in `eval/run_retrieval.py` fitted strictly on dev split with deterministic tie-breaking.
   - Evaluated paired difference bootstrap 95% confidence intervals against position prior.
   - Answered Reviewer B's challenge question: Production BM25 test Recall@1 (54.00%) significantly outperforms the label frequency prior (24.00%) with a +30.00 pt advantage (95% bootstrap CI `[12.0, 48.0]`). Added `tests/unit/test_aub_phase4_baselines.py` (5 tests).

4. **T4.4 / AUB-EVL-01 / AUB-ABS-02 — Honest Metrics, FAR/WSR Split, Real-Confidence ECE (`a8c92d6`):**
   - Disentangled `wrong_protocol_rate` into `false_accept_rate` (FAR = unindicated / expected abstains) and `wrong_syndrome_rate` (WSR = discordant syndrome / positives).
   - Replaced static confidence with genuine normalized retrieval scores in `_compute_ece()`.
   - Added `per_code_abstention` metrics reporting precision, recall, and support per `AbstainCode`.
   - Extended reporting to Recall@{1, 3, 5, 10}, MRR, and graded nDCG@{5, 10}.
   - Implemented cluster-robust group (template-level) bootstrap 95% confidence intervals. Added `tests/unit/test_aub_phase4_metrics.py` (4 tests).

5. **T4.5 / AUB-EVL-01 — Benchmark Validity Self-Tests & Performance Gates (`24b47ac`):**
   - Implemented `validate_benchmark_gate()` enforcing two automated validity self-tests: random candidate baseline Recall@5 must be $< 60.0\%$ and position-prior Recall@1 must be lower than system Recall@1 with paired CI strictly excluding zero.
   - Automatically fails and labels benchmark collection `BENCHMARK_INVALID` on self-test violation.
   - Hard performance gates enforce: `false_accept_rate == 0.0`, `wrong_syndrome_rate == 0.0`, `wrong_protocol_rate == 0.0`, `abstain_recall_hard_negatives == 1.0`, syndrome-provided Recall@5 $\ge 95.0\%$, and bit-for-bit determinism. Added `tests/unit/test_aub_phase4_gates.py` (5 tests).

6. **T4.6 / AUB-EVL-01 — Hand-Computed Metric Verification Fixtures & Reference Docs (`55bf562`):**
   - Authored `docs/evaluation/METRICS.md` documenting exact mathematical formulas, denominators, boundary conditions, and safety rationale for all metrics.
   - Authored `tests/unit/test_aub_phase4_metric_fixtures.py` verifying Recall@{1,3,5,10}, MRR, nDCG@{5,10}, FAR, WSR, legacy WPR, per-code abstention, Cohen's $\kappa$, and ECE against pencil-and-paper hand calculations (7 tests).

7. **T4.7 / AUB-EVL-01 — Controlled 7-Arm Retrieval Ablation & Programmatic Decision (`35d03da`):**
   - Implemented all seven controlled retrieval configurations in `eval/run_retrieval_ablation.py`: `bm25` (Production BM25), `bm25_pure_lexical`, `char_ngram`, `hybrid_rrf`, `hybrid_rrf_rerank`, `bm25_contextual`, and `contextual_predicate`.
   - Computed paired difference 95% bootstrap CIs vs baseline BM25 across 1,000 resamples.
   - Codified `decide_backend()`: strictly enforces hard safety invariants (FAR==0, WSR==0, HN==1, latency < 50ms) and adopts alternative candidates only with non-regressing Recall@5, test MRR gain $\ge +0.05$, and paired difference 95% bootstrap CI strictly excluding zero.
   - Retained `bm25` (with calibrated predicates) as default production backend. Added `tests/unit/test_aub_phase4_ablation.py` (6 tests).

8. **ADR-0013 & Documentation Ledger:**
   - Authored `docs/adr/0013-evaluation-rebuild-and-validity-gates.md` and updated `docs/AUB_STATUS.md` and `CHANGELOG.md`.

## Next Session Focus: AUB Phase 5 — Citation Condition Verification and Plan Grounding

The next engineer will execute **AUB Phase 5: Citation Condition Verification and Plan Grounding (AUB-GRD-01)**:
- **T5.1 IF-Condition Verification**: Verify that cited protocol nodes' preconditions match patient clinical state, not merely that text contains matching keywords.
- **T5.2 Qualifier-Aware Grounding**: Detect qualifiers (repeat-dose, refractory, contraindications) and enforce applicability during citation checking.
- **T5.3 Grounding Diagnostic Reporting**: Machine-readable grounding explanations stating exact matched vs violated preconditions.

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
