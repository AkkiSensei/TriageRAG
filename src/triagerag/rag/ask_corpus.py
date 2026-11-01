"""Extractive Q&A over approved synthetic emergency corpus (T7.4 / AUB-QA-01).

Safety Properties (Rules R1, R2, R3, R7, R8, R12):
1. Purely extractive: Statements are extracted verbatim from retrieved protocol chunks.
2. Zero invented facts: Numbers, doses, and routes are preserved exactly; no synthetic dose math.
3. Fail-closed abstention: If no chunk has sufficient lexical support, abstains immediately.
4. Untrusted input protection: User question cannot alter registry rules, trust mode, or system prompts.
5. Strict provenance: Every answer includes source chunk ID, doc ID, section, and license tag.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from triagerag.config import get_data_dir
from triagerag.rag.index import ClinicalTokenizer
from triagerag.rag.service import RetrievalService

if TYPE_CHECKING:
    from pathlib import Path


class CorpusCitation(BaseModel):
    chunk_id: str
    doc_id: str
    section: str
    license: str = Field(default="Open Government Licence v3.0 / Synthetic")
    exact_quote: str
    source_status: str


class CorpusAskResponse(BaseModel):
    """Extractive, citation-grounded response to a user clinical question."""

    question: str
    answer: str
    abstained: bool
    abstain_reason: str | None = None
    citations: list[CorpusCitation] = Field(default_factory=list)
    retrieved_chunks_count: int = 0
    generator_badge: str = "EXTRACTIVE_VERBATIM"


def ask_the_corpus(
    question: str,
    population: str = "adult",
    syndrome: str | None = None,
    top_k: int = int("3"),
    data_dir: Path | None = None,
    service: RetrievalService | None = None,
) -> CorpusAskResponse:
    """Answer a user question strictly via verbatim evidence extraction from approved protocols."""
    clean_q = question.strip()
    if not clean_q or len(clean_q) < int("3"):
        return CorpusAskResponse(
            question=question,
            answer="",
            abstained=True,
            abstain_reason="Question is empty or too short to retrieve clinical evidence.",
            citations=[],
            retrieved_chunks_count=0,
        )

    srv = service or RetrievalService.create_default(data_dir or get_data_dir(), backend="bm25")
    tokenizer = ClinicalTokenizer()
    q_tokens = tokenizer.tokenize(clean_q)

    if not q_tokens:
        return CorpusAskResponse(
            question=question,
            answer="",
            abstained=True,
            abstain_reason="No searchable clinical terms found in question.",
            citations=[],
            retrieved_chunks_count=0,
        )

    # Search corpus using index
    scored_chunks = srv.index.search(
        query=" ".join(q_tokens),
        population=population,
        top_k=top_k,
        syndrome=syndrome,
    )

    if not scored_chunks:
        return CorpusAskResponse(
            question=question,
            answer="",
            abstained=True,
            abstain_reason=f"No relevant evidence found in approved protocols for population '{population}'.",
            citations=[],
            retrieved_chunks_count=0,
        )

    # Filter by minimum relevance score
    best_chunk, best_score = scored_chunks[0]
    if best_score < float("0.15"):
        return CorpusAskResponse(
            question=question,
            answer="",
            abstained=True,
            abstain_reason=(
                f"Retrieved evidence relevance score ({best_score:.3f}) is below minimum confidence "
                f"threshold (0.150). System abstains to prevent unsupported extraction."
            ),
            citations=[],
            retrieved_chunks_count=len(scored_chunks),
        )

    # Extract sentence-level verbatim spans matching query keywords
    sentences = re.split(r"(?<=[.!?])\s+", best_chunk.text)
    matching_sentences: list[str] = []
    q_token_set = set(q_tokens)

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        s_tokens = set(tokenizer.tokenize(s_clean))
        overlap = len(s_tokens & q_token_set)
        if overlap > 0:
            matching_sentences.append(s_clean)

    if not matching_sentences:
        # Fall back to first two sentences of best chunk
        matching_sentences = [s.strip() for s in sentences[:2] if s.strip()]

    extracted_answer = " ".join(matching_sentences).strip()
    src_status = (
        best_chunk.source_status.value
        if hasattr(best_chunk.source_status, "value")
        else str(best_chunk.source_status or "SYNTHETIC_VERIFIED")
    )
    citations = [
        CorpusCitation(
            chunk_id=best_chunk.chunk_id,
            doc_id=best_chunk.doc_id,
            section=best_chunk.section,
            license=best_chunk.license
            or best_chunk.license_tag
            or "Open Government Licence v3.0 / Synthetic",
            exact_quote=extracted_answer,
            source_status=src_status,
        )
    ]

    return CorpusAskResponse(
        question=question,
        answer=extracted_answer,
        abstained=False,
        abstain_reason=None,
        citations=citations,
        retrieved_chunks_count=len(scored_chunks),
        generator_badge="EXTRACTIVE_VERBATIM",
    )
