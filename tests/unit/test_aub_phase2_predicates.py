"""Unit tests for AUB Phase 2 Task T2.1: Structured Predicate Vocabulary (D2).

Safety Properties:
1. Every predicate is typed, constrained, and carries source_status: SYNTHETIC_AUTHORED.
2. Field paths are strictly validated against the real Patient schema. Invalid fields fail.
3. Unsupported operators fail validation.
4. Unknown patient values yield PredicateEvalResult.UNKNOWN and never silently evaluate to false.
5. The clinical rule engine (src/triagerag/engine) never imports or reads predicates.yaml.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from triagerag.contracts.enums import Consciousness, SourceStatus
from triagerag.contracts.schemas import (
    Age,
    AgeUnit,
    IngredientStrength,
    Measured,
    MedicationEntry,
    Patient,
    Provenance,
    Vitals,
)
from triagerag.rag.predicates import (
    PredicateDefinition,
    PredicateEvalResult,
    PredicateOperator,
    PredicateVocabularyConfig,
    evaluate_predicate,
    load_predicate_vocabulary,
)


def _make_base_patient(**kwargs) -> Patient:
    """Helper to build a clean patient for predicate evaluation."""
    defaults = {
        "assessed_at": datetime.now(UTC),
        "age": Age(value=Decimal("45"), unit=AgeUnit.years),
        "sex": "male",
        "pregnancy": "not_applicable",
        "weight_kg": Measured[Decimal](value=Decimal("75.0"), source="measured"),
        "vitals": Vitals(
            heart_rate_bpm=Measured[int](value=80, source="measured"),
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=80, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            blood_glucose_mg_dl=Measured[Decimal](value=Decimal("100.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
            gcs_total=Measured[int](value=15, source="measured"),
        ),
        "allergy_history_status": "confirmed_none",
        "medication_history_status": "confirmed_none",
        "allergies": [],
        "medications": [],
        "renal_impairment": "no",
        "hepatic_impairment": "no",
        "suspected_syndrome": "chest_pain",
    }
    defaults.update(kwargs)
    return Patient.model_validate(defaults)


def test_load_predicate_vocabulary_from_yaml() -> None:
    """Verify loading canonical data/retrieval/predicates.yaml."""
    config = load_predicate_vocabulary()
    assert isinstance(config, PredicateVocabularyConfig)
    assert len(config.predicates) >= 15
    assert config.source_status == SourceStatus.SYNTHETIC_AUTHORED

    # Verify key expected predicates exist
    pred_ids = {p.id for p in config.predicates}
    assert "low_systolic_bp" in pred_ids
    assert "normal_or_high_systolic_bp" in pred_ids
    assert "tachycardia" in pred_ids
    assert "bradycardia" in pred_ids
    assert "severe_tachypnea" in pred_ids
    assert "respiratory_depression" in pred_ids
    assert "hypoglycemia" in pred_ids
    assert "altered_consciousness" in pred_ids
    assert "beta_blocker_active" in pred_ids
    assert "pde5_inhibitor_active" in pred_ids
    assert "penicillin_allergy" in pred_ids


def test_predicate_provenance_strictly_synthetic_authored() -> None:
    """Verify that every predicate definition carries SYNTHETIC_AUTHORED status."""
    config = load_predicate_vocabulary()
    for pred in config.predicates:
        assert pred.provenance.source_status == SourceStatus.SYNTHETIC_AUTHORED
        assert not pred.provenance.verified


def test_field_validation_rejects_invalid_patient_fields() -> None:
    """Verify that targeting non-existent fields fails validation with ValueError."""
    prov = Provenance(
        source_doc="TEST",
        section_ref="TEST",
        version_or_date="2026",
        source_status=SourceStatus.SYNTHETIC_AUTHORED,
        content_origin="AGENT_DRAFT_SYNTHETIC",
        verified=False,
    )

    # Valid field should succeed
    p_valid = PredicateDefinition(
        id="test_valid",
        description="Test valid field",
        target_field="vitals.systolic_bp_mmhg",
        operator=PredicateOperator.LT,
        threshold=Decimal("90"),
        provenance=prov,
    )
    assert p_valid.target_field == "vitals.systolic_bp_mmhg"

    # Non-existent field on Vitals
    with pytest.raises(ValidationError, match="Invalid target_field"):
        PredicateDefinition(
            id="test_invalid_vital",
            description="Test non-existent vital",
            target_field="vitals.non_existent_vital_signal",
            operator=PredicateOperator.LT,
            threshold=Decimal("90"),
            provenance=prov,
        )

    # Non-existent top-level field on Patient
    with pytest.raises(ValidationError, match="Invalid target_field"):
        PredicateDefinition(
            id="test_invalid_patient",
            description="Test non-existent patient field",
            target_field="non_existent_patient_attribute",
            operator=PredicateOperator.EQ,
            expected_value="yes",
            provenance=prov,
        )


def test_duplicate_predicate_ids_fail_validation() -> None:
    """Verify that duplicate predicate IDs in vocabulary raise ValidationError."""
    prov = Provenance(
        source_doc="TEST",
        section_ref="TEST",
        version_or_date="2026",
        source_status=SourceStatus.SYNTHETIC_AUTHORED,
        content_origin="AGENT_DRAFT_SYNTHETIC",
        verified=False,
    )
    p1 = PredicateDefinition(
        id="duplicate_id",
        description="First definition",
        target_field="vitals.systolic_bp_mmhg",
        operator=PredicateOperator.LT,
        threshold=Decimal("90"),
        provenance=prov,
    )
    p2 = PredicateDefinition(
        id="duplicate_id",
        description="Second definition with same id",
        target_field="vitals.heart_rate_bpm",
        operator=PredicateOperator.GT,
        threshold=Decimal("100"),
        provenance=prov,
    )
    with pytest.raises(ValidationError, match="Duplicate predicate ID"):
        PredicateVocabularyConfig(
            version="1.0.0",
            source_status=SourceStatus.SYNTHETIC_AUTHORED,
            provenance=prov,
            predicates=[p1, p2],
        )


def test_predicate_evaluation_vitals_tri_state() -> None:
    """Verify tri-state evaluation (SATISFIED, NOT_SATISFIED, UNKNOWN) on vitals."""
    prov = Provenance(
        source_doc="TEST",
        section_ref="TEST",
        version_or_date="2026",
        source_status=SourceStatus.SYNTHETIC_AUTHORED,
        content_origin="AGENT_DRAFT_SYNTHETIC",
        verified=False,
    )
    pred_low_bp = PredicateDefinition(
        id="low_systolic_bp",
        description="Systolic BP < 90",
        target_field="vitals.systolic_bp_mmhg",
        operator=PredicateOperator.LT,
        threshold=Decimal("90"),
        provenance=prov,
    )

    # 1. Measured < 90 -> SATISFIED
    pat_hypo = _make_base_patient(
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=84, source="measured"))
    )
    assert evaluate_predicate(pred_low_bp, pat_hypo) == PredicateEvalResult.SATISFIED

    # 2. Measured >= 90 -> NOT_SATISFIED
    pat_norm = _make_base_patient(
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=120, source="measured"))
    )
    assert evaluate_predicate(pred_low_bp, pat_norm) == PredicateEvalResult.NOT_SATISFIED

    # 3. Source unknown -> UNKNOWN (never false!)
    pat_unk = _make_base_patient(
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=None, source="unknown"))
    )
    assert evaluate_predicate(pred_low_bp, pat_unk) == PredicateEvalResult.UNKNOWN


def test_predicate_evaluation_medications() -> None:
    """Verify medication predicate evaluation against history status and classes."""
    prov = Provenance(
        source_doc="TEST",
        section_ref="TEST",
        version_or_date="2026",
        source_status=SourceStatus.SYNTHETIC_AUTHORED,
        content_origin="AGENT_DRAFT_SYNTHETIC",
        verified=False,
    )
    pred_bb = PredicateDefinition(
        id="beta_blocker_active",
        description="Active beta blocker therapy",
        target_field="medications",
        operator=PredicateOperator.HAS_CLASS,
        expected_value="BETA_BLOCKERS",
        provenance=prov,
    )

    # 1. Medication history unknown -> UNKNOWN
    pat_unk = _make_base_patient(medication_history_status="unknown_unobtainable", medications=[])
    assert evaluate_predicate(pred_bb, pat_unk) == PredicateEvalResult.UNKNOWN

    # 2. Medication history confirmed_none -> NOT_SATISFIED
    pat_none = _make_base_patient(medication_history_status="confirmed_none", medications=[])
    assert evaluate_predicate(pred_bb, pat_none) == PredicateEvalResult.NOT_SATISFIED

    # 3. Confirmed list with metoprolol -> SATISFIED
    pat_meto = _make_base_patient(
        medication_history_status="confirmed_list",
        medications=[
            MedicationEntry(
                raw_text="metoprolol 50mg",
                ingredients=[IngredientStrength(ingredient_id="metoprolol")],
                resolved=True,
            )
        ],
    )
    assert evaluate_predicate(pred_bb, pat_meto) == PredicateEvalResult.SATISFIED


def test_clinical_rule_engine_isolation_from_predicates() -> None:
    """Rule separation test: engine modules must NEVER import from predicates.py."""
    engine_dir = Path("src/triagerag/engine")
    assert engine_dir.is_dir()
    for py_file in engine_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "predicates" not in alias.name, (
                        f"Engine file {py_file} violates isolation by importing {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "predicates" not in node.module, (
                    f"Engine file {py_file} violates isolation by importing from {node.module}"
                )
