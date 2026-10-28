"""Unit tests for WP3: Per-population vitals flags, syndrome vocabulary, and hard syndrome filter.

Safety Properties (RAG-01, RAG-03, Rules R2, R3):
1. Vitals flags are loaded per population from data/retrieval/vitals_flags.yaml with Provenance.
2. Unsourced thresholds (status: NEEDS_SOURCE, threshold: null) fail closed and emit no flag.
3. Neonate and paediatric patients never fall back to adult vitals thresholds.
4. AST scan confirms zero clinical numeric literals exist anywhere in src/triagerag/rag/*.py.
5. Known suspected_syndrome acts as a hard metadata filter; unknown syndrome abstains with
   AbstainCode.UNKNOWN_SYNDROME.
6. Missing suspected_syndrome requires calibrated score + top-1/top-2 syndrome margin and sets
   AbstainCode.SYNDROME_INFERRED when not abstaining.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from decimal import Decimal

from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import AbstainCode, AgeUnit
from triagerag.contracts.schemas import Age, Measured, Patient, Vitals
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import derive_vitals_flags, retrieve_protocol_chunks

_ALLOWED_STRUCTURAL_NUMBERS: set[int | float] = {-1, 0, 1, 2, 0.5}


def test_ast_no_numeric_clinical_literals_in_rag() -> None:
    """RAG-03 Gate: AST scan of src/triagerag/rag/*.py forbids hardcoded clinical thresholds."""
    rag_dir = get_repo_root() / "src" / "triagerag" / "rag"
    py_files = sorted(rag_dir.glob("*.py"))
    assert len(py_files) >= 5

    violations: list[str] = []
    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if isinstance(node.value, bool):
                    continue
                if node.value not in _ALLOWED_STRUCTURAL_NUMBERS:
                    violations.append(f"{py_file.name}:{node.lineno} literal {node.value!r}")

    assert violations == [], f"Found hardcoded numeric literals in rag/: {violations}"


def test_needs_source_flag_emits_nothing() -> None:
    """RAG-03: Thresholds marked NEEDS_SOURCE (e.g. paediatric SBP, neonate HR) emit no flags."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)

    # Paediatric SBP hypotension threshold is NEEDS_SOURCE -> must not emit 'hypotension'
    paed_patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("5"), unit=AgeUnit.years),
        sex="female",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("18.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
            heart_rate_bpm=Measured[int](value=105, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
    )
    paed_flags = derive_vitals_flags(paed_patient)
    assert "hypotension" not in paed_flags
    assert "tachycardia" not in paed_flags

    # Neonate thresholds are all NEEDS_SOURCE -> must emit zero numeric vitals flags
    neonate_patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("10"), unit=AgeUnit.days),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("3.2"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=65, source="measured"),
            heart_rate_bpm=Measured[int](value=155, source="measured"),
            respiratory_rate_bpm=Measured[int](value=45, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
    )
    neonate_flags = derive_vitals_flags(neonate_patient)
    assert neonate_flags == []


def test_no_syndrome_requires_margin() -> None:
    """RAG-01: When suspected_syndrome is absent, ambiguous cross-syndrome hits abstain."""
    data_dir = get_data_dir()
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)

    # Adult patient with only hypotension (matches both chest_pain and anaphylaxis closely)
    ambiguous_patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("50"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=None,
    )
    report = retrieve_protocol_chunks(ambiguous_patient, index)
    assert report.abstained is True
    assert report.abstain_code in (AbstainCode.AMBIGUOUS_MARGIN, AbstainCode.LOW_CONFIDENCE)
