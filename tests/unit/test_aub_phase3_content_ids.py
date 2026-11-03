"""Unit tests for Content-Addressed Node Identifiers and Alias Map (T3.3 / AUB-COR-02).

Safety Properties (Rules R1, R2, R3, AUB-COR-02):
1. Node chunk IDs are content-addressed: {chunk_id}_{hash8(canonical_node_text)}.
2. Reordering nodes preserves chunk IDs (invariance to permutation).
3. Inserting new nodes does not alter existing chunk IDs.
4. Legacy positional IDs ({chunk_id}_NODE_{n}) resolve transparently via node_aliases.yaml.
5. Zero hash collisions across the entire synthetic corpus.
6. Citation verification succeeds whether citing canonical content-addressed ID or legacy alias.
"""

from __future__ import annotations

from triagerag.config import get_data_dir
from triagerag.contracts.schemas import SpanCitation
from triagerag.rag.aliases import (
    clear_node_alias_cache,
    load_node_aliases,
    load_reverse_node_aliases,
    resolve_chunk_id,
)
from triagerag.rag.chunking import (
    canonicalize_node_text,
    chunk_protocol_markdown,
    compute_node_hash,
)
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.service import RetrievalService
from triagerag.verify.citations import verify_citation


def test_canonical_text_normalization() -> None:
    """Canonicalization strips leading numbering and normalizes line breaks and whitespace."""
    t1 = "1. IF patient presents with chest pain:\n   THEN acquire immediate ECG."
    t2 = "5. IF patient presents with chest pain:\r\n   THEN acquire immediate ECG.   "
    assert canonicalize_node_text(t1) == canonicalize_node_text(t2)
    assert compute_node_hash(t1) == compute_node_hash(t2)
    assert len(compute_node_hash(t1)) == 8


def test_node_reordering_preserves_content_addressed_ids() -> None:
    """AUB-COR-02 Acceptance: Swapping node order produces identical content-addressed IDs."""
    md_order_a = """---
doc_id: EMERG_TEST_REORDER
title: Test Reorder Protocol
section: Test Section
population: adult
syndrome: test_syndrome
chunk_id: TEST_01
synthetic: true
version: 1.0.0
license: synthetic
attribution: Test Corpus
source_url: null
retrieved_at: null
reviewed_by: null
status: PLACEHOLDER_UNRETRIEVED
---
1. IF first clinical condition occurs:
   THEN execute first intervention protocol.
2. IF second clinical condition occurs:
   THEN execute second intervention protocol.
"""

    md_order_b = """---
doc_id: EMERG_TEST_REORDER
title: Test Reorder Protocol
section: Test Section
population: adult
syndrome: test_syndrome
chunk_id: TEST_01
synthetic: true
version: 1.0.0
license: synthetic
attribution: Test Corpus
source_url: null
retrieved_at: null
reviewed_by: null
status: PLACEHOLDER_UNRETRIEVED
---
1. IF second clinical condition occurs:
   THEN execute second intervention protocol.
2. IF first clinical condition occurs:
   THEN execute first intervention protocol.
"""

    chunks_a = chunk_protocol_markdown(md_order_a)
    chunks_b = chunk_protocol_markdown(md_order_b)

    # In Order A: chunks[1] is first condition, chunks[2] is second condition
    # In Order B: chunks[1] is second condition, chunks[2] is first condition
    assert chunks_a[1].chunk_id == chunks_b[2].chunk_id
    assert chunks_a[2].chunk_id == chunks_b[1].chunk_id

    # Content-addressed IDs are stable across reordering
    assert chunks_a[1].chunk_id.startswith("TEST_01_")
    assert chunks_a[2].chunk_id.startswith("TEST_01_")


def test_node_insertion_leaves_subsequent_node_ids_unchanged() -> None:
    """AUB-COR-02 Acceptance: Inserting a node at position 1 does not change existing node IDs."""
    md_before = """---
doc_id: EMERG_TEST_INSERT
title: Test Insert Protocol
section: Test Section
population: adult
syndrome: test_syndrome
chunk_id: TEST_INS_01
synthetic: true
version: 1.0.0
license: synthetic
attribution: Test Corpus
source_url: null
retrieved_at: null
reviewed_by: null
status: PLACEHOLDER_UNRETRIEVED
---
1. IF existing target node condition:
   THEN administer target medication.
"""

    md_after = """---
doc_id: EMERG_TEST_INSERT
title: Test Insert Protocol
section: Test Section
population: adult
syndrome: test_syndrome
chunk_id: TEST_INS_01
synthetic: true
version: 1.0.0
license: synthetic
attribution: Test Corpus
source_url: null
retrieved_at: null
reviewed_by: null
status: PLACEHOLDER_UNRETRIEVED
---
1. IF newly inserted preliminary condition:
   THEN perform preliminary triage.
2. IF existing target node condition:
   THEN administer target medication.
"""

    chunks_before = chunk_protocol_markdown(md_before)
    chunks_after = chunk_protocol_markdown(md_after)

    target_id_before = chunks_before[1].chunk_id
    target_id_after = chunks_after[2].chunk_id

    assert target_id_before == target_id_after


