"""Unit tests for AUB Phase 2 Task T2.4: Patient-Conditioned Retrieval Scoring (AUB-RET-01).

Safety Properties:
1. Scoring formula: Score = Lexical(query) + λ * predicate_match - μ * predicate_conflict.
2. Predicate scoring is deterministic and tie-broken by (-score, chunk_id).
3. Patients differing on a labelled predicate yield different top-1 nodes.
4. Unknown patient values yield neither match nor conflict.
5. Hand-computed scoring fixture verifies arithmetic independently.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.config import get_data_dir
from triagerag.contracts.enums import Consciousness
from triagerag.contracts.schemas import (
    Age,
    AgeUnit,
    AllergyEntry,
    IngredientStrength,
    Measured,
    MedicationEntry,
    Patient,
    Vitals,
)
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols_with_report
from triagerag.rag.predicates import PredicateEvalResult
from triagerag.rag.retrieve import (
    build_retrieval_context,
    retrieve_protocol_chunks,
)
from triagerag.rag.scoring import (
    calculate_node_predicate_score,
)


def _make_patient(**kwargs) -> Patient:
    """Build clean patient for retrieval scoring tests."""
    defaults = {
        "assessed_at": datetime.now(UTC),
        "age": Age(value=Decimal("45"), unit=AgeUnit.years),
        "sex": "male",
        "pregnancy": "not_applicable",
        "weight_kg": Measured[Decimal](value=Decimal("70.0"), source="measured"),
        "vitals": Vitals(
            heart_rate_bpm=Measured[int](value=75, source="measured"),
            systolic_bp_mmhg=Measured[int](value=125, source="measured"),
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


def test_hand_computed_scoring_fixture() -> None:
    """Verify hand-computed score calculation independently from the engine."""
    # Hand fixture setup:
    # Lexical score = 2.5000, lambda (match) = 1.0, mu (conflict) = 2.0
    # Node requires ["normal_or_high_systolic_bp"], contraindicated by ["low_systolic_bp"]
    lexical = 2.5000
    match_weight = 1.0
    conflict_weight = 2.0

    # Case 1: Normal BP (normal_or_high_systolic_bp=SATISFIED, low_systolic_bp=NOT_SATISFIED)
    evals_case1 = {
        "normal_or_high_systolic_bp": PredicateEvalResult.SATISFIED,
        "low_systolic_bp": PredicateEvalResult.NOT_SATISFIED,
    }
    score_1, match_1, conflict_1 = calculate_node_predicate_score(
        requires_predicates=("normal_or_high_systolic_bp",),
        contraindicated_by=("low_systolic_bp",),
        always_applicable=False,
        patient_evals=evals_case1,
        lexical_score=lexical,
        match_weight=match_weight,
        conflict_weight=conflict_weight,
    )
    # Expected: match = 1 (normal_bp), conflict = 0
    # Score = 2.5 + 1.0*1 - 2.0*0 = 3.5
    assert match_1 == 1
    assert conflict_1 == 0
    assert score_1 == 3.5

    # Case 2: Hypotensive (normal_or_high_systolic_bp=NOT_SATISFIED, low_systolic_bp=SATISFIED)
    evals_case2 = {
        "normal_or_high_systolic_bp": PredicateEvalResult.NOT_SATISFIED,
        "low_systolic_bp": PredicateEvalResult.SATISFIED,
    }
    score_2, match_2, conflict_2 = calculate_node_predicate_score(
        requires_predicates=("normal_or_high_systolic_bp",),
        contraindicated_by=("low_systolic_bp",),
        always_applicable=False,
        patient_evals=evals_case2,
        lexical_score=lexical,
        match_weight=match_weight,
        conflict_weight=conflict_weight,
    )
    # Expected: match = 0, conflict = 2 (not satisfied required + satisfied contraindication)
    # Score = 2.5 + 1.0*0 - 2.0*2 = -1.5
    assert match_2 == 0
    assert conflict_2 == 2
    assert score_2 == -1.5


def test_chest_pain_paired_patients_differ_on_top_node() -> None:
    """Two chest pain patients (normal BP vs hypotensive) must yield different top-1 nodes."""
    ctx = build_retrieval_context()
    report_ingest = ingest_protocols_with_report(data_dir=get_data_dir())
    index = BM25ClinicalIndex(report_ingest.chunks)

    # Patient A: Normal BP (systolic 130) -> prefers Nitroglycerin node (CHEST_PAIN_01_NODE_2)
    pat_norm = _make_patient(
        suspected_syndrome="chest_pain",
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=130, source="measured")),
    )
    res_a = retrieve_protocol_chunks(pat_norm, index, context=ctx)
    assert not res_a.abstained
    assert len(res_a.chunks) > 0

    # Patient B: Severe hypotension (systolic 80) -> prefers Fluid node (CHEST_PAIN_01_NODE_5)
    pat_hypo = _make_patient(
        suspected_syndrome="chest_pain",
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=80, source="measured")),
    )
    res_b = retrieve_protocol_chunks(pat_hypo, index, context=ctx)
    assert not res_b.abstained
    assert len(res_b.chunks) > 0

    assert res_a.chunks[0].chunk_id != res_b.chunks[0].chunk_id
    assert (
        res_b.chunks[0].legacy_id == "CHEST_PAIN_01_NODE_5"
        or "CHEST_PAIN_01_NODE_5" in res_b.chunks[0].aliases
    )


def test_anaphylaxis_paired_patients_differ_on_top_node() -> None:
    """Anaphylaxis patients (hypotensive shock vs active beta-blocker) yield different rankings."""
    ctx = build_retrieval_context()
    report_ingest = ingest_protocols_with_report(data_dir=get_data_dir())
    index = BM25ClinicalIndex(report_ingest.chunks)

    # Patient A: Severe hypotension (systolic 70)
    pat_shock = _make_patient(
        suspected_syndrome="anaphylaxis",
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=70, source="measured")),
    )
    res_a = retrieve_protocol_chunks(pat_shock, index, context=ctx)
    assert not res_a.abstained

    # Patient B: Normal BP but taking metoprolol
    pat_bb = _make_patient(
        suspected_syndrome="anaphylaxis",
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=125, source="measured")),
        medication_history_status="confirmed_list",
        medications=[
            MedicationEntry(
                raw_text="metoprolol 50mg daily",
                ingredients=[IngredientStrength(ingredient_id="metoprolol")],
                resolved=True,
            )
        ],
    )
    res_b = retrieve_protocol_chunks(pat_bb, index, context=ctx)
    assert not res_b.abstained

    node_4_a = next(
        i
        for i, c in enumerate(res_a.chunks)
        if (c.chunk_id == "ANAPHYLAXIS_01_NODE_4" or c.legacy_id == "ANAPHYLAXIS_01_NODE_4")
    )
    node_4_b = next(
        i
        for i, c in enumerate(res_b.chunks)
        if (c.chunk_id == "ANAPHYLAXIS_01_NODE_4" or c.legacy_id == "ANAPHYLAXIS_01_NODE_4")
    )
    assert node_4_b < node_4_a


def test_altered_mental_status_paired_patients_differ() -> None:
    """AMS patients (hypoglycemia vs normal glucose) yield different rankings."""
    ctx = build_retrieval_context()
    report_ingest = ingest_protocols_with_report(data_dir=get_data_dir())
    index = BM25ClinicalIndex(report_ingest.chunks)

    # Patient A: Severe hypoglycemia (glucose 40) -> prefers dextrose node (NODE_2)
    pat_hypo = _make_patient(
        suspected_syndrome="altered_mental_status",
        vitals=Vitals(
            blood_glucose_mg_dl=Measured[Decimal](value=Decimal("40.0"), source="measured")
        ),
    )
    res_a = retrieve_protocol_chunks(pat_hypo, index, context=ctx)
    assert not res_a.abstained

    # Patient B: Normal glucose (glucose 110) with altered consciousness
    pat_norm = _make_patient(
        suspected_syndrome="altered_mental_status",
        vitals=Vitals(
            blood_glucose_mg_dl=Measured[Decimal](value=Decimal("110.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.V, source="measured"),
        ),
    )
    res_b = retrieve_protocol_chunks(pat_norm, index, context=ctx)
    assert not res_b.abstained

    assert (
        res_a.chunks[0].legacy_id == "ALTERED_MENTAL_STATUS_01_NODE_2"
        or "ALTERED_MENTAL_STATUS_01_NODE_2" in res_a.chunks[0].aliases
    )
    assert res_b.chunks[0].legacy_id != "ALTERED_MENTAL_STATUS_01_NODE_2"


def test_hypoglycemia_paired_patients_differ() -> None:
    """Hypoglycemia patients (conscious oral route vs altered IV route) differ in ranking."""
    ctx = build_retrieval_context()
    report_ingest = ingest_protocols_with_report(data_dir=get_data_dir())
    index = BM25ClinicalIndex(report_ingest.chunks)

    # Patient A: Conscious alert -> conscious oral carb node (NODE_2) boosted
    pat_alert = _make_patient(
        suspected_syndrome="hypoglycemia",
        vitals=Vitals(
            blood_glucose_mg_dl=Measured[Decimal](value=Decimal("55.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
    )
    res_a = retrieve_protocol_chunks(pat_alert, index, context=ctx)
    assert not res_a.abstained

    # Patient B: Unresponsive / confused -> NODE_2 conscious oral carb not matched
    pat_unresp = _make_patient(
        suspected_syndrome="hypoglycemia",
        vitals=Vitals(
            blood_glucose_mg_dl=Measured[Decimal](value=Decimal("55.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.U, source="measured"),
        ),
    )
    res_b = retrieve_protocol_chunks(pat_unresp, index, context=ctx)
    assert not res_b.abstained

    node_2_a = next(
        i
        for i, c in enumerate(res_a.chunks)
        if (c.chunk_id == "HYPOGLYCEMIA_01_NODE_2" or c.legacy_id == "HYPOGLYCEMIA_01_NODE_2")
    )
    node_2_b = next(
        i
        for i, c in enumerate(res_b.chunks)
        if (c.chunk_id == "HYPOGLYCEMIA_01_NODE_2" or c.legacy_id == "HYPOGLYCEMIA_01_NODE_2")
    )
    assert node_2_a < node_2_b


def test_paediatric_sepsis_paired_patients_differ() -> None:
    """Paediatric sepsis patients (NKDA vs penicillin allergy) yield different rankings."""
    ctx = build_retrieval_context()
    report_ingest = ingest_protocols_with_report(data_dir=get_data_dir())
    index = BM25ClinicalIndex(report_ingest.chunks)

    # Patient A: Child aged 4 years with fever and tachycardia, NKDA -> NODE_1 ranks top
    pat_child = _make_patient(
        age=Age(value=Decimal("4"), unit=AgeUnit.years),
        suspected_syndrome="paediatric_sepsis",
        vitals=Vitals(
            temperature_c=Measured[Decimal](value=Decimal("39.2"), source="measured"),
            heart_rate_bpm=Measured[int](value=150, source="measured"),
        ),
    )
    res_a = retrieve_protocol_chunks(pat_child, index, context=ctx)
    assert not res_a.abstained

    # Patient B: Child aged 4 years with penicillin allergy -> NODE_2 matches
    pat_pen_allg = _make_patient(
        age=Age(value=Decimal("4"), unit=AgeUnit.years),
        suspected_syndrome="paediatric_sepsis",
        vitals=Vitals(
            temperature_c=Measured[Decimal](value=Decimal("38.0"), source="measured"),
            heart_rate_bpm=Measured[int](value=105, source="measured"),
        ),
        allergy_history_status="confirmed_list",
        allergies=[
            AllergyEntry(
                raw_substance="amoxicillin",
                normalized_allergen_id="amoxicillin",
                allergen_class="PENICILLINS",
                reaction_type="anaphylaxis_ige",
                resolved=True,
            )
        ],
    )
    res_b = retrieve_protocol_chunks(pat_pen_allg, index, context=ctx)
    assert not res_b.abstained

    node_2_a = next(
        i
        for i, c in enumerate(res_a.chunks)
        if (c.chunk_id == "PAED_SEPSIS_01_NODE_2" or c.legacy_id == "PAED_SEPSIS_01_NODE_2")
    )
    node_2_b = next(
        i
        for i, c in enumerate(res_b.chunks)
        if (c.chunk_id == "PAED_SEPSIS_01_NODE_2" or c.legacy_id == "PAED_SEPSIS_01_NODE_2")
    )
    assert node_2_b < node_2_a


def test_severe_asthma_paired_patients_differ() -> None:
    """Severe asthma patients (critical hypoxemic fatigue vs active beta-blocker) differ."""
    ctx = build_retrieval_context()
    report_ingest = ingest_protocols_with_report(data_dir=get_data_dir())
    index = BM25ClinicalIndex(report_ingest.chunks)

    # Patient A: Severe tachypnea + low SpO2 -> NODE_2 (critical fatigue) matches
    pat_crit = _make_patient(
        suspected_syndrome="severe_asthma",
        vitals=Vitals(
            respiratory_rate_bpm=Measured[int](value=34, source="measured"),
            spo2_percent=Measured[int](value=87, source="measured"),
        ),
    )
    res_a = retrieve_protocol_chunks(pat_crit, index, context=ctx)
    assert not res_a.abstained

    # Patient B: Mild tachypnea on beta-blocker -> NODE_3 (withhold beta-blocker) matches
    pat_bb = _make_patient(
        suspected_syndrome="severe_asthma",
        vitals=Vitals(
            respiratory_rate_bpm=Measured[int](value=22, source="measured"),
            spo2_percent=Measured[int](value=96, source="measured"),
        ),
        medication_history_status="confirmed_list",
        medications=[
            MedicationEntry(
                raw_text="atenolol 50mg daily",
                ingredients=[IngredientStrength(ingredient_id="atenolol")],
                resolved=True,
            )
        ],
    )
    res_b = retrieve_protocol_chunks(pat_bb, index, context=ctx)
    assert not res_b.abstained

    node_2_a = next(
        i
        for i, c in enumerate(res_a.chunks)
        if (c.chunk_id == "SEVERE_ASTHMA_01_NODE_2" or c.legacy_id == "SEVERE_ASTHMA_01_NODE_2")
    )
    node_2_b = next(
        i
        for i, c in enumerate(res_b.chunks)
        if (c.chunk_id == "SEVERE_ASTHMA_01_NODE_2" or c.legacy_id == "SEVERE_ASTHMA_01_NODE_2")
    )
    assert node_2_a < node_2_b

    node_3_a = next(
        i
        for i, c in enumerate(res_a.chunks)
        if (c.chunk_id == "SEVERE_ASTHMA_01_NODE_3" or c.legacy_id == "SEVERE_ASTHMA_01_NODE_3")
    )
    node_3_b = next(
        i
        for i, c in enumerate(res_b.chunks)
        if (c.chunk_id == "SEVERE_ASTHMA_01_NODE_3" or c.legacy_id == "SEVERE_ASTHMA_01_NODE_3")
    )
    assert node_3_b < node_3_a


def test_unknown_patient_vitals_neither_match_nor_conflict() -> None:
    """When vitals are unknown, predicate scoring introduces 0 match and 0 conflict."""
    evals_unknown = {
        "normal_or_high_systolic_bp": PredicateEvalResult.UNKNOWN,
        "low_systolic_bp": PredicateEvalResult.UNKNOWN,
    }
    score, match, conflict = calculate_node_predicate_score(
        requires_predicates=("normal_or_high_systolic_bp",),
        contraindicated_by=("low_systolic_bp",),
        always_applicable=False,
        patient_evals=evals_unknown,
        lexical_score=2.0,
        match_weight=1.0,
        conflict_weight=2.0,
    )
    assert match == 0
    assert conflict == 0
    assert score == 2.0


def test_deterministic_repeat_runs() -> None:
    """Running identical patient 5 times produces bit-identical scores and rankings."""
    ctx = build_retrieval_context()
    report_ingest = ingest_protocols_with_report(data_dir=get_data_dir())
    index = BM25ClinicalIndex(report_ingest.chunks)

    pat = _make_patient(
        suspected_syndrome="chest_pain",
        vitals=Vitals(systolic_bp_mmhg=Measured[int](value=84, source="measured")),
    )

    first_res = retrieve_protocol_chunks(pat, index, context=ctx)
    first_ids = [c.chunk_id for c in first_res.chunks]
    first_scores = [c.score for c in first_res.chunks]

    for _ in range(4):
        rep = retrieve_protocol_chunks(pat, index, context=ctx)
        assert [c.chunk_id for c in rep.chunks] == first_ids
        assert [c.score for c in rep.chunks] == first_scores
