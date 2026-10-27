"""Edge case testing for protocol ingestion, chunking, and BM25 retrieval.

Safety Properties (Rule R5, R12):
1. Empty index or missing population gracefully abstains without raising unhandled exceptions.
2. Case, punctuation, and acronym queries parse safely and deterministically.
3. Chunks with irregular syntax (IF without THEN, missing headings) are parsed without crash.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from triagerag.config import get_data_dir
from triagerag.contracts.enums import AgeUnit
from triagerag.contracts.schemas import Age, Patient, Vitals
from triagerag.rag.chunking import ProtocolChunk, chunk_protocol_markdown
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import retrieve_protocol_chunks


def _make_dummy_patient(population: str = "adult", syndrome: str = "chest_pain") -> Patient:
    from datetime import UTC, datetime

    age_val = Decimal("35") if population == "adult" else Decimal("5")
    from triagerag.contracts.schemas import Measured

    return Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=age_val, unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=Vitals(),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=syndrome,
        chief_complaint_untrusted="Test complaint",
    )


def test_empty_index_abstains_gracefully() -> None:
    """Empty index returns an abstained report without raising."""
    empty_index = BM25ClinicalIndex([])
    patient = _make_dummy_patient()

    report = retrieve_protocol_chunks(patient, empty_index)
    assert report.abstained is True
    assert report.chunks == []
    assert report.reason is not None
    reason_lower = report.reason.lower()
    assert "abstained" in reason_lower or "empty" in reason_lower or "no" in reason_lower


def test_missing_population_abstains_with_clear_reason() -> None:
    """Querying a population category with no indexed protocols abstains."""
    chunk = ProtocolChunk(
        doc_id="DOC_PAED",
        section="Paediatric Only",
        chunk_id="C1",
        text="paediatric protocol text",
        population="paediatric",
        syndrome="sepsis",
    )
    index = BM25ClinicalIndex([chunk])

    adult_patient = _make_dummy_patient(population="adult", syndrome="sepsis")
    report = retrieve_protocol_chunks(adult_patient, index)

    assert report.abstained is True
    assert report.chunks == []
    assert report.reason is not None
    assert "population" in report.reason.lower()


def test_punctuation_and_case_variant_queries() -> None:
    """Case variations, leading whitespace, and punctuation do not crash search."""
    data_dir = get_data_dir()
    index = BM25ClinicalIndex(ingest_protocols(data_dir))

    for variant in ["  CHEST PAIN!!! ", "chest-pain...", "ANAPHYLAXIS???", "\tSEVERE_ASTHMA\n"]:
        patient = _make_dummy_patient(syndrome=variant)
        report = retrieve_protocol_chunks(patient, index)
        # Should execute deterministically without exception
        assert report is not None
        assert isinstance(report.abstained, bool)


def test_chunking_with_irregular_if_then_syntax() -> None:
    """Markdown protocols with irregular syntax (IF without THEN, arbitrary text) chunk safely."""
    irregular_md = """---
doc_id: "SYNTHETIC_TEST_01"
section: "Irregular Protocol"
population: "adult"
syndrome: "chest_pain"
chunk_id: "SYNTH_01"
synthetic: true
---

# Irregular Protocol

1. IF patient has acute severe crushing substernal chest discomfort:
   There is no THEN clause on this line, only general instructions.
2. An unnumbered irregular clinical recommendation with no IF.
"""
    chunks = chunk_protocol_markdown(irregular_md, Path("test_file.md"))
    assert len(chunks) > 0
    assert chunks[0].doc_id == "SYNTHETIC_TEST_01"
    assert chunks[0].syndrome == "chest_pain"
    assert "irregular" in chunks[0].text.lower()
