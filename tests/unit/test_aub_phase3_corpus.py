"""Unit and regression tests for AUB Phase 3 Synthetic Corpus Expansion (T3.1 / AUB-COR-01).

Safety Properties (Rule R3, Rule R9, Section 13):
1. Verifies that the synthetic protocol corpus contains >= 20 distinct controlled syndromes.
2. Verifies that the corpus includes at least 1 neonate and at least 2 paediatric protocols.
3. Verifies that each syndrome contains at least 8-10 decision nodes.
4. Verifies that the total synthetic chunk count is >= 600.
5. Verifies that candidate pools for every syndrome partition exceed top_k (top_k=5).
6. Verifies that zero documents are quarantined during ingestion.
7. Verifies that cross-syndrome distractor vocabulary (hypotension, tachycardia, etc.) is present.
8. Verifies that no synthetic protocol contains numeric doses (Rule R9).
"""

from __future__ import annotations

import re

from triagerag.config import get_data_dir
from triagerag.rag.ingest import ingest_protocols_with_report, load_corpus_manifest


def test_synthetic_corpus_syndrome_count_at_least_twenty() -> None:
    """T3.1 / AUB-COR-01: Corpus must cover at least 20 distinct controlled syndromes."""
    data_dir = get_data_dir()
    manifest = load_corpus_manifest(data_dir)
    assert len(manifest.controlled_syndromes) >= 20, (
        f"Expected >= 20 controlled syndromes, found {len(manifest.controlled_syndromes)}: "
        f"{manifest.controlled_syndromes}"
    )


def test_synthetic_corpus_chunk_count_at_least_six_hundred() -> None:
    """T3.1 / AUB-COR-01: Ingested synthetic corpus must contain >= 600 chunks."""
    data_dir = get_data_dir()
    report = ingest_protocols_with_report(data_dir, strict_unparsed=True)
    assert report.quarantined == [], f"Ingestion quarantined documents: {report.quarantined}"
    assert len(report.chunks) >= 600, (
        f"Expected >= 600 synthetic chunks, found {len(report.chunks)}"
    )


def test_synthetic_corpus_population_coverage() -> None:
    """T3.1 / AUB-COR-01: Corpus must include at least 1 neonate and >= 2 paediatric protocols."""
    data_dir = get_data_dir()
    manifest = load_corpus_manifest(data_dir)
    neonate_docs = [d for d in manifest.documents if d.population == "neonate"]
    paed_docs = [d for d in manifest.documents if d.population == "paediatric"]

    assert len(neonate_docs) >= 1, f"Expected >= 1 neonate protocol, found {len(neonate_docs)}"
    assert len(paed_docs) >= 2, f"Expected >= 2 paediatric protocols, found {len(paed_docs)}"


def test_decision_nodes_per_syndrome_and_candidate_pool_exceeds_top_k() -> None:
    """T3.1 / AUB-COR-01: Expanded syndromes must have >= 8 decision nodes and candidate pool > top_k."""
    data_dir = get_data_dir()
    report = ingest_protocols_with_report(data_dir, strict_unparsed=True)
    manifest = load_corpus_manifest(data_dir)

    top_k = 5
    nodes_by_syndrome: dict[str, int] = {}
    total_chunks_by_syndrome: dict[str, int] = {}

    for chunk in report.chunks:
        total_chunks_by_syndrome[chunk.syndrome] = (
            total_chunks_by_syndrome.get(chunk.syndrome, 0) + 1
        )
        if chunk.parent_id is not None:
            nodes_by_syndrome[chunk.syndrome] = nodes_by_syndrome.get(chunk.syndrome, 0) + 1

    baseline_syndromes = {
        "altered_mental_status",
        "anaphylaxis",
        "chest_pain",
        "hypoglycemia",
        "paediatric_sepsis",
        "severe_asthma",
    }
    expanded_syndromes = [s for s in manifest.controlled_syndromes if s not in baseline_syndromes]
    assert len(expanded_syndromes) >= 20, (
        f"Expected >= 20 expanded syndromes, found {len(expanded_syndromes)}"
    )

    for syndrome in expanded_syndromes:
        node_count = nodes_by_syndrome.get(syndrome, 0)
        assert node_count >= 8, (
            f"Expanded syndrome '{syndrome}' has only {node_count} decision nodes (required >= 8)"
        )
        pool_size = total_chunks_by_syndrome.get(syndrome, 0)
        assert pool_size > top_k, (
            f"Candidate pool for '{syndrome}' is {pool_size} <= top_k ({top_k})"
        )

    # Candidate pool for every population partition must exceed top_k
    chunks_by_pop: dict[str, int] = {}
    for chunk in report.chunks:
        chunks_by_pop[chunk.population] = chunks_by_pop.get(chunk.population, 0) + 1
    for pop, count in chunks_by_pop.items():
        assert count > top_k, (
            f"Population partition '{pop}' has only {count} chunks (required > {top_k})"
        )


def test_zero_quarantined_documents() -> None:
    """T3.1 / AUB-COR-01: Ingestion report must show 0 quarantined documents."""
    data_dir = get_data_dir()
    report = ingest_protocols_with_report(data_dir, strict_unparsed=True)
    assert len(report.quarantined) == 0, f"Quarantined files: {report.quarantined}"
    assert len(report.unparsed_by_doc) == 0, f"Unparsed lines found: {report.unparsed_by_doc}"


def test_cross_syndrome_distractor_vocabulary() -> None:
    """T3.1 / AUB-COR-01: Distractor clinical findings must be shared across >= 3 syndromes."""
    data_dir = get_data_dir()
    report = ingest_protocols_with_report(data_dir, strict_unparsed=True)

    distractor_keywords = [
        "hypotension",
        "tachycardia",
        "respiratory distress",
        "shock",
        "hypoxia",
    ]

    for kw in distractor_keywords:
        matching_syndromes = {chunk.syndrome for chunk in report.chunks if kw in chunk.text.lower()}
        assert len(matching_syndromes) >= 3, (
            f"Distractor keyword '{kw}' only appeared in {len(matching_syndromes)} syndromes "
            f"({matching_syndromes}), expected >= 3 for genuine retrieval discrimination challenge."
        )


def test_all_synthetic_protocols_have_zero_numeric_doses() -> None:
    """Rule R9: All synthetic protocol documents must strictly contain zero numeric doses."""
    data_dir = get_data_dir()
    protocols_dir = data_dir / "protocols_synthetic"
    pattern = re.compile(r"\b[0-9]+(?:\.[0-9]+)?\s*(?:mg|mcg|g|mL|IU)\b", re.IGNORECASE)

    violations: list[str] = []
    for md_file in sorted(protocols_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        # Split off frontmatter
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else content
        matches = pattern.findall(body)
        if matches:
            violations.append(f"{md_file.name}: {matches}")

    assert violations == [], f"Rule R9 violations found: {violations}"
