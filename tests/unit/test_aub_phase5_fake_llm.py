"""Unit tests for Phase 5 Task T5.4: Retrieval-Dependent FakeLLM Profiles.

Safety Property (AUB-GRD-01, Rule R1, Task T5.4):
1. RANKED_CHOICE: Dynamically drafts from top retrieved ranking rather than
   hardcoded syndrome scripts.
2. WRONG_BUT_MATCHING_CLAUSE: Selects verbatim span from a node whose preconditions are unmet,
   exercising the NOT_APPLICABLE verifier refusal path.
3. QUALIFIER_DROP: Selects a valid qualified node but drops the required qualifier,
   exercising the QUALIFIER_DROPPED / CITATION_UNVERIFIED verifier refusal path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.contracts.enums import ActionType, PopulationCategory, StepStatus
from triagerag.contracts.schemas import (
    Age,
    Measured,
    Patient,
    PlanContext,
    RetrievedChunk,
    Vitals,
)
from triagerag.engine.registry import load_registry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.verify.plan_verifier import verify_plan


def _build_normotensive_test_patient() -> Patient:
    """Normotensive patient with normal vital signs."""
    return Patient(
        assessed_at=datetime.now(UTC),
        age=Age(value=Decimal("40"), unit="years"),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("60.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=75, source="measured"),
            systolic_bp_mmhg=Measured[int](value=125, source="measured"),  # Normotensive
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
        ),
        medications=[],
        allergies=[],
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_nkda",
        suspected_syndrome="anaphylaxis",
    )


def _build_hypotensive_test_patient() -> Patient:
    """Hypotensive shock patient meeting low_systolic_bp predicate (< 90 mmHg)."""
    return Patient(
        assessed_at=datetime.now(UTC),
        age=Age(value=Decimal("40"), unit="years"),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("60.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=115, source="measured"),
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),  # Hypotensive shock < 90
            respiratory_rate_bpm=Measured[int](value=22, source="measured"),
            spo2_percent=Measured[int](value=94, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
        ),
        medications=[],
        allergies=[],
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_nkda",
        suspected_syndrome="anaphylaxis",
    )


def _build_test_chunks() -> list[RetrievedChunk]:
    """Test chunks including first-line and repeat/qualified nodes."""
    chunk1 = RetrievedChunk(
        doc_id="PROTO_SYN_001",
        section="Anaphylaxis Immediate Management",
        chunk_id="ANAPHYLAXIS_01_NODE_1",
        parent_id="ANAPHYLAXIS_01",
        text=(
            "1. IF patient presents with acute respiratory distress or laryngeal edema:\n"
            "   THEN administer intramuscular epinephrine into the anterolateral mid-thigh."
        ),
        population="adult",
        score=Decimal("0.98"),
        syndrome="anaphylaxis",
    )
    chunk3 = RetrievedChunk(
        doc_id="PROTO_SYN_001",
        section="Anaphylaxis Refractory Management",
        chunk_id="ANAPHYLAXIS_01_NODE_3",
        parent_id="ANAPHYLAXIS_01",
        text=(
            "3. IF signs of systemic hypoperfusion, compensatory tachycardia, or refractory shock "
            "continue after initial therapy:\n"
            "   THEN repeat administration of intramuscular epinephrine and establish wide-bore "
            "vascular access."
        ),
        population="adult",
        score=Decimal("0.85"),
        syndrome="anaphylaxis",
    )
    return [chunk1, chunk3]


class TestRetrievalDependentFakeLLMProfiles:
    """Tests asserting distinct verifier refusal or acceptance paths across new profiles."""

    def test_ranked_choice_profile_drafts_from_top_chunk_and_verifies(self) -> None:
        """RANKED_CHOICE drafts from #1 retrieved chunk and passes verification."""
        patient = _build_hypotensive_test_patient()
        registry = load_registry()
        chunks = _build_test_chunks()

        context = PlanContext(
            population_category=PopulationCategory.adult,
            retrieved_chunks=chunks,
            allowed_drug_ids=["epinephrine"],
        )

        llm = FakeLLM(profile=FakeLLMProfile.RANKED_CHOICE)
        draft = llm.draft_plan(context)

        assert len(draft.steps) == 1
        assert draft.steps[0].citations[0].chunk_id == "ANAPHYLAXIS_01_NODE_1"
        assert draft.steps[0].action_type == ActionType.administer

        verified_steps, _, _, _ = verify_plan(
            patient=patient,
            draft=draft,
            baseline_alerts=[],
            retrieved_chunks=chunks,
            registry=registry,
        )

        assert len(verified_steps) == 1
        assert verified_steps[0].status == StepStatus.APPROVED
        assert verified_steps[0].citation_verified is True

    def test_wrong_but_matching_clause_triggers_not_applicable(self) -> None:
        """WRONG_BUT_MATCHING_CLAUSE cites an inapplicable clause, triggering NOT_APPLICABLE."""
        patient = _build_normotensive_test_patient()
        registry = load_registry()
        chunks = _build_test_chunks()

        context = PlanContext(
            population_category=PopulationCategory.adult,
            retrieved_chunks=chunks,
            allowed_drug_ids=["epinephrine"],
        )

        llm = FakeLLM(profile=FakeLLMProfile.WRONG_BUT_MATCHING_CLAUSE)
        draft = llm.draft_plan(context)

        assert len(draft.steps) == 1
        # Cites NODE_3 (which requires low_systolic_bp)
        assert draft.steps[0].citations[0].chunk_id == "ANAPHYLAXIS_01_NODE_3"

        verified_steps, _, _, _ = verify_plan(
            patient=patient,
            draft=draft,
            baseline_alerts=[],
            retrieved_chunks=chunks,
            registry=registry,
        )

        assert len(verified_steps) == 1
        # Refusal path: NOT_APPLICABLE
        assert verified_steps[0].status == StepStatus.NOT_APPLICABLE
        assert any("not applicable" in r.lower() for r in verified_steps[0].rejection_reasons)

    def test_qualifier_drop_triggers_citation_unverified(self) -> None:
        """QUALIFIER_DROP cites a qualified clause but omits qualifier, triggering refusal."""
        patient = _build_hypotensive_test_patient()
        registry = load_registry()
        chunks = _build_test_chunks()

        context = PlanContext(
            population_category=PopulationCategory.adult,
            retrieved_chunks=chunks,
            allowed_drug_ids=["epinephrine"],
        )

        llm = FakeLLM(profile=FakeLLMProfile.QUALIFIER_DROP)
        draft = llm.draft_plan(context)

        assert len(draft.steps) == 1
        # Cites qualified chunk (NODE_3 with repeat), but narrative instruction dropped 'repeat'
        assert "repeat" not in draft.steps[0].narrative_instruction.lower()

        verified_steps, _, _, _ = verify_plan(
            patient=patient,
            draft=draft,
            baseline_alerts=[],
            retrieved_chunks=chunks,
            registry=registry,
        )

        assert len(verified_steps) == 1
        # Refusal path: CITATION_UNVERIFIED due to QUALIFIER_DROPPED
        assert verified_steps[0].status == StepStatus.CITATION_UNVERIFIED
        assert verified_steps[0].citation_verified is False
        assert any("QUALIFIER_DROPPED" in r for r in verified_steps[0].rejection_reasons)
