"""Clinical protocol retrieval index using BM25 with acronym preservation.

Safety Property (Section 8):
1. Hard population filter: zero cross-population ranking.
2. Clinical acronym preservation: STEMI, DKA, SpO2, etc., are never corrupted.
3. Fully offline: BM25Okapi runs without external network or API access.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from triagerag.rag.chunking import ProtocolChunk


class ClinicalTokenizer:
    """Tokenizer that preserves clinical acronyms and expands them via dictionary."""

    def __init__(self, acronyms: dict[str, str] | None = None) -> None:
        self.acronyms = {k.upper(): v for k, v in (acronyms or {}).items()}

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text preserving clinical acronyms and appending expansions."""
        norm_text = text.replace("_", " ")
        raw_tokens = re.findall(r"\b[A-Za-z0-9\-\/]+\b", norm_text)
        tokens: list[str] = []

        for token in raw_tokens:
            cleaned = token.strip().lower()
            if not cleaned:
                continue
            tokens.append(cleaned)

            # Check for acronym expansion
            upper_token = token.upper()
            if upper_token in self.acronyms:
                expansion = self.acronyms[upper_token]
                expansion_tokens = re.findall(r"\b[A-Za-z0-9_\-\/]+\b", expansion.lower())
                tokens.extend(expansion_tokens)

        return tokens


class BM25ClinicalIndex:
    """Partitioned BM25 index enforcing strict population isolation."""

    def __init__(
        self,
        chunks: list[ProtocolChunk],
        acronyms: dict[str, str] | None = None,
    ) -> None:
        self.tokenizer = ClinicalTokenizer(acronyms)
        self.chunks_by_population: dict[str, list[ProtocolChunk]] = {}
        self.index_by_population: dict[str, BM25Okapi] = {}
        self.backend = "bm25"

        # Partition chunks strictly by population
        for chunk in chunks:
            pop = chunk.population.lower().strip()
            self.chunks_by_population.setdefault(pop, []).append(chunk)

        # Build BM25 index for each population slice
        for pop, pop_chunks in self.chunks_by_population.items():
            corpus_tokens = [self.tokenizer.tokenize(c.indexed_text or c.text) for c in pop_chunks]
            self.index_by_population[pop] = BM25Okapi(corpus_tokens)

    def search(
        self,
        query: str,
        population: str,
        top_k: int = 5,
    ) -> list[tuple[ProtocolChunk, float]]:
        """Search the index for a query within a single mandatory population category.

        Hard population filter: If no chunks exist for the specified population,
        immediately returns an empty list without falling back across populations.
        """
        pop_key = population.lower().strip()
        if pop_key not in self.index_by_population:
            return []

        pop_chunks = self.chunks_by_population[pop_key]
        bm25 = self.index_by_population[pop_key]

        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return []

        scores: list[float] = bm25.get_scores(query_tokens)  # type: ignore[assignment]
        # Boost atomic child decision nodes over broad whole-document parent chunks
        # to ensure actionable clinical decision nodes are prioritized
        scored_chunks: list[tuple[ProtocolChunk, float]] = []
        for chunk, score in zip(pop_chunks, scores, strict=True):
            boost = 1.15 if chunk.parent_id is not None else 1.0
            scored_chunks.append((chunk, score * boost))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        return scored_chunks[:top_k]
