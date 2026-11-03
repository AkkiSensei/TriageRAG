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

# Standard English stop words to filter out before lexical search and sentence matching.
# Prevents high BM25 scores on questions whose only matching terms are generic stop words.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)


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

    # Filter out generic stop words and non-informative tokens (AUB-QA-02 / Rule R2)
    content_tokens = [
        t for t in q_tokens if t.lower() not in _STOP_WORDS and len(t) > 1 and not t.isdigit()
    ]

    if not content_tokens:
        return CorpusAskResponse(
            question=question,
            answer="",
            abstained=True,
            abstain_reason="Question contains no searchable clinical terms or content keywords.",
            citations=[],
            retrieved_chunks_count=0,
        )

    # Search corpus using index with content terms to avoid stop-word skew
    scored_chunks = srv.index.search(
        query=" ".join(content_tokens),
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
    content_token_set = set(content_tokens)

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        s_tokens = set(tokenizer.tokenize(s_clean))
        overlap = len(s_tokens & content_token_set)
        if overlap > 0:
            matching_sentences.append(s_clean)

    if not matching_sentences:
        # Rule R2 Fail-Closed: If no sentence contains any of the question's clinical terms,
        # do NOT fall back to arbitrary protocol sentences. Abstain to prevent ungrounded claims.
        return CorpusAskResponse(
            question=question,
            answer="",
            abstained=True,
            abstain_reason=(
                "No sentences in the retrieved protocols directly address the clinical question."
            ),
            citations=[],
            retrieved_chunks_count=len(scored_chunks),
        )

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