def test_alias_resolution_maps_legacy_id_to_content_id() -> None:
    """AUB-COR-02 Acceptance: Unknown old positional ID resolves via alias map."""
    data_dir = get_data_dir()
    alias_map = load_node_aliases(data_dir)
    assert len(alias_map) >= 500

    # Test baseline protocols have legacy aliases mapped
    assert "CHEST_PAIN_01_NODE_1" in alias_map
    resolved = resolve_chunk_id("CHEST_PAIN_01_NODE_1", alias_map)
    assert resolved.startswith("CHEST_PAIN_01_")
    assert resolved != "CHEST_PAIN_01_NODE_1"

    # Resolving an already content-addressed ID returns itself
    assert resolve_chunk_id(resolved, alias_map) == resolved

    # Resolving an unknown identifier returns itself safely
    assert resolve_chunk_id("NONEXISTENT_CHUNK_XYZ", alias_map) == "NONEXISTENT_CHUNK_XYZ"


def test_zero_hash_collisions_across_entire_corpus() -> None:
    """All child decision nodes across all 65 protocols have unique chunk IDs."""
    chunks = ingest_protocols(get_data_dir())
    child_chunks = [c for c in chunks if c.parent_id is not None]
    assert len(child_chunks) >= 550

    seen_ids: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []

    for c in child_chunks:
        if c.chunk_id in seen_ids:
            collisions.append((c.chunk_id, seen_ids[c.chunk_id], c.doc_id))
        else:
            seen_ids[c.chunk_id] = c.doc_id

    assert not collisions, f"Hash collisions detected in corpus: {collisions}"


def test_citation_verification_succeeds_with_content_id_or_legacy_alias() -> None:
    """Grounded citation verification accepts both content-addressed ID and legacy positional alias."""
    from eval.run_retrieval import build_patient_from_eval_case

    case = {
        "id": "TEST_CASE_CP",
        "split": "test",
        "age": {"value": "55", "unit": "years"},
        "population": "adult",
        "suspected_syndrome": "chest_pain",
        "vitals": {
            "systolic_bp_mmhg": 120,
            "heart_rate_bpm": 80,
            "spo2_percent": 98,
        },
    }
    patient = build_patient_from_eval_case(case)

    service = RetrievalService.create_default(get_data_dir(), backend="bm25")
    report = service.retrieve(patient, top_k=5)
    assert not report.abstained
    top_chunk = report.chunks[0]

    # Extract non-empty quoted span from THEN clause
    lines = [ln.strip() for ln in top_chunk.text.splitlines() if ln.strip()]
    then_line = next(ln for ln in lines if ln.upper().startswith("THEN "))
    quoted_span = then_line[5:].rstrip(".")  # Strip 'THEN ' and period

    # 1. Citing with canonical content-addressed ID succeeds
    citation_canonical = SpanCitation(
        doc_id=top_chunk.doc_id,
        section=top_chunk.section,
        chunk_id=top_chunk.chunk_id,
        quoted_span=quoted_span,
    )
    ok_canon, _, _ = verify_citation(
        citation_canonical,
        report.chunks,
        quoted_span,
    )
    assert ok_canon is True

    # 2. Citing with legacy positional alias succeeds
    if top_chunk.legacy_id:
        citation_legacy = SpanCitation(
            doc_id=top_chunk.doc_id,
            section=top_chunk.section,
            chunk_id=top_chunk.legacy_id,
            quoted_span=quoted_span,
        )
        ok_legacy, _, _ = verify_citation(
            citation_legacy,
            report.chunks,
            quoted_span,
        )
        assert ok_legacy is True


def test_alias_cache_isolation_across_directories(tmp_path) -> None:
    """Cache isolation test: distinct directories return their own alias maps without cache leakage."""
    dir_a = tmp_path / "data_a"
    corpus_a = dir_a / "corpus"
    corpus_a.mkdir(parents=True)
    (corpus_a / "node_aliases.yaml").write_text(
        "aliases:\n  ALIAS_A: CANON_A\n",
        encoding="utf-8",
    )

    dir_b = tmp_path / "data_b"
    corpus_b = dir_b / "corpus"
    corpus_b.mkdir(parents=True)
    (corpus_b / "node_aliases.yaml").write_text(
        "aliases:\n  ALIAS_B: CANON_B\n",
        encoding="utf-8",
    )

    clear_node_alias_cache()
    aliases_a = load_node_aliases(dir_a)
    aliases_b = load_node_aliases(dir_b)

    assert aliases_a == {"ALIAS_A": "CANON_A"}
    assert aliases_b == {"ALIAS_B": "CANON_B"}
    assert resolve_chunk_id("ALIAS_A", aliases_a) == "CANON_A"
    assert resolve_chunk_id("ALIAS_A", aliases_b) == "ALIAS_A"

    rev_a = load_reverse_node_aliases(dir_a)
    rev_b = load_reverse_node_aliases(dir_b)
    assert rev_a == {"CANON_A": "ALIAS_A"}
    assert rev_b == {"CANON_B": "ALIAS_B"}
