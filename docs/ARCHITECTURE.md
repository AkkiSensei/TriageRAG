# TriageRAG — System Architecture

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## High-Level Architecture

TriageRAG separates clinical decision authority from generative text generation:

```
[ Structured Patient Input ]
          │
          ▼
   [ Normalizer ] ─── (Exact / Fuzzy Suggestion Only, never auto-resolve)
          │
          ▼
 ┌────────────────────────────────────────────────────────┐
 │   Pass 1 Deterministic Engine                         │
 │   - Baseline Early Warning Score (Adult / Paediatric)  │
 │   - Home Meds × Home Meds DDI                          │
 │   - Meds × Allergies Cross-Reactivity                  │
 │   - Vitals Interlocks & Population Contraindications   │
 │   - Active Ingredient Duplication Checks               │
 └────────────────────────────────────────────────────────┘
          │
          ├──────────────────────────────────────────┐
          │                                          │
          ▼                                          ▼
 [ Hard Population + Hard Syndrome Filter ] [ LLM Fallback Mode ]
 (Unknown syndrome / population → ABSTAIN)  (If LLM/RAG unavailable)
          │                                          │
          ▼                                          │
 [ Retriever Protocol (RetrievalService) ]           │
   - Default: BM25ClinicalIndex (Smoothed IDF)       │
   - Optional: DenseRetriever / HybridRRFRetriever   │
          │                                          │
          ▼                                          │
 [ LLM Plan Draft ]                                  │
 (PlanContext: vitals flags,                         │
  allowed drugs minus BLOCKED,                       │
  <untrusted_retrieved_protocol_data> delimiters)    │
          │                                          │
          ▼                                          │
 ┌────────────────────────────────────────────────────────┐  │
 │   Pass 2 Verification Pipeline                         │  │
 │   - Proposed Meds × Baseline & Proposed                │  │
 │   - Dose Engine (Decimal math, magnitude tripwires)    │  │
 │   - Drug Scan (Lexicon & token mismatch check)         │  │
 │   - Citation Verifier (Verbatim span, overlap >= 0.08, │  │
 │     child-node specificity, drug + action-cue support) │  │
 └────────────────────────────────────────────────────────┘  │
          │                                                  │
          ▼                                                  │
 [ Repair Loop (Max 2 attempts, violation codes only) ]       │
          │                                                  │
          ▼                                                  │
 [ Final Assembly & Verdict Lattice ] <──────────────────────┘
 (BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR)
          │
          ▼
 [ Cryptographic Audit Chain (Append-only SHA-256 JSONL) ]
          │
          ▼
 [ React Web UI / FastAPI / Streamlit Clinical UI / Typer CLI ]
```

## Retrieval & Grounding Architecture (`src/triagerag/rag/` & `src/triagerag/verify/`)

1. **`@runtime_checkable class Retriever(Protocol)`:**
   - Implemented by `BM25ClinicalIndex` (`bm25`, default), `CharNgramRetriever` (`char_ngram` / `dense`), and `HybridRRFRetriever` (`hybrid_rrf` and `hybrid_rrf_rerank` with `LexicalOverlapReranker`).
   - Managed through a single thread-safe factory `RetrievalService.create_default(data_dir, backend=...)` shared across FastAPI, CLI, Streamlit, Orchestrator, and Evaluation suites.
2. **Query-Time Hard Safety Gates:**
   - **Hard Population Filter:** `adult`, `paediatric`, and `neonate` slices are strictly isolated; `neonate` abstains (`NO_POPULATION_COVERAGE`) when no neonate protocol exists.
   - **Hard Syndrome Filter:** `suspected_syndrome` is normalized against the controlled vocabulary in `data/corpus/manifest.yaml` and `data/retrieval/synonyms.yaml`. Unknown syndromes abstain immediately (`UNKNOWN_SYNDROME`) regardless of abnormal vitals flags.
   - **Vitals-Only Fail-Closed Gate (HD-1):** In the absence of an explicit syndrome, unverified vital flags (`status: NEEDS_SOURCE`) omit tokens, failing closed to `UNVERIFIED` abstention.
3. **4-Arm Retrieval Ablation (`eval/run_retrieval_ablation.py`):**
   - Evaluates `bm25`, `char_ngram`, `hybrid_rrf`, and `hybrid_rrf_rerank` on the held-out test split (88 cases) with 95% bootstrap confidence intervals for Recall@5 and MRR (`eval/reports/retrieval_ablation.md`).
   - A codified deterministic rule `decide_backend()` selects `bm25` as the default production backend because alternative arms do not meet the mandatory `+0.05` MRR improvement threshold over pure lexical BM25 with global corpus statistics.
4. **Deterministic Citation Support Verification (`verify_step_support`):**
   - Structural clause parsing extracts `(action, drug_id)` pairs at chunking time.
   - Negation detection (`do not give`, `never administer`) flips polarity to `withhold`.
   - Administer steps citing a withheld drug in mixed-polarity nodes are strictly rejected.
   - Non-drug steps (`monitor`, `diagnostic`, `maneuver`) require action-verb binding and THEN-clause coverage.
5. **Corpus & Prompt Sanitization (`src/triagerag/normalize/sanitizer.py`):**
   - Centralized sanitizer enforces Unicode NFKC normalization, zero-width stripping, and pattern detection against 18 injection categories across 32 adversarial test attacks. Documents with injection patterns are quarantined and cannot achieve `status: REVIEWED`.

## Layer Isolation

Enforced by `import-linter`:
1. `contracts` and `engine` have zero dependencies on `rag`, `llm`, `verify`, `audit`, or UI frameworks.
2. Generative components cannot mutate or override deterministic engine evaluations.
