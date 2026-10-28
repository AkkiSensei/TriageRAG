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
   - Implemented by `BM25ClinicalIndex` (`bm25`, default), `DenseRetriever` (`dense`), and `HybridRRFRetriever` (`hybrid_rrf` and `hybrid_rrf_rerank`).
   - Managed through a single thread-safe factory `RetrievalService.create_default(data_dir, backend=...)` shared across FastAPI, CLI, Streamlit, Orchestrator, and Evaluation suites.
2. **Query-Time Hard Safety Gates:**
   - **Hard Population Filter:** `adult`, `paediatric`, and `neonate` slices are strictly isolated; `neonate` abstains (`NO_POPULATION_COVERAGE`) when no neonate protocol exists.
   - **Hard Syndrome Filter:** `suspected_syndrome` is normalized against the controlled vocabulary in `data/corpus/manifest.yaml` and `data/retrieval/synonyms.yaml`. Unknown syndromes abstain immediately (`UNKNOWN_SYNDROME`) regardless of abnormal vitals flags.
3. **4-Arm Retrieval Ablation (`eval/run_retrieval_ablation.py`):**
   - Evaluates `bm25`, `dense`, `hybrid_rrf`, and `hybrid_rrf_rerank` across 160 node-level graded cases (`eval/reports/retrieval_ablation.md`). Because queries are synthesized deterministically from canonical syndrome tokens and YAML-driven physiological flags (`data/retrieval/vitals_flags.yaml`), `BM25ClinicalIndex` achieves 100% Recall@5 and 0.00% Wrong-Protocol Rate with minimal latency, and is retained as the default offline backend.
4. **Deterministic Citation Support Verification (`verify_step_support`):**
   - Every `administer` or `withhold` step must cite a child decision node (`_NODE_`) whose text contains both (a) the step's `drug_id` (or a verified alias) and (b) a matching action cue (`administer_cues` vs `withhold_cues` from `data/retrieval/action_cues.yaml`), with lexical overlap `>= 0.08`.

## Layer Isolation

Enforced by `import-linter`:
1. `contracts` and `engine` have zero dependencies on `rag`, `llm`, `verify`, `audit`, or UI frameworks.
2. Generative components cannot mutate or override deterministic engine evaluations.
