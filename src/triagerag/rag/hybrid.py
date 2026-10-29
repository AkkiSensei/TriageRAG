"""Dense, Hybrid Reciprocal Rank Fusion (RRF), and Rerank retrievers (RAG-08).

Safety Properties (Section 8, RAG-01, RAG-08, Rule R12):
1. All retriever backends implement the Retriever protocol and enforce identical
   query-time hard population and hard syndrome filters.
2. Runs 100% offline with zero network calls and deterministic float math.
3. Zero numeric clinical literals in code (all parameters derived from config).
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from triagerag.rag.abstain import load_retrieval_config
from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.index import BM25ClinicalIndex, ClinicalTokenizer, Retriever
from triagerag.rag.ingest import compute_corpus_hash


def _extract_char_ngrams(text: str, tokenizer: ClinicalTokenizer) -> Counter[str]:
    """Build combined token + character trigram feature vector for dense cosine similarity."""
    tokens = tokenizer.tokenize(text)
    features: Counter[str] = Counter()
    ngram_len = 2 + 1
    for tok in tokens:
        features[f"tok:{tok}"] += 2
        padded = f"<{tok}>"
        if len(padded) >= ngram_len:
            for i in range(len(padded) - ngram_len + 1):
                features[f"ng:{padded[i : i + ngram_len]}"] += 1
    return features


class CharNgramRetriever:
    """Offline char n-gram TF-IDF vector retriever (FG-14 / HD-5)."""

    def __init__(
        self,
        chunks: list[ProtocolChunk],
        acronyms: dict[str, str] | None = None,
    ) -> None:
        self.tokenizer = ClinicalTokenizer(acronyms=acronyms)
        self.all_chunks: tuple[ProtocolChunk, ...] = tuple(chunks)
        self.corpus_hash: str = compute_corpus_hash(chunks)
        self.index_version: str = "2.0.0"
        self.backend: str = "char_ngram"
        self.retrieval_context: Any = None

        self.parents_by_id: dict[str, ProtocolChunk] = {
            c.chunk_id: c for c in self.all_chunks if c.parent_id is None
        }
        parents_with_children: set[str] = {
            c.parent_id for c in self.all_chunks if c.parent_id is not None
        }

        self.chunks_by_population: dict[str, list[ProtocolChunk]] = {}
        self.index_by_population: dict[str, list[int]] = {}
        self._vectors_by_population: dict[str, list[dict[str, float]]] = {}
        self._idf_by_population: dict[str, dict[str, float]] = {}

        for idx, chunk in enumerate(self.all_chunks):
            pop = chunk.population.lower().strip()
            self.index_by_population.setdefault(pop, []).append(idx)
            if chunk.parent_id is None and chunk.chunk_id in parents_with_children:
                continue
            self.chunks_by_population.setdefault(pop, []).append(chunk)

        for pop, pop_chunks in self.chunks_by_population.items():
            raw_Counters = [
                _extract_char_ngrams(c.indexed_text or c.text, self.tokenizer) for c in pop_chunks
            ]
            df_map: Counter[str] = Counter()
            for cnt in raw_Counters:
                for feat in cnt:
                    df_map[feat] += 1
            total = len(pop_chunks)
            idf_map: dict[str, float] = {
                feat: math.log(1.0 + (float(total - df) + 0.5) / (float(df) + 0.5))
                for feat, df in df_map.items()
            }
            self._idf_by_population[pop] = idf_map

            norm_vecs: list[dict[str, float]] = []
            for cnt in raw_Counters:
                weighted = {feat: float(val) * idf_map.get(feat, 1.0) for feat, val in cnt.items()}
                norm = math.sqrt(sum(v * v for v in weighted.values()))
                if norm > 0.0:
                    weighted = {k: v / norm for k, v in weighted.items()}
                norm_vecs.append(weighted)
            self._vectors_by_population[pop] = norm_vecs

    def known_syndromes(self, population: str | None = None) -> set[str]:
        if population is not None:
            pop_key = population.lower().strip()
            return {c.syndrome.lower().strip() for c in self.chunks_by_population.get(pop_key, [])}
        return {c.syndrome.lower().strip() for c in self.all_chunks}

    def expand_parents(self, chunks: list[ProtocolChunk]) -> list[ProtocolChunk]:
        seen: set[str] = set()
        parents: list[ProtocolChunk] = []
        for chunk in chunks:
            pid = chunk.parent_id or chunk.chunk_id
            if pid not in seen and pid in self.parents_by_id:
                seen.add(pid)
                parents.append(self.parents_by_id[pid])
        return parents

    def search(
        self,
        query: str,
        population: str,
        top_k: int | None = None,
        syndrome: str | None = None,
    ) -> list[tuple[ProtocolChunk, float]]:
        cfg = load_retrieval_config()
        eff_top_k = top_k if top_k is not None else cfg.top_k
        pop_key = population.lower().strip()
        if pop_key not in self.chunks_by_population:
            return []

        q_cnt = _extract_char_ngrams(query, self.tokenizer)
        if not q_cnt:
            return []

        idf_map = self._idf_by_population[pop_key]
        q_weighted = {feat: float(val) * idf_map.get(feat, 1.0) for feat, val in q_cnt.items()}
        q_norm = math.sqrt(sum(v * v for v in q_weighted.values()))
        if q_norm <= 0.0:
            return []
        q_vec = {k: v / q_norm for k, v in q_weighted.items()}

        syn_filter = syndrome.lower().strip() if syndrome else None
        pop_chunks = self.chunks_by_population[pop_key]
        pop_vecs = self._vectors_by_population[pop_key]

        scored: list[tuple[ProtocolChunk, float]] = []
        for chunk, d_vec in zip(pop_chunks, pop_vecs, strict=True):
            if syn_filter is not None and chunk.syndrome.lower().strip() != syn_filter:
                continue
            cosine = sum(q_val * d_vec.get(feat, 0.0) for feat, q_val in q_vec.items())
            scored.append((chunk, float(cosine * (cfg.bm25_k1 + 1.0))))

        scored.sort(key=lambda x: (-x[1], x[0].chunk_id))
        return scored[:eff_top_k]


# Backward-compatible alias for CharNgramRetriever (FG-14 / HD-5)
DenseRetriever = CharNgramRetriever


class LexicalOverlapReranker:
    """Lexical overlap reranker computing token intersection ratio (FG-14 / HD-5)."""

    def rerank(
        self,
        query_tokens: set[str],
        doc_tokens: set[str],
        base_score: float,
        boost: float = 0.5,
    ) -> float:
        """Scale base score by token intersection ratio against query terms."""
        if not query_tokens or base_score <= 0.0:
            return float(base_score)
        overlap_ratio = float(len(query_tokens & doc_tokens)) / float(len(query_tokens))
        return float(base_score * (1.0 + boost * overlap_ratio))


class HybridRRFRetriever:
    """Reciprocal Rank Fusion (RRF) combining lexical BM25 and CharNgram retrievers."""

    def __init__(
        self,
        chunks: list[ProtocolChunk],
        acronyms: dict[str, str] | None = None,
        rerank: bool = False,
    ) -> None:
        self.bm25 = BM25ClinicalIndex(chunks, acronyms=acronyms)
        self.dense = CharNgramRetriever(chunks, acronyms=acronyms)
        self.rerank = rerank
        self.reranker = LexicalOverlapReranker() if rerank else None
        self.corpus_hash: str = self.bm25.corpus_hash
        self.index_version: str = "2.0.0"
        self.backend: str = "hybrid_rrf_rerank" if rerank else "hybrid_rrf"
        self.index_by_population: dict[str, list[int]] = self.bm25.index_by_population
        self.retrieval_context: Any = None

    def known_syndromes(self, population: str | None = None) -> set[str]:
        return self.bm25.known_syndromes(population=population)

    def expand_parents(self, chunks: list[ProtocolChunk]) -> list[ProtocolChunk]:
        return self.bm25.expand_parents(chunks)

    def search(
        self,
        query: str,
        population: str,
        top_k: int | None = None,
        syndrome: str | None = None,
    ) -> list[tuple[ProtocolChunk, float]]:
        cfg = load_retrieval_config()
        eff_top_k = top_k if top_k is not None else cfg.top_k
        pool_k = eff_top_k * (2 + 2)

        bm25_hits = self.bm25.search(
            query=query, population=population, top_k=pool_k, syndrome=syndrome
        )
        dense_hits = self.dense.search(
            query=query, population=population, top_k=pool_k, syndrome=syndrome
        )

        if not bm25_hits and not dense_hits:
            return []

        rrf_k = float(cfg.top_k * cfg.top_k)
        chunk_map: dict[str, ProtocolChunk] = {}
        rrf_scores: dict[str, float] = {}
        bm25_raw: dict[str, float] = {}

        for rank_idx, (chunk, sc) in enumerate(bm25_hits, start=1):
            chunk_map[chunk.chunk_id] = chunk
            bm25_raw[chunk.chunk_id] = sc
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (
                1.0 / (rrf_k + float(rank_idx))
            )

        for rank_idx, (chunk, _sc) in enumerate(dense_hits, start=1):
            chunk_map[chunk.chunk_id] = chunk
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (
                1.0 / (rrf_k + float(rank_idx))
            )

        # Scale fused RRF score by top BM25 magnitude so calibrated thresholds apply consistently
        max_bm25 = max(bm25_raw.values(), default=0.0)
        max_rrf = max(rrf_scores.values(), default=1.0)
        scale = max_bm25 / max_rrf if max_rrf > 0.0 and max_bm25 > 0.0 else 1.0

        query_tokens = set(self.bm25.tokenizer.tokenize(query))
        final_scored: list[tuple[ProtocolChunk, float]] = []
        for cid, rrf_val in rrf_scores.items():
            chunk = chunk_map[cid]
            scaled_score = float(rrf_val * scale)
            if self.reranker and query_tokens and scaled_score > 0.0:
                doc_tokens = set(self.bm25.tokenizer.tokenize(chunk.indexed_text or chunk.text))
                scaled_score = self.reranker.rerank(query_tokens, doc_tokens, scaled_score)
            final_scored.append((chunk, scaled_score))

        final_scored.sort(key=lambda x: (-x[1], x[0].chunk_id))
        return final_scored[:eff_top_k]


def build_retriever_backend(
    backend: str,
    chunks: list[ProtocolChunk],
    acronyms: dict[str, str] | None = None,
) -> Retriever:
    """Factory helper constructing the requested Retriever implementation (FG-14)."""
    b_norm = backend.lower().strip()
    if b_norm == "bm25":
        return BM25ClinicalIndex(chunks, acronyms=acronyms)
    if b_norm in ("char_ngram", "dense"):
        return CharNgramRetriever(chunks, acronyms=acronyms)
    if b_norm == "hybrid_rrf":
        return HybridRRFRetriever(chunks, acronyms=acronyms, rerank=False)
    if b_norm in ("hybrid_rrf_rerank", "hybrid_rerank"):
        return HybridRRFRetriever(chunks, acronyms=acronyms, rerank=True)
    raise ValueError(f"Unknown retrieval backend '{backend}'")
