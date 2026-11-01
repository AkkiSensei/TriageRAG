# ADR 0016: Phase 7 Research Extensions, Showcase, and Forensic Closure

## Status
Accepted

## Context
In AUB Phase 7, TriageRAG reached its final planned engineering milestone: **Research Extensions and Showcase** (T7.1–T7.7).
The system required:
1. Controlled, evidence-grounded query expansion that prevents query drift or prompt leakage.
2. Local neural embedding and cross-encoder retriever/re-ranker abstractions while strictly preserving Human Decision Gate **HD-10** (no external neural model weights downloaded or executed without documented approval).
3. A clinical user experience in the React/Vite web application that surfaces generator provenance (`MOCK` vs `REAL`), query expansion traces, chunk licenses, an inline "Why did this alert fire?" explanation drawer, and an extractive "Ask the Corpus" clinical question-answering console.
4. Defense-in-depth API gateway security: constant-time API key and Bearer token authentication, sliding-window in-memory rate limiting with `429 Too Many Requests` and `Retry-After` headers, and vulnerability audit tasks.
5. Inferred-mode MMR (Maximum Marginal Relevance) diversity re-ranking over candidate protocol chunks, nearest-miss diagnostics, and strict preservation of Human Decision Gate **HD-12** (explicit refusal of isotonic/conformal calibration without verified clinician labels).
6. Local real provider architecture and bit-for-bit deterministic cassette record/replay tape infrastructure, strictly preserving Human Decision Gate **HD-14** (`BLOCKED_EXTERNAL` for unapproved live neural models).
7. Forensic reconciliation and hardening across all preceding phases (Phases 0–6).

## Decision

1. **Phase 0–6 Forensic Reconciliation & Hardening:**
   - Independently investigated and reconciled the 7 audit items identified in Phase 6.
   - Clarified candidate rule counts: 40 candidates in Batches 1–3 + 9 candidates in `auto_mined.yaml` = 49 total candidate rules in `data/rules_candidates/`.
   - Verified that the 86 golden test scenarios govern the 12 active shipped rules; candidate rules remain in unreviewed draft status pending clinician sign-off (HD-7).
   - Documented the 3.0 mL IM volume threshold as an illustrative boundary with status `NEEDS_SOURCE`.
   - Added dedicated isolation tests for `CoAdministrationRule` and synchronized documentation metrics.

2. **Controlled Query Expansion (T7.1):**
   - Implemented `data/retrieval/expansion_terms.yaml` with synthetic protocol synonym dictionaries and explicit provenance.
   - Built `src/triagerag/rag/query_expansion.py` providing `build_expanded_query`.
   - Enforced fail-closed behavior: unknown or indeterminate predicates are never expanded.
   - Emitted inspectable `expansion_trace` and `expansion_mode` in `RetrievalReport`.

3. **Local Neural Interfaces & HD-10 Boundary (T7.2):**
   - Created `src/triagerag/rag/neural_interface.py` defining `EmbeddingModel`, `CrossEncoderModel`, `NeuralDenseRetriever`, and `NeuralCrossEncoderReranker`.
   - Enforced HD-10 gate: unapproved models raise `NeuralModelApprovalError` and remain marked `BLOCKED_EXTERNAL`.
   - Provided deterministic offline mock fixtures for contract testing.

4. **Visible RAG Evidence Experience, Why Drawer & Ask-the-Corpus (T7.3, T7.4):**
   - Created `src/triagerag/rag/ask_corpus.py` implementing extractive verbatim question answering over approved protocol chunks with `generator_badge="EXTRACTIVE_VERBATIM"`.
   - Created `src/triagerag/rag/alert_why.py` explaining triggered rules, matched patient facts, unmeasured vitals, and Rule R11 non-overridable BLOCK severity rationale.
   - Mounted API routes `POST /api/corpus/ask` and `POST /api/triage/alert-why`.
   - Updated React frontend (`AlertsList.tsx`, `RetrievalView.tsx`, `AskCorpusSection.tsx`, `ResultsPane.tsx`) with:
     - Prominent generator badge (`DETERMINISTIC MOCK` vs `REAL PROVIDER`).
     - Query expansion term badges and trace drawer.
     - Protocol chunk license disclosures (`Open Government Licence v3.0 / Synthetic`).
     - Inline interactive "Why did this alert fire?" drawer.
     - "Ask the Corpus" query input with instant extractive answer card and clickable chunk citations.

5. **Security and Operations (T7.5):**
   - Built `src/triagerag/api/security.py` with `SlidingWindowRateLimiter` and constant-time token comparison.
   - Configured authentication boundary via `TRIAGERAG_REQUIRE_AUTH` and `TRIAGERAG_API_KEY`.
   - Protected endpoints return `401 Unauthorized` with `WWW-Authenticate: Bearer` when credentials are missing or invalid; public health and docs endpoints remain exempt.
   - Per-client sliding-window rate limiter returns `429 Too Many Requests` with `Retry-After` header.
   - Added `@app.command("security-audit")` in `tools/tasks.py` supporting `pip-audit` and `npm audit`.

6. **Inferred-Mode MMR, Nearest-Miss Diagnostics & HD-12 Refusal (T7.6):**
   - Implemented `src/triagerag/rag/diagnostics.py` with `apply_mmr_rerank`, `calculate_nearest_misses`, and `explain_chunk_predicates`.
   - Activated MMR when syndrome is inferred from vitals, balancing relevance and lexical token Jaccard diversity ($\lambda = 0.7$).
   - Populated `diagnostics` in `RetrievalReport` with nearest misses, deltas to threshold, and rejection reasons.
   - Preserved HD-12: Added `CalibrationDataRefusalError` in `eval/retrieval/calibrate.py` strictly refusing isotonic/conformal probability calibration when verified clinician annotations are missing.

7. **Local Provider Architecture & Cassette Replay (T7.7):**
   - Built `src/triagerag/llm/cassette.py` with `CassetteEntry`, `CassetteTape`, and `CassetteReplayProvider`.
   - Replay matches on cryptographic SHA-256 hashes of canonical context and prompt strings.
   - Preserved HD-14: Created `ApprovedLocalProvider` raising `LLMProviderApprovalError` for unapproved live models.

## Consequences
- The research prototype is fully feature-complete across all 7 planned AUB phases.
- Zero network calls and 100% offline reproducibility are strictly preserved.
- All 16 Human Decision Gates remain intact with documented audit trails.
- The React web frontend provides full transparency into the RAG retrieval pipeline, rule firings, and evidence provenance.
