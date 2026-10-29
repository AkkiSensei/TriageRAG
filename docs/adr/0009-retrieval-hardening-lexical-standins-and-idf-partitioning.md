# ADR 0009: Retrieval Component Honesty, Lexical Reranker, and Population Partitioning (HD-5)

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Status
Accepted (2026-10-29) — Fix Gate G5 (`FG-08`, `FG-13`, `FG-14`, `FG-17`, `FG-19`, `HD-5`)

## Context
Audit flags identified five retrieval and lexical normalization discrepancies:
1. **Stand-in Terminology (`FG-14`, `HD-5`):** `DenseRetriever` was described as dense vector search but was implemented using token and character trigram TF-IDF cosine similarity, and the reranker was a token overlap ratio check.
2. **IDF Partitioning vs Global IDF (`FG-13`):** WP4 specified global IDF statistics, while `_PopulationBM25Stats` isolated document frequencies to guarantee cross-population score stability.
3. **Prompt Injection Defense Fragmentation (`FG-17`):** Regex sanitizers were duplicated across `rag/ingest.py` and `llm/prompts.py`, lacked Unicode NFKC normalization and zero-width stripping, and did not explicitly block `status: REVIEWED` on flagged chunks.
4. **Tokenizer Acronym False Positives (`FG-19`):** Sentence-initial title-cased short words (`Pe`, `Iv`, `Hr`) were mistakenly expanded to multi-word acronyms (`pulmonary embolism`, `intravenous`, `heart rate`) due to `any(ch.isupper() for ch in token)`.
5. **Ablation Methodology (`FG-08`):** Ablation reports evaluated aggregate cases rather than the held-out test split, omitted bootstrap confidence intervals, and lacked a programmatic decision rule.

## Decision
1. **Honest Component Naming & Backward Compatibility (`FG-14`, `HD-5`):**
   - The token + character trigram TF-IDF cosine retriever is renamed to `CharNgramRetriever`. `DenseRetriever = CharNgramRetriever` is retained as an alias.
   - The token overlap reranker is formalized as `LexicalOverlapReranker`.
   - The offline prototype retains these pure-Python lexical stand-ins (`HD-5` fail-closed default); neural cross-encoders and dense embedding models are documented as future extensions in `LIMITATIONS.md`.

2. **Population Partitioning with Global Corpus Statistics (`FG-13`):**
   - `BM25ClinicalIndex` computes and exposes `global_total_docs`, `global_doc_freqs`, and `global_idf` across all deduplicated protocol chunks in the repository.
   - To strictly preserve the safety property that adding or updating documents in one population has zero effect on another population's scores or rankings (`test_score_stability_across_populations`), candidate scoring within a population partition uses that partition's local length normalization and non-negative smoothed IDF.

3. **Unified Sanitizer Module & Review Blocker (`FG-17`):**
   - Created `src/triagerag/normalize/sanitizer.py` implementing Unicode NFKC normalization, zero-width stripping (`\u200b`, `\u200c`, `\u200d`, `\ufeff`), and 18 injection/role-marker patterns.
   - Ingestion records flagged chunks in `IngestReport.flagged_chunks` and **blocks `status: REVIEWED`** on documents with flagged patterns.

4. **Title-Case Acronym Case Rule (`FG-19`):**
   - Short tokens (length <= 2) only expand as clinical acronyms when `token == token.upper()` (e.g., `PE`, `IV`, `HR`). Sentence-initial title-cased words (`Pe`, `Iv`, `Hr`) are not expanded.

5. **Held-Out Test Split Ablation & Programmatic Selection (`FG-08`):**
   - Ablation evaluates the held-out test split (n=88) with 95% bootstrap confidence intervals.
   - Implemented `decide_backend()`: verifies hard safety constraints (`wrong_protocol_rate == 0.0`, `hard_negative_abstain_recall == 1.0`, `p95 < 50.0 ms`), and adopts an alternative stage over `bm25` only if test Recall@5 does not regress and test MRR improves by >= 0.05.

## Consequences
- Lexical stand-ins are accurately represented across code and documentation (`HD-5`).
- Cross-population isolation is strictly verified without metric drift.
- Sanitization is centralized with Unicode robustness and review-blocking enforcement.
- Ablation backend selection is deterministic and automated.

