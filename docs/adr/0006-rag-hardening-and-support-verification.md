# ADR 0006: RAG Hardening, Hard Syndrome Filtering, and Deterministic Citation Support Verification

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Status
Accepted (2026-10-28)

## Context
During the comprehensive RAG subsystem postmortem audit (`RAG-01` through `RAG-16`), several safety-critical failure modes were identified:
1. **Cross-Syndrome Contamination (`RAG-01`):** `suspected_syndrome` was previously concatenated into the BM25 query string without a query-time hard filter. When a patient presented with an unknown syndrome (e.g., `kidney_stone`) or shared physiological flags (`hypotension`, `tachycardia`), BM25 matched unrelated protocol documents (e.g., `anaphylaxis.md` or `chest_pain.md`) instead of abstaining.
2. **Citation Laundering (`RAG-02`):** `verify_citation` checked only whether `quoted_span` was a substring of `chunk.text`. A step proposing `administer nitroglycerin` could cite an unrelated `hypoglycemia` chunk or a `withhold` node and still pass citation verification.
3. **Hardcoded Adult Vitals Thresholds (`RAG-03`):** `derive_vitals_flags` previously applied adult heart-rate and respiratory-rate cutoffs to paediatric and neonate patients in Python code.
4. **Silent Provenance & Ingestion Fallbacks (`RAG-04`, `RAG-05`):** Missing `synthetic` frontmatter defaulted to `True`, and trailing markdown sections bled into the final decision node.

## Decision
1. **Hard Query-Time Population & Syndrome Filters (`AbstainCode`):**
   - `suspected_syndrome` is normalized via `data/retrieval/synonyms.yaml` against the controlled vocabulary in `data/corpus/manifest.yaml`.
   - Missing syndrome returns `AbstainCode.MISSING_SYNDROME`; unrecognized syndrome returns `AbstainCode.UNKNOWN_SYNDROME`; populations without protocol coverage return `AbstainCode.NO_POPULATION_COVERAGE`.
   - When `suspected_syndrome` is valid, the retriever filters candidate chunks strictly to `chunk.syndrome == normalized_syndrome` and `chunk.population == population`.
2. **Data-Driven Vitals Flags with Fail-Closed `NEEDS_SOURCE` (`data/retrieval/vitals_flags.yaml`):**
   - All physiological flag derivations are loaded from `data/retrieval/vitals_flags.yaml` with `Provenance`. Rules marked `status: NEEDS_SOURCE` or `threshold: null` fail closed and never fall back to adult cutoffs.
3. **Deterministic Step-Support & Child-Node Citation Verification (`verify_step_support`):**
   - Parent-only citations are rejected whenever child decision nodes (`_NODE_`) exist for that document in `retrieved_chunks`.
   - Minimum lexical overlap (`>= 0.08`, configured in `data/retrieval/action_cues.yaml`) is enforced between `narrative_instruction` and `quoted_span`.
   - For `administer` and `withhold` steps, `verify_step_support` verifies that at least one cited chunk contains both (a) the step's `drug_id` (or a verified alias from `registry.aliases`) and (b) a matching action cue from `administer_cues` or `withhold_cues`.
4. **Unified `RetrievalService` & Cryptographic Audit Provenance:**
   - All surfaces (API, CLI, Streamlit UI, Orchestrator, Evaluation) construct and access the retriever through `RetrievalService.create_default()`.
   - Every `AuditRecord` logs a distinct `formulary_version` hash plus `retrieval_query`, `retrieval_filters`, `retrieval_stage_scores`, `corpus_hash`, `index_version`, `config_hash`, and `abstain_code`.

## Consequences
- **Zero Wrong-Protocol Rate:** Unknown or out-of-scope syndromes deterministically abstain (`UNKNOWN_SYNDROME`), achieving `0.00%` Wrong-Protocol Rate on the 160-case evaluation benchmark.
- **Elimination of Citation Laundering:** Mutants `M29`–`M33` verify that dropping drug support, withhold-cue polarity, overlap gates, child-node specificity, or unknown-syndrome abstention is immediately caught by the test and mutation suites (`45/45` killed).

