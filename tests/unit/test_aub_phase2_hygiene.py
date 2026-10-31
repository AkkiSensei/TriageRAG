"""Unit tests and ablation verification for Query and Index Token Hygiene (AUB-RET-06 / T2.5).

Safety Properties (AUB Phase 2 / T2.5):
1. Query tokens are strictly deduplicated; each distinct token is evaluated once in BM25 scoring.
2. Token classes (raw, stem, synonym, cue) are explicitly weighted without uncontrolled inflation.
3. Document length in BM25 statistics reflects discriminative raw words only, stopping stem/synonym
   double-counting from artificially inflating dl and distorting avgdl.
4. Non-discriminative header fragments ('node', positional digits, redundant syndrome tokens)
   are stripped from indexed_text while preserving full display headers.
5. Zero degradation across golden syndrome retrieval fixtures.
"""

from __future__ import annotations

from triagerag.config import get_data_dir
from triagerag.rag.chunking import ProtocolChunk, chunk_protocol_markdown
from triagerag.rag.index import BM25ClinicalIndex, ClinicalTokenizer
from triagerag.rag.ingest import ingest_protocols


def test_query_token_deduplication() -> None:
    """T2.5: Query tokens are deduplicated; repeated terms evaluate once with explicit weight."""
    tokenizer = ClinicalTokenizer()
    repeated_query = "wheezing wheezing tachypnea tachypnea tachycardia"

    # Tokenizer raw list would contain duplicates
    tokens_list = tokenizer.tokenize(repeated_query)
    assert tokens_list.count("wheezing") > 1

    # Weighted query tokenizer strictly deduplicates
    weights = tokenizer.tokenize_query_weighted(
        repeated_query,
        weights={"raw": 1.0, "stem": 0.8, "synonym": 0.6},
    )

    # Every distinct token appears exactly once as a dictionary key
    assert "wheezing" in weights
    assert "tachypnea" in weights
    assert "tachycardia" in weights
    assert weights["wheezing"] == 1.0
    assert weights["tachypnea"] == 1.0
    assert weights["tachycardia"] == 1.0
    # No duplicate keys can exist in a dict
    assert len(weights) < len(tokens_list)


def test_token_class_weights_raw_vs_stem_vs_synonym() -> None:
    """T2.5: Explicit class weights distinguish raw (1.0), stem (0.8), and synonym (0.6)."""
    tokenizer = ClinicalTokenizer()
    query = "wheezing"  # stems to 'wheez', has synonyms e.g. bronchospasm

    weights = tokenizer.tokenize_query_weighted(
        query,
        weights={"raw": 1.0, "stem": 0.8, "synonym": 0.6},
    )

    assert "wheezing" in weights
    assert weights["wheezing"] == 1.0  # raw weight
    assert "wheez" in weights
    assert weights["wheez"] == 0.8  # stem weight
    # If synonym is present, it receives the synonym weight
    for term, w in weights.items():
        if term not in ("wheezing", "wheez"):
            assert w == 0.6


def test_document_length_ablation_stops_stem_and_synonym_double_counting() -> None:
    """T2.5 Ablation: Document length counts raw words only, preventing length inflation."""
    tokenizer = ClinicalTokenizer()
    sample_text = (
        "IF respiratory wheezing or lower airway bronchospasm persists:\n"
        "THEN administer inhaled salbutamol via nebulization with high-flow oxygen."
    )

    chunk = ProtocolChunk(
        doc_id="TEST_DOC",
        title="Test Guideline",
        section="Assessment",
        chunk_id="TEST_01_NODE_1",
        parent_id="TEST_01",
        text=sample_text,
        population="adult",
        syndrome="severe_asthma",
        synthetic=True,
    )
    raw_tokens = tokenizer.tokenize_raw(chunk.indexed_text)
    expanded_tokens = tokenizer.tokenize(chunk.indexed_text)

    # Ablation demonstration:
    # Expanded tokens include raw + stems (wheez, persist, nebul) + synonyms
    assert len(expanded_tokens) > len(raw_tokens)

    # In BM25 stats, doc_length must equal len(raw_tokens), NOT len(expanded_tokens)
    index = BM25ClinicalIndex([chunk])
    stats = index._stats_by_population["adult"]

    assert stats.doc_lengths[0] == len(raw_tokens)
    assert stats.doc_lengths[0] < len(expanded_tokens)
    assert stats.avgdl == float(len(raw_tokens))


