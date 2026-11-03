"""Tests for retrieval explainability, complaint isolation, and syndrome inference hardening.

Covers:
- Finding A: No substring-based syndrome inference in triage route; unconfirmed vitals inference
  caps steps at REQUIRES_CLINICIAN_CONFIRMATION (ADR-0007).
- Finding B: Strict isolation of untrusted chief complaint (Rule R7: default false, opt-in only).
- Contract: TriageExplanation deterministic generation, headline, plain language summary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.api.routes.triage import execute_triage, get_retrieval_service
from triagerag.api.schemas import TriageApiRequest
from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AbstainCode,
    ActionType,
    DoseUnit,
    Route,
    StepStatus,
    Verdict,
)
from triagerag.contracts.schemas import (
    Age,
    EngineReport,
    ExplicitDose,
    Measured,
    Patient,
    PlanStepDraft,
    ProviderMetadata,
    RetrievalReport,
    RetrievedChunk,
    SpanCitation,
    TriageExplanation,
    VerifiedStep,
    Vitals,
)
from triagerag.engine.registry import load_registry
from triagerag.orchestrator import build_triage_explanation, run_triage

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def _make_test_patient(
    suspected_syndrome: str | None = None,
    complaint: str = "",
) -> Patient:
    return Patient(
        assessed_at=NOW,
        age=Age(value=Decimal(52), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=128, source="measured"),
            heart_rate_bpm=Measured[int](value=76, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=suspected_syndrome,
        chief_complaint_untrusted=complaint,
    )


def test_no_substring_syndrome_inference_from_complaint() -> None:
    """Narrative text like 'acute chest pain' must NOT mutate syndrome to chest_pain."""
    req = TriageApiRequest(
        patient=_make_test_patient(
            suspected_syndrome=None,
            complaint="Patient presents with acute chest pain and diaphoresis",
        ),
        suspected_syndrome=None,
        include_complaint_in_llm=False,
    )

    resp = execute_triage(req)
    # Syndrome must NOT be forced to chest_pain simply by substring match in route
    assert resp.explanation is not None
    assert (
        "EMPTY_QUERY" in resp.explanation.retrieval_explanation
        or "no suspected syndrome" in resp.explanation.retrieval_explanation
    )


def test_include_complaint_strictly_opt_in() -> None:
    """include_complaint_in_llm is strictly false by default and only enabled when requested."""
    req_default = TriageApiRequest(
        patient=_make_test_patient(
            suspected_syndrome=None,
            complaint="Severe headache and shortness of breath",
        ),
        include_complaint_in_llm=False,
    )
    resp_default = execute_triage(req_default)
    assert resp_default.explanation is not None
    assert "Patient narrative was excluded" in resp_default.explanation.generation_disclosure

    req_opt_in = TriageApiRequest(
        patient=_make_test_patient(
            suspected_syndrome=None,
            complaint="Severe headache and shortness of breath",
        ),
        include_complaint_in_llm=True,
    )
    resp_opt_in = execute_triage(req_opt_in)
    assert resp_opt_in.explanation is not None
    assert "delimited clinical context block only" in resp_opt_in.explanation.generation_disclosure


def test_vitals_inferred_syndrome_enforces_clinician_confirmation() -> None:
    """When a syndrome is inferred from vitals (ADR-0007), steps require clinician confirmation."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)

    # Anaphylaxis vitals criteria: hypotension + tachycardia
    patient = Patient(
        assessed_at=NOW,
        age=Age(value=Decimal(30), unit="years"),  # type: ignore[arg-type]
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("60.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),  # severe hypotension
            heart_rate_bpm=Measured[int](value=125, source="measured"),  # tachycardia
            respiratory_rate_bpm=Measured[int](value=24, source="measured"),
            spo2_percent=Measured[int](value=91, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.5"), source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=None,  # Not clinician confirmed!
    )

    index = get_retrieval_service().index
    report = run_triage(patient=patient, registry=registry, index=index)

    # The real index must have been consulted (not INDEX_UNAVAILABLE), otherwise
    # this test would pass vacuously with zero steps.
    assert report.retrieval is not None
    assert report.retrieval.abstain_code != AbstainCode.INDEX_UNAVAILABLE
    # Without a clinician-confirmed syndrome, no step may be auto-approved (ADR-0007, R2).
    assert all(step.status != StepStatus.APPROVED for step in report.verified_steps)
    # Never CHECKED_CLEAR when retrieval produced no applicable protocol evidence.
    if report.retrieval.abstained:
        assert report.engine.verdict != Verdict.CHECKED_CLEAR


def test_triage_explanation_structure_and_coverage() -> None:
    """build_triage_explanation produces a complete, grounded TriageExplanation."""
    patient = _make_test_patient(suspected_syndrome="anaphylaxis")

    engine_report = EngineReport(
        verdict=Verdict.CHECKED_CLEAR,
        score=None,
        baseline_alerts=[],
        plan_alerts=[],
        dose_reports=[],
        checks_run=5,
        checks_skipped=[],
        unresolved_entities=[],
        ruleset_coverage=["DDI", "ALLERGY", "DOSE"],
        coverage_gaps=["Pediatric dosing adjustments"],
        unverified_rules_evaluated=0,
    )

    retrieval_report = RetrievalReport(
        chunks=[
            RetrievedChunk(
                doc_id="PROTO_ANAPHYLAXIS",
                section="Immediate Management",
                chunk_id="CHUNK_001",
                parent_id="DOC_ANAPHYLAXIS",
                text="Administer epinephrine IM 0.3mg immediately.",
                population="adult",
                syndrome="anaphylaxis",
                score=4.85,
            )
        ],
        abstained=False,
        query="adult anaphylaxis management",
    )

    verified_steps = [
        VerifiedStep(
            draft=PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                drug_id="epinephrine",
                requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg),
                route=Route.im,
                narrative_instruction="Administer epinephrine IM 0.3mg.",
                citations=[
                    SpanCitation(
                        doc_id="PROTO_ANAPHYLAXIS",
                        section="Immediate Management",
                        chunk_id="CHUNK_001",
                        quoted_span="Administer epinephrine IM 0.3mg",
                    )
                ],
            ),
            status=StepStatus.APPROVED,
            rejection_reasons=[],
        )
    ]

    provider_meta = ProviderMetadata(
        generation_mode="deterministic_mock",
        requested_profile="COMPLIANT",
        repair_attempted=False,
        repair_cycles=0,
        retrieval_backend="bm25",
    )

    explanation = build_triage_explanation(
        engine=engine_report,
        retrieval=retrieval_report,
        verified_steps=verified_steps,
        patient=patient,
        provider_info=provider_meta,
        llm_fallback_mode=False,
    )

    assert isinstance(explanation, TriageExplanation)
    assert explanation.headline == "CHECKED CLEAR: No Configured Safety Rules Triggered"
    assert "All applicable deterministic rules" in explanation.plain_language_summary
    assert len(explanation.outcome_reasons) >= 1
    assert "BM25" in explanation.retrieval_explanation
    assert "PROTO_ANAPHYLAXIS" in explanation.evidence_summary
    assert any("Deterministic" in check for check in explanation.completed_checks)
    assert any("Pediatric dosing adjustments" in gap for gap in explanation.unresolved_checks)
    assert len(explanation.permitted_ui_actions) >= 1
    assert len(explanation.rejected_paths) >= 1
    assert any("Rejected BLOCKED" in r for r in explanation.rejected_paths)


