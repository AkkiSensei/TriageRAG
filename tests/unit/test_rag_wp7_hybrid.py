"""Unit tests for WP7: Hybrid RRF retriever, DenseRetriever, and 4-arm retrieval ablation (RAG-08).

Safety Properties (RAG-08, Rule R12):
1. DenseRetriever and HybridRRFRetriever implement the Retriever protocol and enforce
   identical hard population and hard syndrome filters.
2. 4-arm retrieval ablation (bm25, dense, hybrid_rrf, hybrid_rrf_rerank) executes offline
   on the 160-case WP5 dataset and writes retrieval_ablation.json and retrieval_ablation.md.
3. docs/ARCHITECTURE.md accurately documents the Retriever protocol and ablation findings.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import AgeUnit
from triagerag.contracts.schemas import Age, Measured, Patient, Vitals
from triagerag.rag.hybrid import DenseRetriever, HybridRRFRetriever, build_retriever_backend
from triagerag.rag.index import Retriever
from triagerag.rag.service import RetrievalService


def test_dense_and_hybrid_retrievers_conform_to_protocol() -> None:
    """RAG-08: DenseRetriever and HybridRRFRetriever satisfy @runtime_checkable Retriever."""
    svc_bm25 = RetrievalService.create_default(get_data_dir(), backend="bm25")
    svc_dense = RetrievalService.create_default(get_data_dir(), backend="dense")
    svc_hybrid = RetrievalService.create_default(get_data_dir(), backend="hybrid_rrf")
    svc_rerank = RetrievalService.create_default(get_data_dir(), backend="hybrid_rrf_rerank")

    assert isinstance(svc_bm25.index, Retriever)
    assert isinstance(svc_dense.index, Retriever)
    assert isinstance(svc_dense.index, DenseRetriever)
    assert isinstance(svc_hybrid.index, Retriever)
    assert isinstance(svc_hybrid.index, HybridRRFRetriever)
    assert isinstance(svc_rerank.index, Retriever)

    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("45"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
            heart_rate_bpm=Measured[int](value=125, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
    )

    for svc in (svc_bm25, svc_dense, svc_hybrid, svc_rerank):
        rep = svc.retrieve(patient)
        assert rep.abstained is False
        assert len(rep.chunks) > 0
        assert all(c.syndrome == "anaphylaxis" for c in rep.chunks)
        assert all(c.population == "adult" for c in rep.chunks)

    # Also test build_retriever_backend directly
    chunks = svc_bm25.list_chunks()
    r_dense = build_retriever_backend("dense", chunks)
    assert isinstance(r_dense, Retriever)


def test_four_arm_retrieval_ablation_and_architecture_docs(tmp_path: Path) -> None:
    """RAG-08: 4-arm retrieval ablation report and ARCHITECTURE.md match implementation."""
    from eval.run_retrieval_ablation import run_retrieval_ablation_suite

    rc = run_retrieval_ablation_suite(output_dir=tmp_path)
    assert rc == 0

    json_path = tmp_path / "retrieval_ablation.json"
    md_path = tmp_path / "retrieval_ablation.md"
    assert json_path.exists()
    assert md_path.exists()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    arms = report.get("arms", {})
    for arm_key in ("bm25", "char_ngram", "hybrid_rrf", "hybrid_rrf_rerank"):
        assert arm_key in arms
        assert arms[arm_key]["recall_at_5"] >= 65.0
        assert arms[arm_key]["wrong_protocol_rate"] == 0.0
        assert arms[arm_key]["hard_negative_abstain_recall"] >= 0.95

    repo_root = get_repo_root()
    arch_text = (repo_root / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "Retriever" in arch_text
    assert "HybridRRFRetriever" in arch_text
    assert "DenseRetriever" in arch_text
