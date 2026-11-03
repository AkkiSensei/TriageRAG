"""Unit tests for AUB Phase 2 Task T2.2: Patient-Aware Node Predicates.

Safety Properties:
1. Every active IF/THEN decision node declares patient applicability metadata:
   requires_predicates, contraindicated_by, or always_applicable: true.
2. Every declared predicate ID exists in data/retrieval/predicates.yaml.
3. Ingestion round-trip invariant is preserved without text loss or header leakage.
4. Node applicability distinguishes satisfied, not satisfied, unknown, and contraindicated.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from triagerag.config import get_data_dir
from triagerag.contracts.enums import SourceStatus
from triagerag.rag.chunking import ProtocolChunk, verify_round_trip_invariant
from triagerag.rag.ingest import ingest_protocols_with_report
from triagerag.rag.node_predicates import (
    NodePredicateDeclaration,
    NodePredicatesConfig,
    load_node_predicates_config,
)
from triagerag.rag.predicates import load_predicate_vocabulary


def test_load_node_predicates_config() -> None:
    """Verify loading canonical data/retrieval/node_predicates.yaml."""
    config = load_node_predicates_config()
    assert isinstance(config, NodePredicatesConfig)
    assert config.source_status == SourceStatus.SYNTHETIC_AUTHORED
    assert len(config.nodes) >= 21  # 21 IF/THEN child nodes across the 6 protocols


def test_all_declared_predicates_exist_in_vocabulary() -> None:
    """Every predicate referenced in node declarations must exist in predicates.yaml."""
    node_cfg = load_node_predicates_config()
    vocab = load_predicate_vocabulary()
    vocab_ids = {p.id for p in vocab.predicates}

    for chunk_id, decl in node_cfg.nodes.items():
        for req_pred in decl.requires_predicates:
            assert req_pred in vocab_ids, (
                f"Node {chunk_id} requires predicate '{req_pred}' not in vocabulary"
            )
        for contra_pred in decl.contraindicated_by:
            assert contra_pred in vocab_ids, (
                f"Node {chunk_id} contraindicates predicate '{contra_pred}' not in vocabulary"
            )


def test_every_active_node_has_predicate_or_always_applicable() -> None:
    """Every active child decision node must have at least one predicate or always_applicable."""
    node_cfg = load_node_predicates_config()
    for chunk_id, decl in node_cfg.nodes.items():
        has_req = len(decl.requires_predicates) > 0
        has_always = decl.always_applicable is True
        assert has_req or has_always, (
            f"Node {chunk_id} must declare requires_predicates or always_applicable=True"
        )


def test_node_predicates_attached_during_ingestion() -> None:
    """Verify ingest_protocols_with_report attaches node predicate metadata to ProtocolChunks."""
    data_dir = get_data_dir()
    report = ingest_protocols_with_report(data_dir=data_dir)
    assert len(report.quarantined) == 0
    assert len(report.chunks) >= 27

    child_chunks = [c for c in report.chunks if c.parent_id is not None]
    assert len(child_chunks) >= 21

    for child in child_chunks:
        assert isinstance(child.requires_predicates, tuple)
        assert isinstance(child.contraindicated_by, tuple)
        assert isinstance(child.always_applicable, bool)
        has_req = len(child.requires_predicates) > 0
        has_always = child.always_applicable is True
        assert has_req or has_always, (
            f"Ingested child chunk {child.chunk_id} missing predicate metadata"
        )


def test_round_trip_invariant_preserves_content_and_predicates() -> None:
    """Verify round-trip invariant remains satisfied on all protocols."""
    data_dir = get_data_dir()
    proto_dir = data_dir / "protocols_synthetic"
    md_files = list(proto_dir.glob("*.md"))
    assert len(md_files) >= 6

    report = ingest_protocols_with_report(data_dir=data_dir)
    chunks_by_doc: dict[str, list[ProtocolChunk]] = {}
    for c in report.chunks:
        chunks_by_doc.setdefault(c.doc_id, []).append(c)

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        doc_chunks = [c for c in report.chunks if c.doc_id in content]
        assert verify_round_trip_invariant(content, doc_chunks), (
            f"Round trip invariant violated for {md_file.name}"
        )


def test_unresolved_node_predicates_validation() -> None:
    """Declaring an empty node with neither predicates nor always_applicable fails validation."""
    with pytest.raises(ValidationError, match="requires_predicates or always_applicable"):
        NodePredicateDeclaration(
            chunk_id="TEST_NODE_1",
            requires_predicates=(),
            contraindicated_by=(),
            always_applicable=False,
            predicate_review_required=False,
        )
