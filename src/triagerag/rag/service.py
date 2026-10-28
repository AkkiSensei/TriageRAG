"""Unified, thread-safe RetrievalService factory for API, CLI, UI, Orchestrator, and Eval.

Safety Properties (RAG-12, RAG-13, Rule R12):
1. Single construction site for index, acronyms, synonyms, manifest, and calibrated config.
2. Thread-safe caching with explicit reload() invalidation (replaces module-global _INDEX).
3. Guarantees 100% parity between evaluation benchmarks and production surfaces.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from triagerag.config import get_data_dir
from triagerag.contracts.schemas import Patient, RetrievalReport
from triagerag.rag.abstain import RetrievalConfig, load_retrieval_config
from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.index import BM25ClinicalIndex, Retriever, load_default_acronyms
from triagerag.rag.ingest import (
    CorpusManifest,
    IngestReport,
    ingest_protocols_with_report,
    load_corpus_manifest,
)
from triagerag.rag.retrieve import (
    build_retrieval_query,
    normalize_syndrome,
    retrieve_protocol_chunks,
)

_SERVICE_LOCK = threading.RLock()
_SERVICE_CACHE: dict[tuple[str, str], RetrievalService] = {}


class RetrievalService:
    """Immutable, versioned retrieval service shared across all TriageRAG surfaces."""

    def __init__(
        self,
        data_dir: Path,
        ingest_report: IngestReport,
        manifest: CorpusManifest,
        config: RetrievalConfig,
        index: Retriever,
    ) -> None:
        self.data_dir: Path = data_dir
        self.ingest_report: IngestReport = ingest_report
        self.manifest: CorpusManifest = manifest
        self.config: RetrievalConfig = config
        self.index: Retriever = index
        self.corpus_hash: str = ingest_report.corpus_hash
        self.index_version: str = index.index_version
        self.config_hash: str = config.config_hash

    @classmethod
    def build(cls, data_dir: Path | None = None, backend: str = "bm25") -> RetrievalService:
        """Construct a fresh RetrievalService instance from disk."""
        target_dir = (data_dir or get_data_dir()).resolve()
        ingest_report = ingest_protocols_with_report(target_dir, strict_unparsed=True)
        manifest = load_corpus_manifest(target_dir)
        config = load_retrieval_config(target_dir)
        acronyms = load_default_acronyms(target_dir)

        if backend == "bm25":
            index: Retriever = BM25ClinicalIndex(ingest_report.chunks, acronyms=acronyms)
        else:
            from triagerag.rag.hybrid import build_retriever_backend

            index = build_retriever_backend(
                backend=backend,
                chunks=ingest_report.chunks,
                acronyms=acronyms,
            )

        return cls(
            data_dir=target_dir,
            ingest_report=ingest_report,
            manifest=manifest,
            config=config,
            index=index,
        )

    @classmethod
    def create_default(
        cls,
        data_dir: Path | None = None,
        backend: str = "bm25",
    ) -> RetrievalService:
        """Return a thread-safe cached RetrievalService for the given data_dir and backend."""
        target_dir = (data_dir or get_data_dir()).resolve()
        key = (str(target_dir), backend.lower().strip())
        with _SERVICE_LOCK:
            if key not in _SERVICE_CACHE:
                _SERVICE_CACHE[key] = cls.build(target_dir, backend=backend)
            return _SERVICE_CACHE[key]

    @classmethod
    def reload(
        cls,
        data_dir: Path | None = None,
        backend: str = "bm25",
    ) -> RetrievalService:
        """Explicitly rebuild and replace the cached RetrievalService instance."""
        target_dir = (data_dir or get_data_dir()).resolve()
        key = (str(target_dir), backend.lower().strip())
        with _SERVICE_LOCK:
            fresh = cls.build(target_dir, backend=backend)
            _SERVICE_CACHE[key] = fresh
            return fresh

    def list_chunks(self) -> list[ProtocolChunk]:
        """Return all ingested protocol chunks (parents and children)."""
        return list(self.ingest_report.chunks)

    def retrieve(
        self,
        patient: Patient,
        threshold: float | None = None,
        top_k: int | None = None,
    ) -> RetrievalReport:
        """Execute full retrieval and abstention pipeline for a structured patient."""
        eff_threshold = threshold if threshold is not None else self.config.calibrated_threshold
        eff_top_k = top_k if top_k is not None else self.config.top_k
        return retrieve_protocol_chunks(
            patient=patient,
            index=self.index,
            threshold=eff_threshold,
            top_k=eff_top_k,
        )

    def explain(self, patient: Patient, top_k: int | None = None) -> dict[str, Any]:
        """Produce a complete diagnostic trace of query building, filters, and BM25 scoring."""
        pop = str(patient.age.population_category).lower().strip()
        query_str, flags = build_retrieval_query(patient)
        norm_syndrome = normalize_syndrome(patient.suspected_syndrome, self.data_dir)
        report = self.retrieve(patient, top_k=top_k)

        bm25_explain: dict[str, Any] = {}
        if isinstance(self.index, BM25ClinicalIndex):
            bm25_explain = self.index.explain_search(
                query=query_str,
                population=pop,
                top_k=top_k,
                syndrome=norm_syndrome,
            )

        return {
            "query": query_str,
            "vitals_derived_flags": flags,
            "population": pop,
            "raw_syndrome": patient.suspected_syndrome,
            "normalized_syndrome": norm_syndrome,
            "abstained": report.abstained,
            "abstain_code": report.abstain_code.value,
            "reason": report.reason,
            "corpus_hash": self.corpus_hash,
            "index_version": self.index_version,
            "config_hash": self.config_hash,
            "bm25_trace": bm25_explain,
            "retrieved_chunks": [c.model_dump(mode="json") for c in report.chunks],
        }
