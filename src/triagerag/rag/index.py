"""Clinical protocol retrieval index using global non-negative IDF BM25.

Safety Properties (Section 8, RAG-01, RAG-07, RAG-09):
1. Hard population filter at query time: zero cross-population ranking.
2. Hard syndrome filter at query time (when suspected_syndrome is provided): zero cross-syndrome
   contamination.
3. Global non-negative IDF across the corpus: eliminates small-shard IDF degeneracy (zero or
   negative scores on small paediatric/neonate pools).
4. Pure Python float scores: no numpy.float64 leakage and zero '# type: ignore' comments.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from triagerag.rag.abstain import load_retrieval_config
from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.ingest import compute_corpus_hash


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
    """BM25 index with global non-negative IDF and strict query-time population/syndrome filters."""

    def __init__(
        self,
        chunks: list[ProtocolChunk],
        acronyms: dict[str, str] | None = None,
    ) -> None:
        cfg = load_retrieval_config()
        self.k1: float = cfg.bm25_k1
        self.b: float = cfg.bm25_b
        self.child_node_boost: float = cfg.child_node_boost
        self.tokenizer = ClinicalTokenizer(acronyms)
        self.all_chunks: tuple[ProtocolChunk, ...] = tuple(chunks)
        self.corpus_hash: str = compute_corpus_hash(chunks)
        self.index_version: str = "2.0.0"
        self.chunks_by_population: dict[str, list[ProtocolChunk]] = {}
        self.index_by_population: dict[str, list[int]] = {}
        self.backend = "bm25"

        self._doc_term_freqs: list[Counter[str]] = []
        self._doc_lengths: list[int] = []
        self._doc_freqs: Counter[str] = Counter()

        for idx, chunk in enumerate(self.all_chunks):
            pop = chunk.population.lower().strip()
            self.chunks_by_population.setdefault(pop, []).append(chunk)
            self.index_by_population.setdefault(pop, []).append(idx)

            tokens = self.tokenizer.tokenize(chunk.indexed_text or chunk.text)
            tf = Counter(tokens)
            self._doc_term_freqs.append(tf)
            self._doc_lengths.append(len(tokens))
            for term in tf:
                self._doc_freqs[term] += 1

        total_docs = len(self.all_chunks)
        self._total_docs: int = total_docs
        self._avgdl: float = (
            float(sum(self._doc_lengths)) / float(total_docs) if total_docs > 0 else 1.0
        )
        self._idf: dict[str, float] = {}
        for term, df in self._doc_freqs.items():
            # Non-negative Lucene/BM25+ IDF: ln(1 + (N - df + 0.5) / (df + 0.5)) > 0 always
            self._idf[term] = math.log(1.0 + (float(total_docs - df) + 0.5) / (float(df) + 0.5))

    def known_syndromes(self, population: str | None = None) -> set[str]:
        """Return set of syndromes present in the index (optionally scoped to population)."""
        if population is not None:
            pop_key = population.lower().strip()
            return {c.syndrome.lower().strip() for c in self.chunks_by_population.get(pop_key, [])}
        return {c.syndrome.lower().strip() for c in self.all_chunks}

    def _score_doc(self, doc_idx: int, query_tokens: list[str]) -> float:
        """Compute pure-Python float BM25 score for a single document index."""
        tf_map = self._doc_term_freqs[doc_idx]
        dl = float(self._doc_lengths[doc_idx])
        norm_denom_base = self.k1 * (1.0 - self.b + self.b * (dl / self._avgdl))
        score = 0.0
        for token in query_tokens:
            tf = float(tf_map.get(token, 0))
            if tf <= 0.0:
                continue
            idf = self._idf.get(token, 0.0)
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + norm_denom_base
            score += idf * (numerator / denominator)
        return float(score)

    def search(
        self,
        query: str,
        population: str,
        top_k: int | None = None,
        syndrome: str | None = None,
    ) -> list[tuple[ProtocolChunk, float]]:
        """Search the index for a query within a mandatory population and optional syndrome.

        Hard population filter: If no chunks exist for the specified population,
        immediately returns an empty list without falling back across populations.
        Hard syndrome filter: If syndrome is specified, only chunks matching that
        syndrome are eligible.
        """
        cfg = load_retrieval_config()
        eff_top_k = top_k if top_k is not None else cfg.top_k

        pop_key = population.lower().strip()
        if pop_key not in self.index_by_population:
            return []

        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return []

        syn_filter = syndrome.lower().strip() if syndrome else None
        candidate_indices = self.index_by_population[pop_key]

        scored_chunks: list[tuple[ProtocolChunk, float]] = []
        for doc_idx in candidate_indices:
            chunk = self.all_chunks[doc_idx]
            if syn_filter is not None and chunk.syndrome.lower().strip() != syn_filter:
                continue
            raw_score = self._score_doc(doc_idx, query_tokens)
            boost = self.child_node_boost if chunk.parent_id is not None else 1.0
            scored_chunks.append((chunk, float(raw_score * boost)))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        return scored_chunks[:eff_top_k]
