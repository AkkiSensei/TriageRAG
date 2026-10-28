"""Reproduction probes for RAG postmortem findings (WP0 / Appendix A).

Safety Properties Tested:
1. RAG-01: Unknown syndrome with abnormal vitals must abstain with UNKNOWN_SYNDROME.
2. RAG-01: Known syndrome is a hard filter; never returns chunks from unrelated syndromes.
3. RAG-03: Adult vitals thresholds are never applied to paediatric or neonate populations.
4. RAG-05: Trailing non-decision sections (e.g. '## Notes') are never absorbed into the last node.
5. RAG-05: Decision nodes lacking a THEN clause are reported as unparsed, never silently dropped.
6. RAG-04: Frontmatter missing the 'synthetic' boolean flag is rejected, never defaulted to True.
7. RAG-02: Plan steps administering/withholding a drug must cite a child node that supports
   that drug and action cue (prevents citation laundering).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from triagerag.config import get_data_dir
from triagerag.contracts.enums import ActionType, AgeUnit, DoseUnit, Route, StepStatus
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    Patient,
    PlanDraft,
    PlanStepDraft,
    RetrievedChunk,
    SpanCitation,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.rag.chunking import chunk_protocol_markdown
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import derive_vitals_flags, retrieve_protocol_chunks
from triagerag.verify.plan_verifier import verify_plan


def _build_index() -> BM25ClinicalIndex:
    data_dir = get_data_dir()
    chunks = ingest_protocols(data_dir)
    return BM25ClinicalIndex(chunks)


def test_unknown_syndrome_with_flags_abstains() -> None:
    """RAG-01: Patient with unknown syndrome ('kidney_stone') and abnormal vitals must abstain."""
    index = _build_index()
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("45"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
            heart_rate_bpm=Measured[int](value=130, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="kidney_stone",
    )

    report = retrieve_protocol_chunks(patient, index)
    assert report.abstained is True
    assert report.chunks == []
    assert getattr(report, "abstain_code", None) == "UNKNOWN_SYNDROME"


def test_known_syndrome_never_returns_other_syndrome_chunks() -> None:
    """RAG-01: Known syndrome 'anaphylaxis' with hypotension only returns anaphylaxis chunks."""
    index = _build_index()
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("35"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
    )

    report = retrieve_protocol_chunks(patient, index)
    assert report.abstained is False
    assert len(report.chunks) > 0
    assert all(c.syndrome == "anaphylaxis" for c in report.chunks), (
        f"Cross-syndrome contamination: {[c.syndrome for c in report.chunks]}"
    )


def test_no_adult_thresholds_applied_to_paediatric() -> None:
    """RAG-03: A 4-year-old with HR 120 and RR 30 must not trigger adult tachycardia/tachypnea."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    paed_patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("4"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("16.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=120, source="measured"),
            respiratory_rate_bpm=Measured[int](value=30, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="paediatric_sepsis",
    )

    flags = derive_vitals_flags(paed_patient)
    assert "tachycardia" not in flags, f"Adult HR threshold leaked to paediatric: {flags}"
    assert "tachypnea" not in flags, f"Adult RR threshold leaked to paediatric: {flags}"


TRAILING_SECTION_MD = """---
doc_id: "X"
section: "S"
population: "adult"
syndrome: "chest_pain"
chunk_id: "X_1"
synthetic: true
---
1. IF condition a is observed:
   THEN perform action b.
2. IF condition c is observed:
   THEN perform action d.

## Notes
unrelated trailing text
"""


def test_trailing_section_not_absorbed_into_last_node() -> None:
    """RAG-05: Trailing non-decision section ('## Notes') must not bleed into the last node."""
    chunks = chunk_protocol_markdown(TRAILING_SECTION_MD)
    child_nodes = [c for c in chunks if c.parent_id is not None]
    assert len(child_nodes) == 2
    last_node = child_nodes[-1]
    assert "## Notes" not in last_node.text
    assert "unrelated trailing text" not in last_node.text


DROPPED_NODE_MD = """---
doc_id: "X"
section: "S"
population: "adult"
syndrome: "chest_pain"
chunk_id: "X_1"
synthetic: true
---
1. IF condition a is observed:
   THEN perform action b.
2. IF condition c has no then clause at all:
   Just some dangling text without action keyword.
"""


def test_node_without_then_is_reported_not_silently_dropped() -> None:
    """RAG-05: A decision node with IF but no THEN must be reported as unparsed, not dropped."""
    chunks = chunk_protocol_markdown(DROPPED_NODE_MD)
    parent = chunks[0]
    unparsed = getattr(parent, "unparsed_lines", ())
    assert len(unparsed) > 0, "Malformed IF node without THEN was silently dropped!"
    assert any("condition c" in line for line in unparsed)


MISSING_SYNTHETIC_MD = """---
doc_id: "X"
section: "S"
population: "adult"
syndrome: "chest_pain"
chunk_id: "X_1"
---
1. IF condition a is observed:
   THEN perform action b.
"""


def test_missing_synthetic_flag_rejected() -> None:
    """RAG-04: Protocol frontmatter omitting 'synthetic' must be rejected, not defaulted True."""
    with pytest.raises(ValueError, match="synthetic"):
        chunk_protocol_markdown(MISSING_SYNTHETIC_MD)


def test_step_drug_must_appear_in_cited_chunk() -> None:
    """RAG-02: Administering nitroglycerin while citing a hypoglycemia/dextrose chunk must fail."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("50"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=90, source="measured"),
            systolic_bp_mmhg=Measured[int](value=130, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
    )

    unrelated_chunk = RetrievedChunk(
        doc_id="EMERG_HYPOGLYCEMIA",
        section="Acute Metabolic Screening",
        chunk_id="HYPOGLYCEMIA_01_NODE_1",
        text=(
            "1. IF the adult patient presents with acute neuroglycopenic symptoms and "
            "confirmed capillary hypoglycemia:\n"
            "   THEN administer intravenous dextrose immediately via secure vascular access."
        ),
        population="adult",
        syndrome="hypoglycemia",
    )

    draft = PlanDraft(
        matched_protocol_title="Acute Metabolic Screening",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                narrative_instruction=(
                    "Administer sublingual vasodilator immediately via secure access"
                ),
                drug_id="nitroglycerin",
                requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
                route=Route.sublingual,
                citations=[
                    SpanCitation(
                        doc_id="EMERG_HYPOGLYCEMIA",
                        section="Acute Metabolic Screening",
                        chunk_id="HYPOGLYCEMIA_01_NODE_1",
                        quoted_span="administer intravenous dextrose immediately",
                    )
                ],
            )
        ],
    )

    verified_steps, _, _, _ = verify_plan(
        patient=patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[unrelated_chunk],
        registry=registry,
    )

    assert len(verified_steps) == 1
    assert verified_steps[0].status == StepStatus.CITATION_UNVERIFIED
    assert verified_steps[0].citation_verified is False
