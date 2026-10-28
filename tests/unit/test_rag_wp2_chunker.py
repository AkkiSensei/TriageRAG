"""Unit tests for WP2: Grammar-based chunker, ELSE/sub-steps, contextual headers, and JSON graph.

Safety Properties (RAG-05, RAG-06):
1. Round-trip invariant holds on all bundled protocol documents with zero unparsed lines.
2. Multi-branch IF / THEN / ELSE IF / ELSE and nested sub-step bullets stay in one atomic node.
3. Contextual headers ('{title} › {section} › {syndrome} › {chunk_id}') are indexed by BM25
   while 'text' remains pure verbatim node text for citation verification.
4. JSON decision-graph adapter produces valid parent and child ProtocolChunks.
"""

from __future__ import annotations

from triagerag.config import get_data_dir
from triagerag.rag.chunking import (
    chunk_decision_graph_json,
    chunk_protocol_markdown,
    verify_round_trip_invariant,
)
from triagerag.rag.index import BM25ClinicalIndex


def test_bundled_corpus_satisfies_round_trip_invariant() -> None:
    """RAG-05: Every bundled protocol satisfies the round-trip invariant with 0 unparsed lines."""
    synth_dir = get_data_dir() / "protocols_synthetic"
    md_files = sorted(synth_dir.glob("*.md"))
    assert len(md_files) >= 6

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        chunks = chunk_protocol_markdown(content, source_path=md_file)
        assert verify_round_trip_invariant(content, chunks), f"Invariant failed for {md_file.name}"
        assert chunks[0].unparsed_lines == (), (
            f"Unexpected unparsed lines in {md_file.name}: {chunks[0].unparsed_lines}"
        )
        assert len(chunks) >= 4  # 1 parent + at least 3 child nodes


def test_else_branches_and_nested_substeps_preserved_in_node() -> None:
    """RAG-05: ELSE IF, ELSE, and indented bullet sub-steps remain inside the atomic child node."""
    md = """---
doc_id: "COMPLEX_DOC"
title: "Complex Airway Protocol"
section: "Emergency Intubation"
population: "adult"
syndrome: "anaphylaxis"
chunk_id: "COMPLEX_01"
synthetic: true
---
# Complex Airway Protocol

## Emergency Intubation
1. IF stridor or severe upper airway edema is present:
   THEN prepare immediate difficult airway cart:
   - pre-oxygenate with high-flow reservoir mask
   - summon senior airway specialist
   ELSE IF mild wheezing without stridor is present:
   THEN administer nebulized bronchodilator therapy
   ELSE:
   THEN continue continuous pulse oximetry monitoring.
"""
    chunks = chunk_protocol_markdown(md)
    assert verify_round_trip_invariant(md, chunks)
    assert chunks[0].unparsed_lines == ()
    children = [c for c in chunks if c.parent_id is not None]
    assert len(children) == 1
    node = children[0]
    assert "IF stridor" in node.text
    assert "- pre-oxygenate" in node.text
    assert "- summon senior airway specialist" in node.text
    assert "ELSE IF mild wheezing" in node.text
    assert "ELSE:" in node.text
    assert "continue continuous pulse oximetry" in node.text


def test_contextual_header_populated_and_indexed_by_bm25() -> None:
    """RAG-06: Child node indexed_text carries contextual header while text stays verbatim."""
    md = """---
doc_id: "CTX_DOC"
title: "Acute Pericarditis Guideline"
section: "Hemodynamic Tamponade Screening"
population: "adult"
syndrome: "chest_pain"
chunk_id: "CTX_01"
synthetic: true
---
1. IF pulsus paradoxus or muffled heart sounds are observed:
   THEN perform urgent bedside echocardiography.
"""
    chunks = chunk_protocol_markdown(md)
    child = chunks[1]
    assert child.chunk_id == "CTX_01_NODE_1"
    # Raw text must NOT contain the contextual header prefix
    assert "Acute Pericarditis Guideline ›" not in child.text
    assert child.text.startswith("1. IF pulsus paradoxus")
    # Indexed text MUST contain the contextual header
    expected_header = (
        "Acute Pericarditis Guideline › Hemodynamic Tamponade Screening › "
        "chest_pain › CTX_01_NODE_1"
    )
    assert expected_header in child.indexed_text

    # Searching for section/title terms ('pericarditis tamponade') must match the child node
    # via its contextual header even though those words do not appear in child.text!
    distractor_md = """---
doc_id: "OTHER_DOC"
title: "General Triage Note"
section: "Routine Observation"
population: "adult"
syndrome: "chest_pain"
chunk_id: "OTHER_01"
synthetic: true
---
1. IF mild stable symptoms are present:
   THEN monitor vital signs periodically.
"""
    distractor_chunks = chunk_protocol_markdown(distractor_md)
    index = BM25ClinicalIndex([child, *distractor_chunks])
    results = index.search("pericarditis tamponade", population="adult", top_k=1)
    assert len(results) == 1
    matched_chunk, score = results[0]
    assert matched_chunk.chunk_id == "CTX_01_NODE_1"
    assert score > 0.0


def test_decision_graph_json_adapter() -> None:
    """RAG-05: JSON decision graph flowchart converts cleanly into parent and child chunks."""
    graph = {
        "frontmatter": {
            "doc_id": "FLOW_ANAPHYLAXIS",
            "title": "Anaphylaxis Flowchart",
            "section": "Resuscitation Algorithm",
            "population": "adult",
            "syndrome": "anaphylaxis",
            "chunk_id": "FLOW_01",
            "synthetic": True,
        },
        "nodes": [
            {
                "if_condition": "airway compromise or shock is present",
                "then_action": "administer intramuscular epinephrine immediately.",
                "else_action": "observe closely in monitored bay.",
            },
            {
                "if_condition": "bronchospasm persists after epinephrine",
                "then_action": "administer inhaled salbutamol.",
            },
        ],
    }
    chunks = chunk_decision_graph_json(graph)
    assert len(chunks) == 3
    assert chunks[0].chunk_id == "FLOW_01"
    assert chunks[1].chunk_id == "FLOW_01_NODE_1"
    assert "ELSE observe closely" in chunks[1].text
    assert chunks[2].chunk_id == "FLOW_01_NODE_2"