def test_rejected_paths_for_all_canonical_verdicts() -> None:
    """_build_rejected_paths explains why alternative verdicts were rejected for all lattice states."""
    from triagerag.contracts.enums import Verdict
    from triagerag.orchestrator import _build_rejected_paths

    for v, expected_rejections in [
        (
            Verdict.BLOCKED,
            ["Rejected CHECKED_CLEAR", "Rejected CHECKED_ALERTS", "Rejected UNVERIFIED"],
        ),
        (
            Verdict.UNVERIFIED,
            ["Rejected CHECKED_CLEAR", "Rejected BLOCKED", "Rejected CHECKED_ALERTS"],
        ),
        (
            Verdict.CHECKED_ALERTS,
            ["Rejected CHECKED_CLEAR", "Rejected BLOCKED", "Rejected UNVERIFIED"],
        ),
        (
            Verdict.CHECKED_CLEAR,
            ["Rejected BLOCKED", "Rejected CHECKED_ALERTS", "Rejected UNVERIFIED"],
        ),
    ]:
        dummy_engine = EngineReport(
            verdict=v,
            score=None,
            baseline_alerts=[],
            plan_alerts=[],
            dose_reports=[],
            checks_run=1,
            checks_skipped=[],
            unresolved_entities=[],
            ruleset_coverage=[],
            coverage_gaps=[],
            unverified_rules_evaluated=0,
        )
        rejections = _build_rejected_paths(dummy_engine, None)
        assert len(rejections) == 3
        for expected in expected_rejections:
            assert any(expected in r for r in rejections)


