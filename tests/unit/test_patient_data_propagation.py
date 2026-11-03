"""Regression tests for patient data propagation through LangGraph and API layers.

Safety Property:
All user-entered patient information (demographics, weight, vitals, medications, allergies)
must propagate faithfully through the LangGraph StateGraph pipeline into TriageResponse.
No entered value may be dropped, overwritten to None, or mistaken for UNKNOWN.
Genuinely missing values must remain UNKNOWN without fabricated defaults.
"""

from __future__ import annotations

import concurrent.futures
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from triagerag.api.app import app
from triagerag.config import get_data_dir
from triagerag.contracts.enums import AgeUnit, Consciousness, Route, Verdict
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    ExplicitDose,
    Measured,
    MedicationEntry,
    Patient,
    TriageResponse,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestration.langgraph_workflow import run_triage_graph
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols


@pytest.fixture(scope="module")
def registry() -> ClinicalRegistry:
    return ClinicalRegistry.load_from_directory(get_data_dir())


@pytest.fixture(scope="module")
def index() -> BM25ClinicalIndex:
    return BM25ClinicalIndex(ingest_protocols(get_data_dir()))


@pytest.fixture
def base_assessed_at() -> datetime:
    return datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)


def test_entered_weight_propagates_through_graph(
    registry: ClinicalRegistry, index: BM25ClinicalIndex, base_assessed_at: datetime
) -> None:
    """Entered weight (e.g. 84.7 kg) must survive LangGraph execution into TriageResponse.patient."""
    patient = Patient(
        assessed_at=base_assessed_at,
        age=Age(value=Decimal("45"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("84.7"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=78, source="measured"),
            systolic_bp_mmhg=Measured[int](value=125, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=82, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            supplemental_o2=Measured[Any](value="no", source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
    )

    response, _trace = run_triage_graph(
        patient=patient,
        registry=registry,
        index=index,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
    )

    assert response.patient is not None
    assert response.patient.weight_kg.value == Decimal("84.7")
    assert response.patient.weight_kg.source == "measured"
    # Weight was entered, so INTAKE_PATIENT_WEIGHT should NOT be skipped
    skipped_ids = [s.rule_id for s in response.engine.checks_skipped]
    assert "INTAKE_PATIENT_WEIGHT" not in skipped_ids


def test_all_populated_fields_survive_graph_execution(
    registry: ClinicalRegistry, index: BM25ClinicalIndex, base_assessed_at: datetime
) -> None:
    """All populated clinical details must survive graph execution without data corruption."""
    patient = Patient(
        assessed_at=base_assessed_at,
        age=Age(value=Decimal("62"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("68.5"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=92, source="measured"),
            systolic_bp_mmhg=Measured[int](value=138, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=88, source="measured"),
            respiratory_rate_bpm=Measured[int](value=18, source="measured"),
            spo2_percent=Measured[int](value=97, source="measured"),
            supplemental_o2=Measured[Any](value="no", source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("37.2"), source="measured"),
            blood_glucose_mg_dl=Measured[Decimal](value=Decimal("115.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_list",
        medications=[
            MedicationEntry(
                raw_text="Amlodipine 5mg",
                dose_taken=ExplicitDose(amount=Decimal("5"), unit="mg"),  # type: ignore[arg-type]
                route=Route.oral,
            )
        ],
        allergy_history_status="confirmed_list",
        allergies=[
            AllergyEntry(
                raw_substance="Penicillin",
                reaction_type="mild_rash",
            )
        ],
        suspected_syndrome="chest_pain",
        renal_impairment="mild",
        hepatic_impairment="no",
    )

    response, _trace = run_triage_graph(
        patient=patient,
        registry=registry,
        index=index,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
    )

    p = response.patient
    assert p is not None
    assert p.age.value == Decimal("62")
    assert p.sex == "female"
    assert p.pregnancy == "no"
    assert p.weight_kg.value == Decimal("68.5")
    assert p.weight_kg.source == "measured"
    assert p.vitals.heart_rate_bpm.value == 92
    assert p.vitals.systolic_bp_mmhg.value == 138
    assert p.vitals.diastolic_bp_mmhg.value == 88
    assert p.vitals.respiratory_rate_bpm.value == 18
    assert p.vitals.spo2_percent.value == 97
    assert p.vitals.supplemental_o2.value == "no"
    assert p.vitals.temperature_c.value == Decimal("37.2")
    assert p.vitals.blood_glucose_mg_dl.value == Decimal("115.0")
    assert p.vitals.consciousness.value == Consciousness.A
    assert len(p.medications) == 1
    assert len(p.allergies) == 1
    assert p.renal_impairment == "mild"
    assert p.hepatic_impairment == "no"


def test_genuinely_missing_values_remain_unknown(
    registry: ClinicalRegistry, index: BM25ClinicalIndex, base_assessed_at: datetime
) -> None:
    """Missing fields must remain unknown; system must fail closed to UNVERIFIED without defaults."""
    patient = Patient(
        assessed_at=base_assessed_at,
        age=Age(value=Decimal("50"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=None, source="unknown"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=80, source="measured"),
            systolic_bp_mmhg=Measured[int](value=None, source="unknown"),
        ),
        medication_history_status="incomplete",
        allergy_history_status="unknown_unobtainable",
    )

    response, _trace = run_triage_graph(
        patient=patient,
        registry=registry,
        index=index,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
    )

    assert response.patient is not None
    assert response.patient.weight_kg.value is None
    assert response.patient.weight_kg.source == "unknown"
    assert response.engine.verdict == Verdict.UNVERIFIED
    skipped_ids = [s.rule_id for s in response.engine.checks_skipped]
    assert "INTAKE_PATIENT_WEIGHT" in skipped_ids
    assert any("medications" in s.missing_fields for s in response.engine.checks_skipped)
    assert any("allergies" in s.missing_fields for s in response.engine.checks_skipped)


def test_legitimate_zero_and_false_values_not_mistaken_for_missing(
    registry: ClinicalRegistry, index: BM25ClinicalIndex, base_assessed_at: datetime
) -> None:
    """Zero pulse or false/no boolean options must be preserved and not converted to null."""
    patient = Patient(
        assessed_at=base_assessed_at,
        age=Age(value=Decimal("30"), unit=AgeUnit.years),
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=0, source="measured"),
            systolic_bp_mmhg=Measured[int](value=0, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=0, source="measured"),
            respiratory_rate_bpm=Measured[int](value=0, source="measured"),
            supplemental_o2=Measured[Any](value="no", source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
    )

    response, _trace = run_triage_graph(
        patient=patient,
        registry=registry,
        index=index,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
    )

    p = response.patient
    assert p is not None
    assert p.vitals.heart_rate_bpm.value == 0
    assert p.vitals.heart_rate_bpm.source == "measured"
    assert p.vitals.systolic_bp_mmhg.value == 0
    assert p.vitals.diastolic_bp_mmhg.value == 0
    assert p.vitals.respiratory_rate_bpm.value == 0
    assert p.vitals.supplemental_o2.value == "no"
    assert p.vitals.supplemental_o2.source == "measured"


def test_concurrent_graph_executions_isolate_patient_data(
    registry: ClinicalRegistry, index: BM25ClinicalIndex, base_assessed_at: datetime
) -> None:
    """Concurrent invocations of LangGraph must not contaminate or swap patient details."""
    patient_a = Patient(
        assessed_at=base_assessed_at,
        age=Age(value=Decimal("22"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("52.0"), source="measured"),
        vitals=Vitals(heart_rate_bpm=Measured[int](value=72, source="measured")),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
    )

    patient_b = Patient(
        assessed_at=base_assessed_at,
        age=Age(value=Decimal("77"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("108.5"), source="measured"),
        vitals=Vitals(heart_rate_bpm=Measured[int](value=110, source="measured")),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
    )

    def execute(pat: Patient) -> TriageResponse:
        resp, _ = run_triage_graph(
            patient=pat,
            registry=registry,
            index=index,
            llm=FakeLLM(FakeLLMProfile.COMPLIANT),
        )
        return resp

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        fut_a = executor.submit(execute, patient_a)
        fut_b = executor.submit(execute, patient_b)
        resp_a = fut_a.result()
        resp_b = fut_b.result()

    assert resp_a.patient is not None
    assert resp_b.patient is not None
    assert resp_a.patient.weight_kg.value == Decimal("52.0")
    assert resp_a.patient.age.value == Decimal("22")
    assert resp_b.patient.weight_kg.value == Decimal("108.5")
    assert resp_b.patient.age.value == Decimal("77")


def test_fastapi_triage_endpoint_propagates_patient_details() -> None:
    """The /api/triage HTTP endpoint must return the populated Patient in TriageResponse."""
    client = TestClient(app)
    payload = {
        "patient": {
            "assessed_at": "2026-11-02T10:00:00Z",
            "age": {"value": "45", "unit": "years"},
            "sex": "male",
            "pregnancy": "not_applicable",
            "weight_kg": {"value": "82.5", "source": "measured"},
            "vitals": {
                "heart_rate_bpm": {"value": 85, "source": "measured"},
                "systolic_bp_mmhg": {"value": 120, "source": "measured"},
                "diastolic_bp_mmhg": {"value": 80, "source": "measured"},
                "respiratory_rate_bpm": {"value": 16, "source": "measured"},
                "spo2_percent": {"value": 98, "source": "measured"},
                "supplemental_o2": {"value": "no", "source": "measured"},
                "temperature_c": {"value": "37.0", "source": "measured"},
                "consciousness": {"value": "A", "source": "measured"},
                "blood_glucose_mg_dl": {"value": None, "source": "unknown"},
                "gcs_total": {"value": None, "source": "unknown"},
            },
            "medication_history_status": "confirmed_none",
            "allergy_history_status": "confirmed_none",
            "medications": [],
            "allergies": [],
            "suspected_syndrome": "chest_pain",
            "renal_impairment": "no",
            "hepatic_impairment": "no",
            "chief_complaint_untrusted": "",
        },
        "llm_profile": "COMPLIANT",
        "include_complaint_in_llm": False,
    }

    resp = client.post("/api/triage", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "patient" in data
    assert data["patient"] is not None
    assert data["patient"]["weight_kg"]["value"] == "82.5"
    assert data["patient"]["weight_kg"]["source"] == "measured"
    assert data["patient"]["age"]["value"] == "45"
    assert data["patient"]["vitals"]["heart_rate_bpm"]["value"] == 85
    assert data["patient"]["vitals"]["supplemental_o2"]["value"] == "no"
    assert data["patient"]["vitals"]["consciousness"]["value"] == "A"
