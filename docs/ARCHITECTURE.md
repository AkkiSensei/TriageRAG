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
 [ Hard Population Filter ]               [ LLM Fallback Mode ]
          │                               (If LLM/RAG unavailable)
          ▼                                          │
 [ BM25 / RRF Retrieval ]                            │
 (Synthetic Protocols, no doses)                     │
          │                                          │
          ▼                                          │
 [ LLM Plan Draft ]                                  │
 (PlanContext: vitals flags,                         │
  allowed drugs minus BLOCKED)                       │
          │                                          │
          ▼                                          │
 ┌────────────────────────────────────────────────────────┐  │
 │   Pass 2 Verification Pipeline                         │  │
 │   - Proposed Meds × Baseline & Proposed                │  │
 │   - Dose Engine (Decimal math, magnitude tripwires)    │  │
 │   - Drug Scan (Lexicon & token mismatch check)         │  │
 │   - Citation Verifier (Verbatim chunk span check)      │  │
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
 [ Streamlit Clinical UI / Typer CLI ]
```

## Layer Isolation

Enforced by `import-linter`:
1. `contracts` and `engine` have zero dependencies on `rag`, `llm`, `verify`, `audit`, or UI frameworks.
2. Generative components cannot mutate or override deterministic engine evaluations.
