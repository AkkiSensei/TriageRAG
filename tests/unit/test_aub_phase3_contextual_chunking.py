"""Tests for AUB Phase 3 Task 3.5: Contextual Chunking Research Arm (AUB-COR-03).

Safety Properties (AUB-COR-03, T3.5, Rules R1, R2, R3, R9):
1. Verbatim node text and content hashes are 100% invariant whether contextual chunking
   is active or not (preserves exact citation verification and hash stability).
2. Child nodes (idx > 1) in a protocol branch receive the extracted governing condition
   prepended to indexed_text when contextual_chunking=True.
3. Node 1 is the governing root condition and does not depend on itself.
4. Decision rule decide_backend() reports contextual chunking as an ablation arm and
   adopts it only if hard safety invariants and clinical gain thresholds are met.
"""

from __future__ import annotations

from eval.run_retrieval_ablation import decide_backend
from triagerag.config import get_data_dir
from triagerag.rag.abstain import load_retrieval_config
from triagerag.rag.chunking import (
    chunk_decision_graph_json,
    chunk_protocol_markdown,
    compute_node_hash,
    extract_if_condition,
)
from triagerag.rag.service import RetrievalService

SAMPLE_PROTOCOL_MD = """---
doc_id: PROTO_CHEST_SAMPLE
title: Acute Chest Discomfort Management
section: Acute Coronary Evaluation
population: adult
syndrome: chest_pain
chunk_id: PROTO_CHEST_SAMPLE_SEC1
synthetic: true
version: 1.0.0
license_tag: synthetic
---
# Acute Chest Discomfort Management
> Research prototype. Synthetic data only. Not a medical device. Not for clinical use.
## Acute Coronary Evaluation
1. IF patient presents with acute crushing retrosternal chest pain and hypoperfusion:
   THEN assess 12-lead ECG and initiate continuous telemetry.
2. IF ECG demonstrates diagnostic ST-segment elevation:
   THEN activate emergent cardiac catheterization laboratory.
3. IF systolic blood pressure drops below 90 mmHg:
   THEN withhold sublingual nitroglycerin and administer IV normal saline.
"""


def test_extract_if_condition_parsing() -> None:
    """Verifies that extract_if_condition extracts the clean condition from decision clauses."""
    node1 = (
        "1. IF patient presents with acute crushing retrosternal chest pain and hypoperfusion:\n"
        "   THEN assess 12-lead ECG and initiate continuous telemetry."
    )
    cond1 = extract_if_condition(node1)
    assert cond1 == "patient presents with acute crushing retrosternal chest pain and hypoperfusion"

    node2 = "2. IF ECG demonstrates diagnostic ST-segment elevation THEN activate cath lab."
    cond2 = extract_if_condition(node2)
    assert cond2 == "ECG demonstrates diagnostic ST-segment elevation"

    non_if = "Some stray text without condition"
    assert extract_if_condition(non_if) is None


def test_default_chunking_preserves_unmodified_indexed_text() -> None:
    """With contextual_chunking=False, contextual_chunking_applied is False and indexed_text is standard."""
    chunks = chunk_protocol_markdown(SAMPLE_PROTOCOL_MD, contextual_chunking=False)
    assert len(chunks) == 4  # 1 parent + 3 children
    for child in chunks[1:]:
        assert child.contextual_chunking_applied is False
        assert "Governing Context:" not in child.indexed_text


def test_contextual_chunking_prepends_governing_condition_to_dependent_nodes() -> None:
    """With contextual_chunking=True, node 1 remains governing and nodes 2..N receive governing context."""
    chunks = chunk_protocol_markdown(SAMPLE_PROTOCOL_MD, contextual_chunking=True)
    assert len(chunks) == 4

    _parent = chunks[0]
    node1 = chunks[1]
    node2 = chunks[2]
    node3 = chunks[3]

    # Node 1 is the governing root condition -> not prepended with itself
    assert node1.contextual_chunking_applied is False
    assert "Governing Context:" not in node1.indexed_text

    # Node 2 and Node 3 are dependent nodes -> receive governing condition in indexed_text
    expected_context = (
        "patient presents with acute crushing retrosternal chest pain and hypoperfusion"
    )
    assert node2.contextual_chunking_applied is True
    assert f"Governing Context: {expected_context}" in node2.indexed_text

    assert node3.contextual_chunking_applied is True
    assert f"Governing Context: {expected_context}" in node3.indexed_text


