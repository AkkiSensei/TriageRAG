"""Unit tests for AUB Phase 1 Task T1.5: Remove Fail-Open Citation Verification (AUB-GRD-02).

Safety Property (T1.5 / AUB-GRD-02):
1. Ingest failures during child-node detection must fail closed (CITATION_UNVERIFIED).
2. Never silently pass via `except Exception: pass`.
3. Log structured error reason when corpus ingestion fails.
"""

from __future__ import annotations

from unittest.mock import patch

from triagerag.config import get_data_dir
from triagerag.contracts.enums import ActionType, StepStatus
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import PlanDraft, PlanStepDraft, RetrievedChunk, SpanCitation
from triagerag.engine.registry import load_registry
from triagerag.verify.citations import verify_citation
from triagerag.verify.plan_verifier import verify_plan


def _make_parent_chunk(
    chunk_id: str = "DOC_01",
    text: str = "Administer epinephrine IM.",
) -> RetrievedChunk:
    return RetrievedChunk(
        doc_id="DOC_01",
        section="Management",
        chunk_id=chunk_id,
        parent_id=None,
        text=text,
        population="adult",
        syndrome="anaphylaxis",
    )


def test_parent_citation_rejected_when_ingest_fails() -> None:
    """When corpus ingestion fails during child node lookup, fail closed and reject (T1.5)."""
    parent_chunk = _make_parent_chunk("DOC_01")
    citation = SpanCitation(
        doc_id="DOC_01",
        chunk_id="DOC_01",
        section="Management",
        quoted_span="Administer epinephrine IM.",
    )

    with patch(
        "triagerag.rag.ingest.ingest_protocols",
        side_effect=RuntimeError("Disk failure reading protocol directory"),
    ):
        is_valid, score, reason = verify_citation(
            citation=citation,
            retrieved_chunks=[parent_chunk],
            narrative_instruction="Administer epinephrine IM immediately.",
        )

    assert is_valid is False
    assert score == 0.0
    assert reason is not None
    assert "Fail closed: corpus ingestion failed while verifying child nodes" in reason
    assert "Disk failure reading protocol directory" in reason


def test_plan_verifier_marks_step_unverified_on_ingest_failure() -> None:
    """End-to-end plan verification marks step CITATION_UNVERIFIED on ingestion error."""
    parent_chunk = _make_parent_chunk("DOC_01")
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        narrative_instruction="Administer epinephrine IM.",
        citations=[
            SpanCitation(
                doc_id="DOC_01",
                chunk_id="DOC_01",
                section="Management",
                quoted_span="Administer epinephrine IM.",
            )
        ],
    )

    patient, _ = get_preloaded_scenario("CLEAN")
    draft = PlanDraft(
        matched_protocol_title="Emergency Management",
        steps=[step],
    )
    registry = load_registry(get_data_dir())

    with patch(
        "triagerag.rag.ingest.ingest_protocols",
        side_effect=OSError("Corrupted synthetic protocol file"),
    ):
        v_steps, _, _, _ = verify_plan(
            patient=patient,
            draft=draft,
            baseline_alerts=[],
            retrieved_chunks=[parent_chunk],
            registry=registry,
        )

    assert len(v_steps) == 1
    verified_step = v_steps[0]
    assert verified_step.status == StepStatus.CITATION_UNVERIFIED
    assert verified_step.citation_verified is False
    assert any(
        "Fail closed: corpus ingestion failed while verifying child nodes" in r
        for r in verified_step.rejection_reasons
    )
