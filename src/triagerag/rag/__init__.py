"""TriageRAG retrieval-augmented generation (RAG) subsystem."""

from triagerag.rag.abstain import evaluate_abstention
from triagerag.rag.chunking import ProtocolChunk, chunk_protocol_markdown
from triagerag.rag.index import BM25ClinicalIndex, ClinicalTokenizer
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import (
    build_retrieval_query,
    derive_vitals_flags,
    retrieve_protocol_chunks,
)

__all__ = [
    "BM25ClinicalIndex",
    "ClinicalTokenizer",
    "ProtocolChunk",
    "build_retrieval_query",
    "chunk_protocol_markdown",
    "derive_vitals_flags",
    "evaluate_abstention",
    "ingest_protocols",
    "retrieve_protocol_chunks",
]
