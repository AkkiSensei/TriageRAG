# ADR 0012: Corpus Growth, Content-Addressed Node Identifiers, Contextual Chunking, and Regulatory Evidence Ingestion

## Context
Prior to AUB Phase 3, TriageRAG's knowledge base and corpus infrastructure had critical structural bottlenecks:
1. **AUB-COR-01**: Corpus was too small (6 protocol documents, 27 total chunks) for retrieval to realistically fail or reflect authentic emergency triage variety. Candidate pool size per partition was smaller than $k=5$ for most queries, leaving BM25 IDF nearly uniform and uninformative.
2. **AUB-COR-02**: Decision nodes were identified by positional sequence indexes (`{chunk_id}_NODE_{i}`). Any reordering, insertion, or revision of protocol nodes silently re-targeted downstream citations, benchmark labels, and verification spans.
3. **AUB-COR-03**: Cross-node clinical context was lost in isolated child chunks. Subsequent nodes (e.g. Node 3 or Node 5) depending on an initial entry condition or governing clinical presentation lacked governing context in isolated BM25 token statistics.
4. **HD-9 / Licensing Hygiene**: Document metadata lacked explicit license classification tags (`synthetic`, `public_domain`, `cc_by_nc_sa`, `restricted`). Non-synthetic raw files and local indexes risked improper repository check-in.
5. **AUB T3.6 / Evidence Corpus**: The system lacked Tier-2 regulatory drug label evidence for rule grounding and citation verification. Indian-context products (e.g. Deriphyllin, etofylline) lacked explicit fail-closed handling.

## Decision

1. **Synthetic Corpus Expansion Across 36 Syndromes (T3.1 / AUB-COR-01)**:
   - Expanded protocol coverage from 6 to 65 total clinical documents (6 manual baseline documents, 57 adult protocols, 6 paediatric protocols, 2 neonatal protocols).
   - Generated 617 total structured chunks across 36 controlled syndromes with 8–10 decision nodes per syndrome.
   - Injected vocabulary-sharing cross-syndrome distractors and alternative protocol versions (`version: 2.0.0`) to make candidate pools larger than $k=5$ across all partitions.
   - Ingestion report guarantees 0 quarantined documents and 100% round-trip line invariant verification.

2. **Deterministic Generator Tooling (T3.2)**:
   - Created `tools/generate_synthetic_protocols.py` featuring bit-for-bit seeded determinism (`seed: 42`), template variation, and non-overwriting manual protocol protection.
   - Recorded generator seed in `data/corpus/manifest.yaml`.
   - Strictly enforced Rule R9 (zero numeric dosages in any synthetic protocol markdown).

3. **Content-Addressed Node Identifiers and Dual-Key Aliases (T3.3 / AUB-COR-02)**:
   - Implemented `canonicalize_node_text` (NFKC unicode normalization, list number prefix stripping, LF newline normalization, line trim) and `compute_node_hash`: `{chunk_id}_{hash8(canonical_text)}`.
   - Node identifiers are 100% invariant to line reordering, node insertion, and list renumbering.
   - Built dual-key backward compatibility: `ProtocolChunk` and `RetrievedChunk` store canonical `chunk_id` and `legacy_id` (`{chunk_id}_NODE_{i}`).
   - Created `data/corpus/node_aliases.yaml` (552 child node aliases) and `src/triagerag/rag/aliases.py` with transparent resolution across citation verification, evaluation benchmarks, and API responses. Zero collisions across the corpus.

4. **Document Licensing Tags and Provenance Strictness (T3.4 / HD-9)**:
   - Extended `ProtocolFrontmatter`, `ProtocolChunk`, and `CorpusManifestEntry` with `license_tag: Literal["synthetic", "public_domain", "cc_by_nc_sa", "restricted"]`.
   - Labeled all synthetic protocol documents and manifest entries with `license_tag: synthetic`.
   - Hardened `.gitignore` to strictly exclude non-synthetic raw evidence (`data/evidence_raw/*`), restricted clinical guidelines (`data/protocols_restricted/*`), and local dense indexes (`data/indexes_local/*`).

5. **Experimental Contextual Chunking Research Arm (T3.5 / AUB-COR-03)**:
   - Implemented `extract_if_condition` and updated `build_contextual_header` to optionally prepend governing root conditions (`Governing Context: <condition>`) to dependent child nodes (`idx > 1`) in `indexed_text`.
   - Verbatim `chunk.text` and `content_hash` remain 100% untouched to ensure pristine span citation verification.
   - Added `contextual_chunking: bool = False` configuration flag and integrated `bm25_contextual` as an ablation arm in `eval/run_retrieval_ablation.py`.
   - Evaluated under `decide_backend()`: retains default `bm25` unless contextual chunking achieves $\ge +0.05$ test MRR gain without regressing Recall@5 or safety invariants.

6. **Tier-2 openFDA Regulatory Drug Label Evidence Pipeline (T3.6)**:
   - Implemented `tools/fetch_openfda_labels.py` and `src/triagerag/rag/evidence.py` to ingest, chunk, and index SPL drug labels for ~60 generics across Waves 1–2.
   - Chunks by standard SPL sections: Boxed Warning, Contraindications, Warnings and Precautions, Drug Interactions, Specific Populations, Dosage/Administration, Overdosage, Adverse Reactions.
   - Extracted 688 structured `EvidenceChunk` records into `data/corpus/evidence_chunks.json`.
   - Attached strict Provenance on every chunk (`source_doc=f"OPENFDA_SPL_{label_id}"`, `license_tag="public_domain"`, `content_origin="SOURCE_EXTRACT"`, `source_status=RETRIEVED_UNREVIEWED`).
   - Handled Indian-only products (`deriphyllin`, `etofylline`) with explicit `UnretrievedEvidenceNotice` (`no_evidence_chunk=True`) to prevent fabricated facts (Rules R2, R3).
   - Provided offline test fixtures in `tests/fixtures/openfda/` ensuring 100% offline, idempotent execution.

## Status
Accepted. Implemented in Tasks T3.1–T3.6 (commits `85d0985` through `ac21b62`).
- 65 protocol documents, 617 chunks, 36 controlled syndromes.
- 688 Tier-2 openFDA regulatory evidence chunks across 62 generics.
- 0 hash collisions across all content-addressed child nodes.
- Full 35-test Phase 3 unit suite passing in 2.88s.
- Zero network calls in test execution; 100% offline reproducible.
