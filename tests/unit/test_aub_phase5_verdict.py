"""Unit and API regression tests for Phase 5 Task T5.3: Verdict Consequences.

Safety Property (AUB-GRD-01, Rule R1, Rule R2, Rule R11, Task T5.3):
1. Normal vitals + anaphylaxis selected must NEVER resolve to CHECKED_CLEAR
   with an APPROVED epinephrine step when citing inapplicable repeat-dose node
   (ANAPHYLAXIS_01_NODE_3).
2. If a step's preconditions are unmet, its status is NOT_APPLICABLE.
3. The verdict lattice fail-closed property guarantees that any NOT_APPLICABLE
   or non-approved step prevents CHECKED_CLEAR, resolving to UNVERIFIED.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from starlette.testclient import TestClient

from triagerag.api.app import app
from triagerag.contracts.enums import ActionType, DoseUnit, Route, StepStatus, Verdict
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    Patient,
    PlanContext,
    PlanDraft,
    PlanStepDraft,
    RetrievedChunk,
    SpanCitation,
    Vitals,
)
from triagerag.engine.registry import load_registry
from triagerag.llm.provider import LLMProvider
from triagerag.orchestrator import run_triage
from triagerag.verify.plan_verifier import verify_plan

client = TestClient(app)


def _build_normotensive_anaphylaxis_patient() -> Patient:
    """Normotensive patient presenting with allergic reaction / anaphylaxis complaint."""
    return Patient(
        assessed_at=datetime.now(UTC),
        age=Age(value=Decimal("30"), unit="years"),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=78, source="measured"),
            systolic_bp_mmhg=Measured[int](value=125, source="measured"),  # Normotensive
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=99, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.7"), source="measured"),
        ),
        medications=[],
        allergies=[],
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_nkda",
        suspected_syndrome="anaphylaxis",
    )


def _build_hypotensive_anaphylaxis_patient() -> Patient:
    """Hypotensive shock patient with anaphylaxis."""
    return Patient(
        assessed_at=datetime.now(UTC),
        age=Age(value=Decimal("30"), unit="years"),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=120, source="measured"),
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),  # Hypotensive shock < 90
            respiratory_rate_bpm=Measured[int](value=24, source="measured"),
            spo2_percent=Measured[int](value=92, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.7"), source="measured"),
        ),
        medications=[],
        allergies=[],
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_nkda",
        suspected_syndrome="anaphylaxis",
    )


class TestVerdictApplicabilityConsequences:
    """Tests establishing verdict lattice safety when citing conditional protocol nodes."""

    def test_normotensive_anaphylaxis_node3_never_checked_clear(self) -> None:
        """AUB-GRD-01 Acceptance: Normotensive anaphylaxis citing repeat node cannot be CLEAR."""
        patient = _build_normotensive_anaphylaxis_patient()
        registry = load_registry()

        repeat_node_text = (
            "3. IF signs of systemic hypoperfusion, compensatory tachycardia, or refractory shock "
            "continue after initial therapy:\n"
            "   THEN repeat administration of intramuscular epinephrine and establish wide-bore "
            "vascular access."
        )
        quoted_span = (
            "repeat administration of intramuscular epinephrine and establish wide-bore "
            "vascular access."
        )

        chunk = RetrievedChunk(
            doc_id="PROTO_SYN_001",
            section="Anaphylaxis Refractory Management",
            chunk_id="ANAPHYLAXIS_01_NODE_3",
            parent_id="ANAPHYLAXIS_01",
            text=repeat_node_text,
            population="adult",
            score=Decimal("0.95"),
            syndrome="anaphylaxis",
        )

        # Plan correctly preserves the 'repeat' qualifier, but cites the node requiring shock
        draft = PlanDraft(
            matched_protocol_title="Anaphylaxis Protocol",
            steps=[
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=(
                        "Repeat administration of intramuscular epinephrine and establish "
                        "wide-bore vascular access."
                    ),
                    drug_id="epinephrine",
                    requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                    route=Route.im,
                    citations=[
                        SpanCitation(
                            doc_id="PROTO_SYN_001",
                            section="Anaphylaxis Refractory Management",
                            chunk_id="ANAPHYLAXIS_01_NODE_3",
                            quoted_span=quoted_span,
                        )
                    ],
                )
            ],
        )

        verified_steps, _, _, _ = verify_plan(
            patient=patient,
            draft=draft,
            baseline_alerts=[],
            retrieved_chunks=[chunk],
            registry=registry,
        )

        assert len(verified_steps) == 1
        step = verified_steps[0]

        # Safety assertion 1: Step must NOT be APPROVED
        assert step.status != StepStatus.APPROVED
        # Safety assertion 2: Step must be marked NOT_APPLICABLE
        assert step.status == StepStatus.NOT_APPLICABLE
        assert any("not applicable" in r.lower() for r in step.rejection_reasons)

        class SpecificDraftLLM(LLMProvider):
            def __init__(self, plan: PlanDraft) -> None:
                self.plan = plan

            def draft_plan(self, context: PlanContext) -> PlanDraft:
                return self.plan

            def repair_plan(
                self,
                context: PlanContext,
                original_plan: PlanDraft,
                failure_reasons: list[str],
            ) -> PlanDraft:
                return original_plan

        # Safety assertion 3: Verdict evaluation must be UNVERIFIED, NEVER CHECKED_CLEAR
        triage_report = run_triage(
            patient=patient,
            registry=registry,
            llm=SpecificDraftLLM(draft),
        )
        assert triage_report.engine.verdict != Verdict.CHECKED_CLEAR
        assert triage_report.engine.verdict == Verdict.UNVERIFIED

    def test_hypotensive_anaphylaxis_node3_satisfies_applicability(self) -> None:
        """When shock is present (hypotensive), repeat node preconditions are met and approve."""
        patient = _build_hypotensive_anaphylaxis_patient()
        registry = load_registry()

        repeat_node_text = (
            "3. IF signs of systemic hypoperfusion, compensatory tachycardia, or refractory shock "
            "continue after initial therapy:\n"
            "   THEN repeat administration of intramuscular epinephrine and establish wide-bore "
            "vascular access."
        )
        quoted_span = (
            "repeat administration of intramuscular epinephrine and establish wide-bore "
            "vascular access."
        )

        chunk = RetrievedChunk(
            doc_id="PROTO_SYN_001",
            section="Anaphylaxis Refractory Management",
            chunk_id="ANAPHYLAXIS_01_NODE_3",
            parent_id="ANAPHYLAXIS_01",
            text=repeat_node_text,
            population="adult",
            score=Decimal("0.95"),
            syndrome="anaphylaxis",
        )

        draft = PlanDraft(
            matched_protocol_title="Anaphylaxis Protocol",
            steps=[
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=(
                        "Repeat administration of intramuscular epinephrine and establish "
                        "wide-bore vascular access."
                    ),
                    drug_id="epinephrine",
                    requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                    route=Route.im,
                    citations=[
                        SpanCitation(
                            doc_id="PROTO_SYN_001",
                            section="Anaphylaxis Refractory Management",
                            chunk_id="ANAPHYLAXIS_01_NODE_3",
                            quoted_span=quoted_span,
                        )
                    ],
                )
            ],
        )

        verified_steps, _, _, _ = verify_plan(
            patient=patient,
            draft=draft,
            baseline_alerts=[],
            retrieved_chunks=[chunk],
            registry=registry,
        )

        assert len(verified_steps) == 1
        step = verified_steps[0]
        # Step satisfies applicability under shock/hypotension
        assert step.status == StepStatus.APPROVED

    def test_api_triage_endpoint_normotensive_anaphylaxis_not_clear(self) -> None:
        """FastAPI /api/triage endpoint integration test confirming fail-closed verdict."""
        payload = {
            "patient": {
                "assessed_at": datetime.now(UTC).isoformat(),
                "age": {"value": 35, "unit": "years"},
                "sex": "male",
                "pregnancy": "no",
                "weight_kg": {"value": 75, "source": "measured"},
                "vitals": {
                    "heart_rate_bpm": {"value": 72, "source": "measured"},
                    "systolic_bp_mmhg": {"value": 128, "source": "measured"},  # Normal BP
                    "respiratory_rate_bpm": {"value": 16, "source": "measured"},
                    "spo2_percent": {"value": 98, "source": "measured"},
                    "temperature_c": {"value": "36.6", "source": "measured"},
                },
                "medications": [],
                "allergies": [],
                "medication_history_status": "confirmed_none",
                "allergy_history_status": "confirmed_nkda",
                "suspected_syndrome": "anaphylaxis",
            },
            "selected_syndrome": "anaphylaxis",
        }

        resp = client.post("/api/triage", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # The verdict must never be CHECKED_CLEAR when any step is unverified or not applicable
        assert data["engine"]["verdict"] in (
            Verdict.UNVERIFIED.value,
            Verdict.CHECKED_ALERTS.value,
        )
        assert data["engine"]["verdict"] != Verdict.CHECKED_CLEAR.value
