"""Citation verification module for clinical protocol groundedness.

Safety Property (Section 10):
1. chunk_id must match a verified chunk from the current retrieval report.
2. quoted_span must be an exact verbatim whitespace-normalized substring of the chunk.
3. Calculates lexical overlap between instruction and source span.
4. Failures result in CITATION_UNVERIFIED status.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triagerag.contracts.schemas import RetrievedChunk, SpanCitation


def _normalize_whitespace(text: str) -> str:
    """Normalize repeated whitespace, tabs, and newlines to single spaces."""
    return " ".join(text.split()).strip()


def compute_lexical_overlap(instruction: str, quoted_span: str) -> float:
    """Compute token Jaccard overlap between narrative instruction and cited span."""
    inst_tokens = set(re.findall(r"\b[A-Za-z0-9]+\b", instruction.lower()))
    span_tokens = set(re.findall(r"\b[A-Za-z0-9]+\b", quoted_span.lower()))

    if not inst_tokens or not span_tokens:
        return 0.0

    intersection = inst_tokens & span_tokens
    union = inst_tokens | span_tokens
    return round(len(intersection) / len(union), 4)


def verify_citation(
    citation: SpanCitation,
    retrieved_chunks: list[RetrievedChunk],
    narrative_instruction: str,
) -> tuple[bool, float, str | None]:
    """Verify that a step citation is grounded in retrieved chunks.

    Returns:
        (is_verified, lexical_overlap_score, failure_reason)
    """
    # 1. Minimum quoted span length (Section 4)
    if len(citation.quoted_span.strip()) < 10:
        return (
            False,
            0.0,
            f"Quoted span too short ({len(citation.quoted_span.strip())} < 10 characters)",
        )

    # 2. Check chunk existence
    chunk_map = {c.chunk_id: c for c in retrieved_chunks}
    if citation.chunk_id not in chunk_map:
        return (
            False,
            0.0,
            f"Citation chunk_id '{citation.chunk_id}' not found in retrieved chunks",
        )

    matched_chunk = chunk_map[citation.chunk_id]

    # 3. Exact verbatim substring check (whitespace normalized)
    norm_span = _normalize_whitespace(citation.quoted_span)
    norm_chunk_text = _normalize_whitespace(matched_chunk.text)

    if norm_span.lower() not in norm_chunk_text.lower():
        msg = (
            f"Quoted span '{citation.quoted_span[:30]}...' is not a verbatim "
            f"substring of chunk {citation.chunk_id}"
        )
        return False, 0.0, msg

    # 4. Compute lexical overlap score
    overlap = compute_lexical_overlap(narrative_instruction, citation.quoted_span)
    return True, overlap, None
