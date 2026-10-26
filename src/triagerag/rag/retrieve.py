"""Protocol retrieval orchestrator.

Safety Property (Rules R7, R8, Section 8):
1. Query constructed strictly from structured patient fields:
   suspected_syndrome + vitals-derived flags.
2. chief_complaint_untrusted is never used in query construction.
3. Enforces hard population filtering and score-based abstention.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from triagerag.contracts.enums import Consciousness
from triagerag.contracts.schemas import RetrievalReport, RetrievedChunk
from triagerag.rag.abstain import DEFAULT_MIN_RETRIEVAL_THRESHOLD, evaluate_abstention

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient
    from triagerag.rag.index import BM25ClinicalIndex


def derive_vitals_flags(patient: Patient) -> list[str]:
    """Derive standardized categorical physiological flags from measured vitals.

    Safety: Vitals that are unknown or missing never trigger spurious flags.
    """
    flags: list[str] = []
    v = patient.vitals

    if v.systolic_bp_mmhg.value is not None:
        if v.systolic_bp_mmhg.value < 90:
            flags.append("hypotension")
        elif v.systolic_bp_mmhg.value >= 180:
            flags.append("severe_hypertension")

    if v.heart_rate_bpm.value is not None:
        if v.heart_rate_bpm.value > 100:
            flags.append("tachycardia")
        elif v.heart_rate_bpm.value < 60:
            flags.append("bradycardia")

    if v.respiratory_rate_bpm.value is not None and v.respiratory_rate_bpm.value > 22:
        flags.append("tachypnea")

    if v.spo2_percent.value is not None and v.spo2_percent.value < 92:
        flags.append("hypoxia")

    if v.temperature_c.value is not None:
        if v.temperature_c.value > Decimal("38.0"):
            flags.append("fever")
        elif v.temperature_c.value < Decimal("35.5"):
            flags.append("hypothermia")

    if v.consciousness.value == Consciousness.C:
        flags.append("confusion")
    elif v.consciousness.value in (Consciousness.V, Consciousness.P, Consciousness.U):
        flags.append("depressed_consciousness")

    if v.blood_glucose_mg_dl.value is not None and v.blood_glucose_mg_dl.value < Decimal("70"):
        flags.append("hypoglycemia")

    return flags


def build_retrieval_query(patient: Patient) -> tuple[str, list[str]]:
    """Build a search query from structured clinical attributes.

    Rule R7: chief_complaint_untrusted is explicitly forbidden from query construction.
    """
    flags = derive_vitals_flags(patient)
    query_parts: list[str] = []

    if patient.suspected_syndrome:
        query_parts.append(patient.suspected_syndrome)

    query_parts.extend(flags)
    query_string = " ".join(query_parts).strip()
    return query_string, flags


def retrieve_protocol_chunks(
    patient: Patient,
    index: BM25ClinicalIndex,
    threshold: float = DEFAULT_MIN_RETRIEVAL_THRESHOLD,
    top_k: int = 5,
) -> RetrievalReport:
    """Retrieve verified protocol chunks matching patient population and structured query."""
    pop = str(patient.age.population_category).lower().strip()
    query_str, _ = build_retrieval_query(patient)

    if not query_str:
        return RetrievalReport(
            chunks=[],
            backend=index.backend,
            abstained=True,
            reason="Empty clinical query: no suspected syndrome or abnormal vitals flags",
        )

    pop_available = pop in index.index_by_population
    scored_chunks = index.search(query=query_str, population=pop, top_k=top_k)

    abstained, reason = evaluate_abstention(
        scored_chunks=scored_chunks,
        population=pop,
        population_available=pop_available,
        threshold=threshold,
    )

    if abstained:
        return RetrievalReport(
            chunks=[],
            backend=index.backend,
            abstained=True,
            reason=reason,
        )

    retrieved: list[RetrievedChunk] = []
    for chunk, score in scored_chunks:
        # Normalize BM25 score to positive Decimal for schema compliance
        norm_score = max(Decimal("0.0"), Decimal(str(round(score, 4))))
        retrieved.append(
            RetrievedChunk(
                doc_id=chunk.doc_id,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                population=chunk.population,
                syndrome=chunk.syndrome,
                score=norm_score,
            )
        )

    return RetrievalReport(
        chunks=retrieved,
        backend=index.backend,
        abstained=False,
        reason=None,
    )
