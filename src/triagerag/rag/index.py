"""Clinical protocol retrieval index with non-negative IDF, morphology/synonyms, and parent dedupe.

Safety Properties (Section 8, RAG-01, RAG-07, RAG-09, Rule R12):
1. Hard population filter at query time: zero cross-population ranking, and adding documents
   to one population has zero effect on another population's scores or ranking.
2. Hard syndrome filter at query time (when suspected_syndrome is provided): zero cross-syndrome
   contamination.
3. Non-negative smoothed IDF (ln(1 + (N - df + 0.5)/(df + 0.5))) over deduplicated child decision
   nodes: eliminates small-pool IDF degeneracy (child nodes never collapse to 0.0).
4. Parent/child deduplication with explicit expand_parents(): top_k slots are never wasted on
   whole-document parent blobs when atomic child nodes exist.
5. Pure Python float scores: no numpy.float64 leakage and zero type-ignore suppressions.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml
from pydantic import BaseModel, ConfigDict

from triagerag.config import get_data_dir
from triagerag.contracts.schemas import Provenance
from triagerag.rag.abstain import RetrievalConfig, load_retrieval_config
from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.ingest import compute_corpus_hash


class SynonymsConfig(BaseModel):
    """Clinical synonym and morphology lexicon loaded from data/retrieval/synonyms.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    synonyms: dict[str, list[str]]
    provenance: Provenance


@lru_cache
def load_synonyms_config(data_dir: Path | None = None) -> SynonymsConfig:
    """Load and validate clinical synonyms and morphology map."""
    target_dir = data_dir or get_data_dir()
    syn_path = target_dir / "retrieval" / "synonyms.yaml"
    if not syn_path.exists():
        syn_path = get_data_dir() / "retrieval" / "synonyms.yaml"
    raw = yaml.safe_load(syn_path.read_text(encoding="utf-8"))
    return SynonymsConfig.model_validate(raw)


@lru_cache
def load_default_acronyms(data_dir: Path | None = None) -> dict[str, str]:
    """Load default clinical acronyms from data/acronyms.yaml."""
    target_dir = data_dir or get_data_dir()
    acr_path = target_dir / "acronyms.yaml"
    if not acr_path.exists():
        acr_path = get_data_dir() / "acronyms.yaml"
    if not acr_path.exists():
        return {}
    raw = yaml.safe_load(acr_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("acronyms"), dict):
        return {str(k).upper(): str(v) for k, v in raw["acronyms"].items()}
    return {}


def _light_clinical_stem(word: str) -> str | None:
    """Apply conservative suffix stripping for clinical plurals and verb forms."""
    min_len = 2 + 2
    if len(word) <= min_len:
        return None
    if word.endswith("ing") and len(word) > min_len + 2:
        return word[: -1 - 2]
    if word.endswith("ed") and len(word) > min_len + 1:
        return word[:-2]
    if word.endswith("es") and not word.endswith(("ses", "xes", "zes")) and len(word) > min_len + 1:
        return word[:-1]
    if word.endswith("s") and not word.endswith(("ss", "us", "is", "os")) and len(word) > min_len:
        return word[:-1]
    return None


