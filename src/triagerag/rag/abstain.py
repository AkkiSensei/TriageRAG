"""Abstention module for protocol retrieval.

Safety Property (Rule R2, Section 8):
If no protocols exist for a patient's population category, or if the best
retrieval score falls below the confidence threshold, the retrieval module
must abstain. When abstaining, RetrievalReport.abstained is set to True and
no ungrounded protocol text is passed to plan drafting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triagerag.rag.chunking import ProtocolChunk

DEFAULT_MIN_RETRIEVAL_THRESHOLD: float = 0.3


def evaluate_abstention(
    scored_chunks: list[tuple[ProtocolChunk, float]],
    population: str,
    population_available: bool,
    threshold: float = DEFAULT_MIN_RETRIEVAL_THRESHOLD,
) -> tuple[bool, str | None]:
    """Determine whether retrieval should abstain based on population coverage and score."""
    if not population_available or not scored_chunks:
        return (
            True,
            f"No verified protocol chunks available for population '{population}'",
        )

    best_score = scored_chunks[0][1]
    if best_score < threshold:
        msg = f"Top retrieval score {best_score:.2f} is below minimum threshold {threshold:.2f}"
        return True, msg

    return False, None
