# ADR 0011: Patient-Aware Retrieval, Predicate Conditioning, and Reachable Syndrome Inference

## Context
Prior to AUB Phase 2, TriageRAG's protocol retrieval was largely static and unconditioned on patient clinical state:
1. **D2 / Defect D2**: Retrieval had no structured predicate vocabulary; protocol IF/THEN nodes lacked patient applicability metadata (`requires_predicates`, `contraindicated_by`); queries lacked predicate-to-protocol vocabulary bridging; candidate ranking in BM25 was static across patients regardless of physiology or contraindications.
2. **AUB-RET-01**: Candidate chunks were ordered purely by BM25 lexical score, oblivious to physiological fit or contraindications.
3. **AUB-RET-06**: Query and index token hygiene suffered from multi-word stem/synonym expansions inflating `avgdl` in BM25 document statistics, and raw node ID numbers leaking into indexed text.
4. **AUB-RET-02**: `hybrid_rrf_rerank` inflated scores with an uncalibrated 1.5x multiplier (`1 + 0.5 * overlap`), and hybrid RRF scores were artificially rescaled against top BM25 scores.
5. **HD-4 / Defect HD-4**: In unrouted / vitals-only triage presentations (`patient.suspected_syndrome is None`), 0 of 56 test cases progressed past `EMPTY_QUERY` because query construction was gated strictly on `norm_syndrome` presence and vitals flags were unverified (`NEEDS_SOURCE`).

## Decision

1. **Structured Clinical Predicate Vocabulary (T2.1 / D2)**:
   - Defined 17 synthetic clinical predicates in `data/retrieval/predicates.yaml` (e.g. `low_systolic_bp`, `tachycardia`, `beta_blocker_active`, `hypoglycemia`).
   - Implemented typed loader and evaluator in `src/triagerag/rag/predicates.py` with tri-state evaluation (`SATISFIED`, `UNSATISFIED`, `UNKNOWN`).
   - Enforced strict architectural isolation: the core clinical engine (`src/triagerag/engine/`) never imports or consumes retrieval predicates or cues.

2. **Protocol Node Applicability Metadata (T2.2 / D2)**:
   - Catalogued applicability constraints for all 21 synthetic protocol decision nodes in `data/retrieval/node_predicates.yaml`.
   - Attached `requires_predicates`, `contraindicated_by`, and `always_applicable` to `ProtocolChunk` during protocol ingestion.

3. **Synthetic Retrieval Cues & Query Expansion (T2.3 / HD-16)**:
   - Established `data/retrieval/cues.yaml` mapping structured patient predicates to explicit protocol vocabulary without LLMs or external dependencies.
   - Implemented `src/triagerag/rag/cues.py` with deterministic expansion and token deduplication.
   - Categorized predicates into acute presenting findings (`syndrome_cue: true`) versus qualifying baselines (`syndrome_cue: false`) to avoid false cross-syndrome cue pollution.

4. **Patient-Conditioned Linear Scoring Model (T2.4 / AUB-RET-01)**:
   - Implemented `src/triagerag/rag/scoring.py` with the linear model:
     $$\text{Score} = \text{BM25} + \lambda \times \text{satisfied\_matches} - \mu \times \text{active\_conflicts}$$
     with calibrated default weights $\lambda = 1.0, \mu = 2.0$.
   - Unknown/unverified predicates add 0 match and 0 conflict under fail-closed semantics.
   - Enforced deterministic tie-breaking sorted by `(-round(score, 4), chunk_id)`.

5. **Query and Index Token Hygiene (T2.5 / AUB-RET-06)**:
   - Added `tokenize_raw` to `ClinicalTokenizer` in `src/triagerag/rag/index.py`: document length (`dl`) strictly counts discriminative raw words, preventing stem/synonym expansions from inflating document length normalisation.
   - Separated clean `indexed_text` from full citation headers (`display_header`) in `src/triagerag/rag/chunking.py`.
   - Introduced weighted query tokenization (`raw=1.0`, `stem=0.8`, `synonym=0.6`, `cue=0.7`).

6. **Score-Scale Integrity (T2.6 / AUB-RET-02)**:
   - Hardened `LexicalOverlapReranker` in `src/triagerag/rag/hybrid.py`: removed 1.5x multiplier; reranked score is bounded by $\le \text{base\_score}$.
   - Eliminated artificial RRF-to-BM25 rescaling: hybrid retrievers emit authentic RRF scores.
   - Introduced backend-specific confidence normalization contracts in `src/triagerag/rag/abstain.py` mapping raw scores onto calibrated $[0.0, 1.0)$ confidence values.

7. **Reachable Vitals-Only Syndrome Inference Path & HD-4 Clinical Gate (T2.7 / HD-4)**:
   - When `patient.suspected_syndrome is None`, evaluated patient presenting vitals cues (`syndrome_cues_only=True`) to construct a discriminative candidate query.
   - Candidate pool expansion retrieves chunks across protocols; predicate rescoring identifies winning syndrome and enforces minimum relative margin $\ge 0.25$ between top distinct syndromes.
   - If margin $< 0.25$, retrieval cleanly abstains with `AbstainCode.AMBIGUOUS_MARGIN`.
   - If clean winning syndrome, returns `AbstainCode.SYNDROME_INFERRED` with candidate chunks restricted strictly to that inferred syndrome.
   - HD-4 Clinical Confirmation Gate: In `orchestrator.py` / `plan_verifier.py`, any plan verified under `SYNDROME_INFERRED` caps approved steps at `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION`. Inferred syndromes are never auto-approved.

## Status
Accepted. Implemented in Tasks T2.1–T2.7 (commits `af6a410` through `d27dc07`).
- All 295 unit tests passing (294 passed, 1 expected xfail for HD-6).
- Node-Level Test Recall@1 increased from 39.29% to **71.43%**.
- Node-Level Test Recall@5 increased from 73.21% to **98.21%**.
- Vitals-Only Test Recall@1 increased from 0.00% to **73.33%**.
- Wrong-Protocol Rate remains strictly **0.0000** (Gate == 0.0).
- Hard-Negative Abstain Recall remains strictly **1.0000** (Gate == 1.0).
