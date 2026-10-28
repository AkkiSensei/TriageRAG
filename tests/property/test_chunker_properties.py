"""Hypothesis property-based tests for the grammar-based protocol chunker (WP2).

Safety Property (RAG-05):
Across 500 randomly generated protocol documents containing valid IF/THEN nodes
(with optional ELSE IF, ELSE, and bullet sub-steps), malformed IF nodes lacking THEN,
numbered non-IF items, horizontal rules, and trailing non-decision sections:
1. The round-trip line accounting invariant holds 100% of the time.
2. No valid IF...THEN node is ever lost or split.
3. No malformed node or trailing section text is ever absorbed into a child node.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from triagerag.rag.chunking import chunk_protocol_markdown, verify_round_trip_invariant

_SAFE_WORDS = st.sampled_from(
    [
        "hypotension",
        "tachycardia",
        "bradycardia",
        "hypoxia",
        "wheezing",
        "stridor",
        "confusion",
        "epinephrine",
        "salbutamol",
        "dextrose",
        "oxygen",
        "electrocardiogram",
        "monitoring",
        "resuscitation",
        "airway",
        "perfusion",
        "capillary",
        "vascular",
    ]
)

_PHRASE = st.lists(_SAFE_WORDS, min_size=2, max_size=6).map(lambda ws: " ".join(ws))


@st.composite
def _valid_node_strategy(draw: st.DrawFn, idx: int) -> tuple[str, str]:
    cond = draw(_PHRASE)
    act = draw(_PHRASE)
    lines = [f"{idx}. IF {cond}:", f"   THEN perform {act}."]
    if draw(st.booleans()):
        sub = draw(_PHRASE)
        lines.append(f"   - sub-step {sub}")
    if draw(st.booleans()):
        else_cond = draw(_PHRASE)
        else_act = draw(_PHRASE)
        lines.append(f"   ELSE IF {else_cond}:")
        lines.append(f"   THEN consider {else_act}.")
    if draw(st.booleans()):
        fallback = draw(_PHRASE)
        lines.append("   ELSE:")
        lines.append(f"   THEN monitor {fallback}.")
    node_str = "\n".join(lines)
    return node_str, cond


@st.composite
def _protocol_doc_strategy(draw: st.DrawFn) -> tuple[str, int, list[str]]:
    num_items = draw(st.integers(min_value=1, max_value=6))
    body_parts: list[str] = [
        "# Synthetic Generated Protocol",
        "",
        "> **DISCLAIMER:** Synthetic property test document.",
        "",
        "## Primary Decision Section",
    ]

    valid_count = 0
    expected_unparsed_substrings: list[str] = []

    for i in range(1, num_items + 1):
        kind = draw(st.sampled_from(["valid", "valid", "no_then", "non_if"]))
        if kind == "valid":
            node_text, _ = draw(_valid_node_strategy(i))
            body_parts.append(node_text)
            valid_count += 1
        elif kind == "no_then":
            phrase = draw(_PHRASE)
            line = f"{i}. IF {phrase} without action keyword:"
            dangling = f"   Dangling observation {phrase}."
            body_parts.append(line)
            body_parts.append(dangling)
            expected_unparsed_substrings.append(line)
        else:
            phrase = draw(_PHRASE)
            line = f"{i}. General note about {phrase} with no conditional."
            body_parts.append(line)
            expected_unparsed_substrings.append(line)

        if draw(st.booleans()):
            body_parts.append("---")

    # Optionally add a trailing non-decision section
    if draw(st.booleans()):
        trailing_phrase = draw(_PHRASE)
        trailing_line = f"Trailing commentary regarding {trailing_phrase}."
        body_parts.append("")
        body_parts.append("## Notes")
        body_parts.append(trailing_line)
        expected_unparsed_substrings.append(trailing_line)

    frontmatter = (
        "---\n"
        'doc_id: "PROP_DOC"\n'
        'title: "Generated Property Protocol"\n'
        'section: "Primary Decision Section"\n'
        'population: "adult"\n'
        'syndrome: "chest_pain"\n'
        'chunk_id: "PROP_01"\n'
        "synthetic: true\n"
        "---\n"
    )
    full_md = frontmatter + "\n".join(body_parts) + "\n"
    return full_md, valid_count, expected_unparsed_substrings


@settings(max_examples=500, deadline=None)
@given(data=_protocol_doc_strategy())
def test_chunker_round_trip_invariant_500_generated_docs(
    data: tuple[str, int, list[str]],
) -> None:
    """WP2 Gate: Round-trip invariant holds across 500 generated protocol markdown documents."""
    full_md, expected_valid_count, expected_unparsed = data
    chunks = chunk_protocol_markdown(full_md)

    assert verify_round_trip_invariant(full_md, chunks) is True

    parent = chunks[0]
    children = [c for c in chunks[1:] if c.parent_id is not None]
    assert len(children) == expected_valid_count

    for child in children:
        assert "IF " in child.text
        assert "THEN " in child.text
        assert "## Notes" not in child.text

    for unparsed_line in expected_unparsed:
        assert unparsed_line in parent.unparsed_lines
        for child in children:
            assert unparsed_line not in child.text