class ClinicalTokenizer:
    """Tokenizer with acronym case rules, clinical morphology/synonyms, and light stemming."""

    def __init__(
        self,
        acronyms: dict[str, str] | None = None,
        synonyms: dict[str, list[str]] | None = None,
    ) -> None:
        base_acronyms = load_default_acronyms() if acronyms is None else acronyms
        self.acronyms = {k.upper(): v for k, v in base_acronyms.items()}
        self.synonyms = (
            load_synonyms_config().synonyms
            if synonyms is None
            else {k.lower(): [x.lower() for x in v] for k, v in synonyms.items()}
        )

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text preserving acronyms, applying case rules, and expanding synonyms/stems."""
        norm_text = text.replace("_", " ")
        raw_tokens = re.findall(r"\b[A-Za-z0-9\-\/]+\b", norm_text)
        tokens: list[str] = []

        for token in raw_tokens:
            cleaned = token.strip().lower()
            if not cleaned:
                continue
            tokens.append(cleaned)

            # 1. Light suffix stem
            stem = _light_clinical_stem(cleaned)
            if stem and stem != cleaned:
                tokens.append(stem)

            # 2. Clinical synonym / morphology / Hinglish expansion
            if cleaned in self.synonyms:
                for syn_target in self.synonyms[cleaned]:
                    for sub_tok in syn_target.replace("_", " ").split():
                        if sub_tok:
                            tokens.append(sub_tok)

            # 3. Acronym expansion (short <=2-char acronyms like HR/PE/RR require uppercase char)
            upper_token = token.upper()
            if upper_token in self.acronyms:
                is_short = len(upper_token) <= 2
                has_upper = any(ch.isupper() for ch in token)
                if not is_short or has_upper:
                    expansion = self.acronyms[upper_token]
                    expansion_tokens = re.findall(r"\b[A-Za-z0-9_\-\/]+\b", expansion.lower())
                    tokens.extend(expansion_tokens)

        return tokens


@runtime_checkable
class Retriever(Protocol):
    """Protocol for clinical guideline retrievers (BM25, Dense, Hybrid RRF)."""

    backend: str
    corpus_hash: str
    index_version: str
    index_by_population: dict[str, list[int]]
    retrieval_context: Any

    def known_syndromes(self, population: str | None = None) -> set[str]: ...

    def search(
        self,
        query: str,
        population: str,
        top_k: int | None = None,
        syndrome: str | None = None,
    ) -> list[tuple[ProtocolChunk, float]]: ...

    def expand_parents(self, chunks: list[ProtocolChunk]) -> list[ProtocolChunk]: ...


class _PopulationBM25Stats:
    """Precomputed non-negative IDF BM25 statistics for a single population partition."""

    def __init__(self, chunks: list[ProtocolChunk], tokenizer: ClinicalTokenizer) -> None:
        self.chunks: list[ProtocolChunk] = list(chunks)
        self.doc_term_freqs: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        self.doc_freqs: Counter[str] = Counter()
        self.indices_by_syndrome: dict[str, list[int]] = {}

        for idx, chunk in enumerate(self.chunks):
            syn_key = chunk.syndrome.lower().strip()
            self.indices_by_syndrome.setdefault(syn_key, []).append(idx)
            tokens = tokenizer.tokenize(chunk.indexed_text or chunk.text)
            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)
            self.doc_lengths.append(len(tokens))
            for term in tf:
                self.doc_freqs[term] += 1

        total = len(self.chunks)
        self.total_docs: int = total
        self.avgdl: float = float(sum(self.doc_lengths)) / float(total) if total > 0 else 1.0
        self.idf: dict[str, float] = {}
        for term, df in self.doc_freqs.items():
            # Non-negative smoothed IDF: ln(1 + (N - df + 0.5) / (df + 0.5)) > 0 always
            self.idf[term] = math.log(1.0 + (float(total - df) + 0.5) / (float(df) + 0.5))


class BM25ClinicalIndex:
    """BM25 index with non-negative IDF, parent/child deduplication, and strict isolation."""

    def __init__(
        self,
        chunks: list[ProtocolChunk],
        acronyms: dict[str, str] | None = None,
        synonyms: dict[str, list[str]] | None = None,
        config: RetrievalConfig | None = None,
        retrieval_context: Any = None,
    ) -> None:
        cfg = config if config is not None else load_retrieval_config()
        self.k1: float = cfg.bm25_k1
        self.b: float = cfg.bm25_b
        self.score_decimal_places: int = cfg.score_decimal_places
        self.default_top_k: int = cfg.top_k
        self.tokenizer = ClinicalTokenizer(acronyms=acronyms, synonyms=synonyms)
        self.all_chunks: tuple[ProtocolChunk, ...] = tuple(chunks)
        self.corpus_hash: str = compute_corpus_hash(chunks)
        self.index_version: str = "2.0.0"
        self.backend: str = "bm25"
        self.retrieval_context: Any = retrieval_context

        self.parents_by_id: dict[str, ProtocolChunk] = {
            c.chunk_id: c for c in self.all_chunks if c.parent_id is None
        }
        parents_with_children: set[str] = {
            c.parent_id for c in self.all_chunks if c.parent_id is not None
        }

        self.chunks_by_population: dict[str, list[ProtocolChunk]] = {}
        self.index_by_population: dict[str, list[int]] = {}
        self._stats_by_population: dict[str, _PopulationBM25Stats] = {}

        for idx, chunk in enumerate(self.all_chunks):
            pop = chunk.population.lower().strip()
            self.index_by_population.setdefault(pop, []).append(idx)
            # Deduplicate parent vs child: index atomic child nodes when children exist
            if chunk.parent_id is None and chunk.chunk_id in parents_with_children:
                continue
            self.chunks_by_population.setdefault(pop, []).append(chunk)

        for pop, pop_chunks in self.chunks_by_population.items():
            self._stats_by_population[pop] = _PopulationBM25Stats(pop_chunks, self.tokenizer)

    def known_syndromes(self, population: str | None = None) -> set[str]:
        """Return set of syndromes present in the index (optionally scoped to population)."""
        if population is not None:
            pop_key = population.lower().strip()
            return {c.syndrome.lower().strip() for c in self.chunks_by_population.get(pop_key, [])}
        return {c.syndrome.lower().strip() for c in self.all_chunks}

    def expand_parents(self, chunks: list[ProtocolChunk]) -> list[ProtocolChunk]:
        """Attach the parent ProtocolChunk once for each distinct parent_id in chunks."""
        seen_parents: set[str] = set()
        parents: list[ProtocolChunk] = []
        for chunk in chunks:
            pid = chunk.parent_id or chunk.chunk_id
            if pid not in seen_parents and pid in self.parents_by_id:
                seen_parents.add(pid)
                parents.append(self.parents_by_id[pid])
        return parents

    def _score_doc_in_stats(
        self,
        stats: _PopulationBM25Stats,
        local_idx: int,
        query_tokens: list[str],
    ) -> tuple[float, dict[str, float]]:
        """Compute pure-Python float BM25 score and per-term breakdown for a chunk."""
        tf_map = stats.doc_term_freqs[local_idx]
        dl = float(stats.doc_lengths[local_idx])
        norm_denom_base = self.k1 * (1.0 - self.b + self.b * (dl / stats.avgdl))
        total_score = 0.0
        term_contributions: dict[str, float] = {}
        for token in query_tokens:
            tf = float(tf_map.get(token, 0))
            if tf <= 0.0:
                continue
            idf = stats.idf.get(token, 0.0)
            contrib = float(idf * ((tf * (self.k1 + 1.0)) / (tf + norm_denom_base)))
            total_score += contrib
            term_contributions[token] = round(
                term_contributions.get(token, 0.0) + contrib,
                self.score_decimal_places,
            )
        return float(total_score), term_contributions

    def search(
        self,
        query: str,
        population: str,
        top_k: int | None = None,
        syndrome: str | None = None,
    ) -> list[tuple[ProtocolChunk, float]]:
        """Search the index for a query within a mandatory population and optional syndrome."""
        eff_top_k = top_k if top_k is not None else self.default_top_k

        pop_key = population.lower().strip()
        if pop_key not in self._stats_by_population:
            return []

        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return []

        stats = self._stats_by_population[pop_key]
        syn_filter = syndrome.lower().strip() if syndrome else None
        candidate_indices = (
            stats.indices_by_syndrome.get(syn_filter, [])
            if syn_filter is not None
            else range(len(stats.chunks))
        )

        scored_chunks: list[tuple[ProtocolChunk, float]] = []
        for local_idx in candidate_indices:
            chunk = stats.chunks[local_idx]
            score, _ = self._score_doc_in_stats(stats, local_idx, query_tokens)
            scored_chunks.append((chunk, float(score)))

        scored_chunks.sort(key=lambda x: (-x[1], x[0].chunk_id))
        return scored_chunks[:eff_top_k]

    def explain_search(
        self,
        query: str,
        population: str,
        top_k: int | None = None,
        syndrome: str | None = None,
    ) -> dict[str, Any]:
        """Return detailed BM25 term contributions, tokens, and filter trace for inspection."""
        eff_top_k = top_k if top_k is not None else self.default_top_k
        pop_key = population.lower().strip()
        query_tokens = self.tokenizer.tokenize(query)
        syn_filter = syndrome.lower().strip() if syndrome else None

        if pop_key not in self._stats_by_population or not query_tokens:
            return {
                "query": query,
                "query_tokens": query_tokens,
                "population": pop_key,
                "syndrome_filter": syn_filter,
                "results": [],
            }

        stats = self._stats_by_population[pop_key]
        candidate_indices = (
            stats.indices_by_syndrome.get(syn_filter, [])
            if syn_filter is not None
            else range(len(stats.chunks))
        )
        explained: list[dict[str, Any]] = []
        for local_idx in candidate_indices:
            chunk = stats.chunks[local_idx]
            score, contribs = self._score_doc_in_stats(stats, local_idx, query_tokens)
            explained.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "parent_id": chunk.parent_id,
                    "syndrome": chunk.syndrome,
                    "score": round(float(score), self.score_decimal_places),
                    "term_contributions": contribs,
                }
            )

        explained.sort(key=lambda x: (-float(x["score"]), str(x["chunk_id"])))
        return {
            "query": query,
            "query_tokens": query_tokens,
            "population": pop_key,
            "syndrome_filter": syn_filter,
            "corpus_hash": self.corpus_hash,
            "index_version": self.index_version,
            "results": explained[:eff_top_k],
        }
