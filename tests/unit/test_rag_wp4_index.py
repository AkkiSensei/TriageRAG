"""Unit and property tests for WP4: Index & scoring refactor, morphology/synonyms, parent dedupe.

Safety Properties (RAG-07, RAG-09, Rule R12):
1. Score stability: adding documents from an unrelated population never changes a population's
   ranking or scores.
2. Non-negative IDF: small-pool child nodes (e.g. paediatric sepsis) score > 0.0 (never 0.0).
3. Parent/child deduplication: search returns child decision nodes without wasting top_k slots
   on duplicate parent blobs, while expand_parents attaches parent context once.
4. Morphology, synonyms, Hinglish, and short-acronym case rules work deterministically.
5. Pure Python float scores (no numpy.float64) and zero '# type: ignore' in src/triagerag/rag/.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from triagerag.config import get_data_dir, get_repo_root
from triagerag.rag.chunking import ProtocolChunk, chunk_protocol_markdown
from triagerag.rag.index import BM25ClinicalIndex, ClinicalTokenizer, Retriever
from triagerag.rag.ingest import ingest_protocols


def test_paediatric_sepsis_child_nodes_have_positive_float_scores() -> None:
    """RAG-07 Probe Fix: Paediatric sepsis child nodes score > 0.0 and return pure Python floats."""
    chunks = ingest_protocols(get_data_dir())
    index = BM25ClinicalIndex(chunks)

    results = index.search(
        query="paediatric_sepsis fever tachycardia",
        population="paediatric",
        top_k=5,
        syndrome="paediatric_sepsis",
    )
    assert len(results) == 3  # 3 child decision nodes, parent deduplicated
    for chunk, score in results:
        assert type(score) is float, f"Expected pure float, got {type(score)}"
        assert chunk.parent_id == "PAED_SEPSIS_01"
        assert score > 0.0, f"Child node {chunk.chunk_id} scored {score} <= 0.0!"

    # Node 1 explicitly mentions fever and severe tachycardia -> must rank #1
    assert results[0][0].chunk_id == "PAED_SEPSIS_01_NODE_1"


def test_parent_child_deduplication_and_parent_expansion() -> None:
    """RAG-07: Search deduplicates parent chunks when child nodes exist and expands parent once."""
    chunks = ingest_protocols(get_data_dir())
    index = BM25ClinicalIndex(chunks)

    results = index.search(
        query="chest_pain hypotension bradycardia",
        population="adult",
        top_k=5,
        syndrome="chest_pain",
    )
    returned_ids = [c.chunk_id for c, _ in results]
    # Whole-document parent CHEST_PAIN_01 must not duplicate its children in top_k
    assert "CHEST_PAIN_01" not in returned_ids
    assert all(c.parent_id == "CHEST_PAIN_01" for c, _ in results)

    # Parent expansion attaches the parent chunk exactly once
    parents = index.expand_parents([c for c, _ in results])
    assert len(parents) == 1
    assert parents[0].chunk_id == "CHEST_PAIN_01"


def test_tokenizer_morphology_synonyms_and_case_rules() -> None:
    """RAG-09: Stemming, clinical synonyms, Hinglish, and 2-letter acronym case sensitivity."""
    acronyms = {"HR": "Heart Rate", "STEMI": "ST-Elevation Myocardial Infarction"}
    tokenizer = ClinicalTokenizer(acronyms=acronyms)

    # 1. Morphology / synonyms: hypotensive -> hypotension, adrenaline -> epinephrine
    t_morph = tokenizer.tokenize("Hypotensive patient given adrenaline for bukhar")
    assert "hypotension" in t_morph
    assert "epinephrine" in t_morph
    assert "fever" in t_morph

    # 2. Case rule for 2-letter acronyms: uppercase 'HR' expands, lowercase 'hr' (hour) does not
    t_upper = tokenizer.tokenize("Elevated HR observed")
    assert "heart" in t_upper
    assert "rate" in t_upper

    t_lower = tokenizer.tokenize("Taken 2 hr ago")
    assert "heart" not in t_lower


@settings(max_examples=50, deadline=None)
@given(
    extra_count=st.integers(min_value=1, max_value=10),
    term=st.sampled_from(["hypotension", "tachycardia", "epinephrine", "fever", "sepsis"]),
)
def test_score_stability_across_populations(extra_count: int, term: str) -> None:
    """WP4 Gate: Adding unrelated population docs never alters a population's ranking or scores."""
    base_chunks = ingest_protocols(get_data_dir())
    base_index = BM25ClinicalIndex(base_chunks)

    extra_neonate_chunks: list[ProtocolChunk] = []
    for i in range(extra_count):
        md = (
            "---\n"
            f'doc_id: "NEO_{i}"\n'
            'section: "Neonatal Care"\n'
            'population: "neonate"\n'
            'syndrome: "paediatric_sepsis"\n'
            f'chunk_id: "NEO_{i}_01"\n'
            "synthetic: true\n"
            "---\n"
            f"1. IF neonate exhibits {term} and distress:\n"
            f"   THEN monitor {term} closely.\n"
        )
        extra_neonate_chunks.extend(chunk_protocol_markdown(md))

    augmented_index = BM25ClinicalIndex(base_chunks + extra_neonate_chunks)

    adult_base = base_index.search("anaphylaxis hypotension", population="adult", top_k=5)
    adult_aug = augmented_index.search("anaphylaxis hypotension", population="adult", top_k=5)
    assert [(c.chunk_id, round(s, 6)) for c, s in adult_base] == [
        (c.chunk_id, round(s, 6)) for c, s in adult_aug
    ]

    paed_base = base_index.search("paediatric_sepsis fever", population="paediatric", top_k=5)
    paed_aug = augmented_index.search("paediatric_sepsis fever", population="paediatric", top_k=5)
    assert [(c.chunk_id, round(s, 6)) for c, s in paed_base] == [
        (c.chunk_id, round(s, 6)) for c, s in paed_aug
    ]


def test_retriever_protocol_and_zero_type_ignores_in_rag() -> None:
    """RAG-07/08: BM25ClinicalIndex satisfies Retriever protocol; zero type-ignores in rag/."""
    chunks = ingest_protocols(get_data_dir())
    index = BM25ClinicalIndex(chunks)
    assert isinstance(index, Retriever)

    rag_dir = get_repo_root() / "src" / "triagerag" / "rag"
    for py_file in sorted(rag_dir.glob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        assert "type: ignore" not in content, f"Found '# type: ignore' in {py_file.name}"