def test_triage_response_carries_input_patient_and_execution_trace() -> None:
    """TriageResponse carries populated input_patient and 8-stage execution_trace."""
    from triagerag.config import get_data_dir
    from triagerag.contracts.scenarios import get_preloaded_scenario
    from triagerag.engine.registry import ClinicalRegistry
    from triagerag.llm.fake import FakeLLM, FakeLLMProfile
    from triagerag.orchestrator import run_triage
    from triagerag.rag.service import RetrievalService

    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    service = RetrievalService.create_default(data_dir)

    patient, overrides = get_preloaded_scenario("BLOCK")
    response = run_triage(
        patient=patient,
        registry=registry,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
        index=service.index,
        overrides=overrides,
    )

    # 1. Execution trace contains all 8 nodes
    assert isinstance(response.execution_trace, list)
    assert len(response.execution_trace) == 8
    node_names = [stage["node"] for stage in response.execution_trace]
    assert "normalise" in node_names
    assert "intake_safety_checks" in node_names
    assert "retrieve" in node_names
    assert "draft_plan" in node_names
    assert "verify" in node_names
    assert "block_seal" in node_names
    assert "audit" in node_names
    assert "explain" in node_names

    for stage in response.execution_trace:
        assert stage["status"] == "completed"
        assert isinstance(stage["duration_ms"], (int, float))
        assert stage["duration_ms"] >= 0

    # 2. Input patient is preserved alongside normalized patient
    assert response.input_patient is not None
    assert response.patient is not None
    assert response.input_patient.age.value == patient.age.value

    # 3. Action plan is populated
    assert response.action_plan is not None
    assert len(response.action_plan.immediate_actions) > 0


def test_action_plan_populated_for_all_canonical_scenarios() -> None:
    """All 5 canonical scenarios produce populated, deterministic ActionPlan objects."""
    from triagerag.config import get_data_dir
    from triagerag.contracts.scenarios import get_preloaded_scenario
    from triagerag.engine.registry import ClinicalRegistry
    from triagerag.llm.fake import FakeLLM, FakeLLMProfile
    from triagerag.orchestrator import run_triage
    from triagerag.rag.service import RetrievalService

    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    service = RetrievalService.create_default(data_dir)

    for scenario_id in ["BLOCK", "UNVERIFIED", "HIGH", "CLEAN", "ABSTAIN"]:
        patient, overrides = get_preloaded_scenario(scenario_id)
        response = run_triage(
            patient=patient,
            registry=registry,
            llm=FakeLLM(FakeLLMProfile.COMPLIANT),
            index=service.index,
            overrides=overrides,
        )
        assert response.action_plan is not None
        assert isinstance(response.action_plan.decision_summary, str)
        assert len(response.action_plan.decision_summary) > 0
        assert len(response.action_plan.monitoring_steps) > 0
        assert isinstance(response.action_plan.immediate_actions, list)
        assert len(response.action_plan.immediate_actions) > 0
