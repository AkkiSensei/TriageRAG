"""Unit tests for Trust Policy (T6.0 / AUB-ENG-04 / HD-7).

Safety Properties:
1. trust_mode supports 'demo' (default for research prototype) and 'strict'.
2. Every EngineReport unconditionally reports verified rule count ("verified n of N").
3. Under DEMO mode, unverified draft rules execute with explicit provenance disclosure.
4. Under STRICT mode, unverified draft rules cannot issue CHECKED_CLEAR; system fails closed to UNVERIFIED (Rule R2, HD-7).
5. Under STRICT mode, BLOCK alerts from unverified rules are still preserved as protective tripwires.
6. When all evaluated rules carry verified: true, STRICT mode permits CHECKED_CLEAR.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    Consciousness,
    ContentOrigin,
    RuleStatus,
    Severity,
    SourceStatus,
    TrustMode,
    Verdict,
)
from triagerag.contracts.rules_schema import PairRule
from triagerag.contracts.schemas import (
    Age,
    EngineReport,
    Measured,
    MedicationEntry,
    OrchestratorConfig,
    Patient,
    Provenance,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry, load_registry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols


@pytest.fixture(scope="module")
def clinical_index() -> BM25ClinicalIndex:
    return BM25ClinicalIndex(ingest_protocols(get_data_dir()))


def _build_test_patient() -> Patient:
    return Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("30"), unit="years"),  # type: ignore[arg-type]
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("60.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=85, source="measured"),
            heart_rate_bpm=Measured[int](value=120, source="measured"),
            respiratory_rate_bpm=Measured[int](value=26, source="measured"),
            spo2_percent=Measured[int](value=91, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medications=[],
        allergies=[],
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
        chief_complaint_untrusted="Difficulty breathing and tongue swelling after peanut ingestion",
    )


def test_trust_mode_enum_values() -> None:
    assert TrustMode.DEMO == "demo"
    assert TrustMode.STRICT == "strict"


def test_engine_report_contains_verified_summary(clinical_index: BM25ClinicalIndex) -> None:
    registry = load_registry()
    patient = _build_test_patient()
    llm = FakeLLM(FakeLLMProfile.COMPLIANT)

    cfg_demo = OrchestratorConfig(trust_mode=TrustMode.DEMO)
    res_demo = run_triage(patient, registry=registry, llm=llm, index=clinical_index, config=cfg_demo)

    assert hasattr(res_demo.engine, "trust_mode")
    assert res_demo.engine.trust_mode == TrustMode.DEMO
    assert hasattr(res_demo.engine, "verified_rules_count")
    assert hasattr(res_demo.engine, "total_rules_count")
    assert res_demo.engine.total_rules_count == len(registry.rules)
    assert res_demo.engine.verified_rules_count == sum(1 for r in registry.rules if r.provenance.verified)
    assert f"verified {res_demo.engine.verified_rules_count} of {res_demo.engine.total_rules_count}" in res_demo.engine.verified_rules_summary


def test_demo_mode_allows_checked_clear_with_unverified_rules(clinical_index: BM25ClinicalIndex) -> None:
    registry = load_registry()
    patient = _build_test_patient()
    llm = FakeLLM(FakeLLMProfile.COMPLIANT)

    cfg = OrchestratorConfig(trust_mode=TrustMode.DEMO)
    res = run_triage(patient, registry=registry, llm=llm, index=clinical_index, config=cfg)

    # In demo mode, a clean patient with approved steps passes to CHECKED_CLEAR
    assert res.engine.verdict == Verdict.CHECKED_CLEAR
    assert res.engine.trust_mode == TrustMode.DEMO


def test_strict_mode_fails_closed_to_unverified_when_rules_unverified(clinical_index: BM25ClinicalIndex) -> None:
    registry = load_registry()
    patient = _build_test_patient()
    llm = FakeLLM(FakeLLMProfile.COMPLIANT)

    cfg = OrchestratorConfig(trust_mode=TrustMode.STRICT)
    res = run_triage(patient, registry=registry, llm=llm, index=clinical_index, config=cfg)

    # In strict mode, because seed rules are unverified drafts (HD-7), verdict cannot be CHECKED_CLEAR
    assert res.engine.verdict == Verdict.UNVERIFIED
    assert res.engine.trust_mode == TrustMode.STRICT
    assert "UNVERIFIED_RULESET" in (res.engine.unverified_reason or "")
    assert "strict" in (res.engine.unverified_reason or "").lower()


def test_strict_mode_permits_clear_when_rules_verified(clinical_index: BM25ClinicalIndex) -> None:
    registry = load_registry()
    patient = _build_test_patient()
    llm = FakeLLM(FakeLLMProfile.COMPLIANT)

    cfg = OrchestratorConfig(trust_mode=TrustMode.STRICT)
    verified_prov = Provenance(
        source_doc="TEST_DOC",
        source_status=SourceStatus.REVIEWED,
        content_origin=ContentOrigin.SOURCE_EXTRACT,
        version_or_date="2026",
        verified=True,
        reviewer="DR_TEST_CLINICIAN",
        section_ref="SEC_1",
    )
    test_rule = PairRule(
        id="TEST_VERIFIED_INTERACTION",
        severity=Severity.BLOCK,
        status=RuleStatus.ACTIVE,
        consequence="Severe hypotension",
        action="Do not administer",
        provenance=verified_prov,
        type="pair",
        drug_a="nitroglycerin",
        drug_b="sildenafil",
    )
    reg_verified = registry.with_rules([test_rule])
    res = run_triage(patient, registry=reg_verified, llm=llm, index=clinical_index, config=cfg)
    assert res.engine.trust_mode == TrustMode.STRICT
    # With zero alerts and only verified rules evaluated, it can clear
    assert res.engine.verdict == Verdict.CHECKED_CLEAR
    assert res.engine.verified_rules_count == 1
    assert res.engine.total_rules_count == 1
    assert res.engine.verified_rules_summary == "verified 1 of 1"


def test_strict_mode_preserves_block_alert(clinical_index: BM25ClinicalIndex) -> None:
    registry = load_registry()
    # Patient with baseline sildenafil and nitroglycerin interaction
    patient = Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("50"), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
            heart_rate_bpm=Measured[int](value=75, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medications=[
            MedicationEntry(raw_text="sildenafil"),
            MedicationEntry(raw_text="nitroglycerin"),
        ],
        allergies=[],
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_list",
        suspected_syndrome="chest_pain",
    )

    # In strict mode, BLOCK alert still fires and dominates verdict
    cfg = OrchestratorConfig(trust_mode=TrustMode.STRICT)
    res = run_triage(patient, registry=registry, index=clinical_index, config=cfg)
    assert res.engine.trust_mode == TrustMode.STRICT
    assert res.engine.verdict == Verdict.BLOCKED
    assert any(a.severity == Severity.BLOCK for a in res.engine.baseline_alerts)