def test_contextual_chunking_preserves_verbatim_text_and_content_hash() -> None:
    """Crucial safety invariant: verbatim text and content hashes are 100% identical."""
    standard_chunks = chunk_protocol_markdown(SAMPLE_PROTOCOL_MD, contextual_chunking=False)
    contextual_chunks = chunk_protocol_markdown(SAMPLE_PROTOCOL_MD, contextual_chunking=True)

    assert len(standard_chunks) == len(contextual_chunks)
    for std, ctx in zip(standard_chunks, contextual_chunks, strict=True):
        assert std.chunk_id == ctx.chunk_id
        assert std.text == ctx.text  # Verbatim node text unchanged for citations!
        assert std.content_hash == ctx.content_hash  # Hash identity preserved!
        assert compute_node_hash(std.text) == compute_node_hash(ctx.text)


def test_chunk_decision_graph_json_supports_contextual_chunking() -> None:
    """Flowchart JSON adapter also supports contextual chunking."""
    graph = {
        "frontmatter": {
            "doc_id": "GRAPH_01",
            "title": "Flowchart Test",
            "section": "Emergency Steps",
            "population": "adult",
            "syndrome": "chest_pain",
            "chunk_id": "GRAPH_01_SEC1",
            "synthetic": True,
            "license_tag": "synthetic",
        },
        "nodes": [
            {
                "if_condition": "patient exhibits altered mental status",
                "then_action": "check point-of-care capillary blood glucose",
            },
            {
                "if_condition": "blood glucose is below 60 mg/dL",
                "then_action": "administer intravenous 25g dextrose 50%",
            },
        ],
    }
    chunks = chunk_decision_graph_json(graph, contextual_chunking=True)
    assert len(chunks) == 3
    node1 = chunks[1]
    node2 = chunks[2]
    assert node1.contextual_chunking_applied is False
    assert node2.contextual_chunking_applied is True
    assert "Governing Context: patient exhibits altered mental status" in node2.indexed_text


def test_retrieval_config_schema_contains_contextual_chunking_flag() -> None:
    """RetrievalConfig loads contextual_chunking flag correctly from config.yaml."""
    cfg = load_retrieval_config(get_data_dir())
    assert hasattr(cfg, "contextual_chunking")
    assert isinstance(cfg.contextual_chunking, bool)


def test_retrieval_service_supports_contextual_chunking_backend() -> None:
    """RetrievalService builds and caches contextual chunking index cleanly."""
    service_default = RetrievalService.create_default(get_data_dir(), backend="bm25")
    service_ctx = RetrievalService.create_default(
        get_data_dir(), backend="bm25", contextual_chunking=True
    )

    default_children = [c for c in service_default.list_chunks() if c.parent_id is not None]
    ctx_children = [c for c in service_ctx.list_chunks() if c.parent_id is not None]

    assert any(c.contextual_chunking_applied for c in ctx_children)
    assert not any(c.contextual_chunking_applied for c in default_children)


def test_decide_backend_evaluates_contextual_arm() -> None:
    """decide_backend evaluates contextual arm and adopts it only on qualifying MRR gain."""
    mock_arms = {
        "bm25": {
            "test_split": {
                "wrong_protocol_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 10.0,
                "recall_at_5": 0.90,
                "mrr": 0.75,
            }
        },
        "bm25_contextual": {
            "test_split": {
                "wrong_protocol_rate": 0.0,
                "abstain_recall_hard_negatives": 1.0,
                "latency_p95_ms": 11.0,
                "recall_at_5": 0.90,
                "mrr": 0.77,  # Gain is +0.02 (< 0.05 threshold) -> retain bm25
            }
        },
    }
    decision = decide_backend(mock_arms)
    assert decision == "bm25"

    # Now simulate a qualifying +0.06 MRR improvement with statistical distinguishability (T4.7)
    mock_arms["bm25_contextual"]["test_split"]["mrr"] = 0.82
    mock_arms["bm25_contextual"]["test_split"]["statistically_distinguishable_from_bm25"] = True
    decision_gain = decide_backend(mock_arms)
    assert decision_gain == "bm25_contextual"