def test_non_discriminative_header_fragments_stripped_from_indexed_text() -> None:
    """T2.5: Non-discriminative header fragments ('node', digits) stripped from indexed_text."""
    md = """---
doc_id: "EMERG_CHEST_PAIN"
title: "Adult Chest Pain Protocol"
section: "Primary Assessment"
population: "adult"
syndrome: "chest_pain"
chunk_id: "CHEST_PAIN_01"
synthetic: true
---
1. IF ischemic discomfort or angina is reported:
   THEN acquire urgent 12-lead electrocardiogram.
"""
    chunks = chunk_protocol_markdown(md)
    child = chunks[1]
    assert child.chunk_id == "CHEST_PAIN_01_NODE_1"

    # Indexed text retains the discriminative title and section
    assert "Adult Chest Pain Protocol › Primary Assessment" in child.indexed_text
    # But non-discriminative ID/positional fragments are absent from indexed_text
    assert "CHEST_PAIN_01_NODE_1" not in child.indexed_text
    assert "NODE_1" not in child.indexed_text

    # Full header is preserved in display_header for UI and citations
    assert (
        child.display_header
        == "Adult Chest Pain Protocol › Primary Assessment › chest_pain › CHEST_PAIN_01_NODE_1"
    )

    # Tokenizer also filters out standalone 'node' and pure digits
    tokenizer = ClinicalTokenizer()
    tokens = tokenizer.tokenize(child.indexed_text)
    assert "node" not in tokens
    assert "1" not in tokens


def test_no_degradation_on_golden_retrieval_fixtures() -> None:
    """T2.5 Gate: Token hygiene causes zero degradation across all golden syndrome protocols."""
    data_dir = get_data_dir()
    index = BM25ClinicalIndex(ingest_protocols(data_dir))

    fixtures = [
        ("chest_pain", "chest pain ischemic discomfort angina", "CHEST_PAIN_01_NODE_1"),
        (
            "anaphylaxis",
            "anaphylaxis acute airway compromise facial swelling collapse epinephrine",
            "ANAPHYLAXIS_01_NODE_1",
        ),
        (
            "hypoglycemia",
            "hypoglycemia neuroglycopenic coma diaphoresis glucose dextrose",
            "HYPOGLYCEMIA_01_NODE_1",
        ),
        (
            "severe_asthma",
            "severe asthma bronchospasm wheezing salbutamol nebulizer",
            "SEVERE_ASTHMA_01_NODE_1",
        ),
        (
            "altered_mental_status",
            "altered mental status unresponsiveness coma airway",
            "ALTERED_MENTAL_STATUS_01_NODE_1",
        ),
        (
            "paediatric_sepsis",
            "paediatric sepsis fever tachycardia capillary refill",
            "PAED_SEPSIS_01_NODE_1",
        ),
    ]

    for syndrome, query, expected_node in fixtures:
        pop = "paediatric" if syndrome == "paediatric_sepsis" else "adult"
        results = index.search(query=query, population=pop, top_k=3, syndrome=syndrome)
        assert len(results) > 0, f"No results for {syndrome}"
        top_chunk, top_score = results[0]
        assert (
            top_chunk.chunk_id == expected_node
        ), f"Expected {expected_node} for {syndrome}, got {top_chunk.chunk_id}"
        assert top_score > 0.0, f"Score for {expected_node} was not positive: {top_score}"
