"""Unit and property tests for Fix Gate G1: Grounding soundness (FG-01, FG-16).

Safety Properties (FG-01, FG-16, Rules R1, R2, R3):
1. Structural clause-scoped (action, drug_id) binding: drug and action cue must be bound in the
   same clause, not merely co-occurring anywhere in the chunk.
2. Mixed-polarity node in chest_pain.md ('THEN withhold metoprolol and initiate intravenous fluid
   volume resuscitation.') rejects 'administer metoprolol' with ACTION_POLARITY_MISMATCH while
   accepting 'withhold metoprolol'.
3. Negation within 3 tokens before an action cue ('do not give', 'never administer', 'avoid')
   flips polarity to withhold.
4. Unparsed clauses mentioning a formulary drug without a bindable cue fail closed and cannot
   support an administer or withhold step.
5. Non-drug steps (diagnostic, monitor, maneuver) require action-verb binding and minimum
   THEN-clause span coverage, with stopword-filtered content overlap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

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
from triagerag.verify.citations import verify_citation, verify_step_support
from triagerag.verify.plan_verifier import verify_plan


def _make_patient() -> Patient:
    return Patient(
        assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("55"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=88, source="measured"),
            systolic_bp_mmhg=Measured[int](value=130, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
    )


def _mixed_chest_pain_node5() -> RetrievedChunk:
    return RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_5",
        parent_id="CHEST_PAIN_01",
        text=(
            "5. IF hypotension or bradycardia is observed:\n"
            "   THEN withhold metoprolol and initiate intravenous fluid volume resuscitation."
        ),
        population="adult",
        syndrome="chest_pain",
    )


def test_administer_withheld_drug_in_mixed_node_rejected() -> None:
    """FG-01: 'administer metoprolol' citing chest_pain node 5 must be rejected."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    patient = _make_patient()
    node5 = _mixed_chest_pain_node5()

    draft = PlanDraft(
        matched_protocol_title="Acute Coronary Syndromes Screening",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                narrative_instruction=(
                    "Initiate intravenous therapy and administer beta-blocker for resuscitation"
                ),
                drug_id="metoprolol",
                requested_dose=ExplicitDose(amount=Decimal("5"), unit=DoseUnit.mg),
                route=Route.iv,
                citations=[
                    SpanCitation(
                        doc_id="EMERG_CHEST_PAIN",
                        section="Acute Coronary Syndromes Screening",
                        chunk_id="CHEST_PAIN_01_NODE_5",
                        quoted_span=(
                            "THEN withhold metoprolol and initiate intravenous fluid "
                            "volume resuscitation."
                        ),
                    )
                ],
            )
        ],
    )
    v_steps, _, _, _ = verify_plan(
        patient=patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[node5],
        registry=registry,
    )
    assert v_steps[0].status == StepStatus.CITATION_UNVERIFIED
    assert v_steps[0].citation_verified is False
    assert v_steps[0].support_reason is not None
    assert "ACTION_POLARITY_MISMATCH" in v_steps[0].support_reason


def test_withhold_drug_in_mixed_node_accepted() -> None:
    """FG-01: 'withhold metoprolol' citing chest_pain node 5 must be APPROVED."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    patient = _make_patient()
    node5 = _mixed_chest_pain_node5()

    draft = PlanDraft(
        matched_protocol_title="Acute Coronary Syndromes Screening",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.withhold,
                narrative_instruction=(
                    "Withhold beta-blocker therapy and initiate intravenous fluid resuscitation"
                ),
                drug_id="metoprolol",
                citations=[
                    SpanCitation(
                        doc_id="EMERG_CHEST_PAIN",
                        section="Acute Coronary Syndromes Screening",
                        chunk_id="CHEST_PAIN_01_NODE_5",
                        quoted_span=(
                            "THEN withhold metoprolol and initiate intravenous fluid "
                            "volume resuscitation."
                        ),
                    )
                ],
            )
        ],
    )
    v_steps, _, _, _ = verify_plan(
        patient=patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[node5],
        registry=registry,
    )
    assert v_steps[0].status == StepStatus.APPROVED
    assert v_steps[0].citation_verified is True


def test_negated_give_is_withhold_polarity() -> None:
    """FG-01: 'do not give nitroglycerin' has withhold polarity; administer step is rejected."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_99",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF hypotension is present:\n"
            "   THEN do not give nitroglycerin under any circumstances."
        ),
        population="adult",
        syndrome="chest_pain",
    )
    admin_step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Give sublingual vasodilator under clinical supervision",
        drug_id="nitroglycerin",
        requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
        route=Route.sublingual,
        citations=[
            SpanCitation(
                doc_id="EMERG_CHEST_PAIN",
                section="Acute Coronary Syndromes Screening",
                chunk_id="CHEST_PAIN_01_NODE_99",
                quoted_span="THEN do not give nitroglycerin under any circumstances.",
            )
        ],
    )
    ok_adm, reason_adm = verify_step_support(admin_step, [chunk], registry)
    assert ok_adm is False
    assert "ACTION_POLARITY_MISMATCH" in reason_adm

    withhold_step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.withhold,
        narrative_instruction="Do not give vasodilator under any circumstances",
        drug_id="nitroglycerin",
        citations=admin_step.citations,
    )
    ok_wh, _ = verify_step_support(withhold_step, [chunk], registry)
    assert ok_wh is True


def test_two_drug_node_binds_cue_to_correct_drug() -> None:
    """FG-01: 'give epinephrine; avoid metoprolol' binds each drug to its own clause polarity."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    chunk = RetrievedChunk(
        doc_id="EMERG_ANAPHYLAXIS",
        section="Acute Airway & Hemodynamic Interventions",
        chunk_id="ANAPHYLAXIS_01_NODE_99",
        parent_id="ANAPHYLAXIS_01",
        text=(
            "1. IF anaphylactic shock occurs:\n"
            "   THEN give epinephrine intramuscularly; avoid metoprolol completely."
        ),
        population="adult",
        syndrome="anaphylaxis",
    )
    cit = [
        SpanCitation(
            doc_id="EMERG_ANAPHYLAXIS",
            section="Acute Airway & Hemodynamic Interventions",
            chunk_id="ANAPHYLAXIS_01_NODE_99",
            quoted_span="THEN give epinephrine intramuscularly; avoid metoprolol completely.",
        )
    ]

    step_bad = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer beta-blocker intramuscularly",
        drug_id="metoprolol",
        requested_dose=ExplicitDose(amount=Decimal("5"), unit=DoseUnit.mg),
        route=Route.iv,
        citations=cit,
    )
    ok_bad, reason_bad = verify_step_support(step_bad, [chunk], registry)
    assert ok_bad is False
    assert "ACTION_POLARITY_MISMATCH" in reason_bad

    step_good = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Give first-line agent intramuscularly",
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
        route=Route.im,
        citations=cit,
    )
    ok_good, _ = verify_step_support(step_good, [chunk], registry)
    assert ok_good is True


def test_cue_in_other_clause_does_not_support() -> None:
    """FG-01: 'withhold metoprolol. Separately, give epinephrine.' rejects administer metoprolol."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_98",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF cardiogenic shock is suspected:\n"
            "   THEN withhold metoprolol. Separately, give epinephrine infusion."
        ),
        population="adult",
        syndrome="chest_pain",
    )
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Give beta-blocker infusion for cardiogenic shock",
        drug_id="metoprolol",
        requested_dose=ExplicitDose(amount=Decimal("5"), unit=DoseUnit.mg),
        route=Route.iv,
        citations=[
            SpanCitation(
                doc_id="EMERG_CHEST_PAIN",
                section="Acute Coronary Syndromes Screening",
                chunk_id="CHEST_PAIN_01_NODE_98",
                quoted_span="THEN withhold metoprolol. Separately, give epinephrine infusion.",
            )
        ],
    )
    ok, reason = verify_step_support(step, [chunk], registry)
    assert ok is False
    assert "ACTION_POLARITY_MISMATCH" in reason


_CACHED_REGISTRY = ClinicalRegistry.load_from_directory(get_data_dir())


@settings(max_examples=500, deadline=None)
@given(
    drug_id=st.sampled_from(
        [
            "epinephrine",
            "nitroglycerin",
            "metoprolol",
            "salbutamol",
            "dextrose",
            "ceftriaxone",
            "amoxicillin",
        ]
    ),
    admin_verb=st.sampled_from(["administer", "give", "initiate", "infuse", "inject"]),
    withhold_verb=st.sampled_from(["withhold", "avoid", "discontinue", "stop", "do not give"]),
)
def test_polarity_flip_metamorphic(drug_id: str, admin_verb: str, withhold_verb: str) -> None:
    """FG-01 Hypothesis (500 examples): Swapping administer<->withhold verb flips support."""
    registry = _CACHED_REGISTRY

    admin_chunk = RetrievedChunk(
        doc_id="SYN_DOC",
        section="Test Section",
        chunk_id="SYN_01_NODE_1",
        parent_id="SYN_01",
        text=f"1. IF clinical indication present:\n   THEN {admin_verb} {drug_id} immediately.",
        population="adult",
        syndrome="chest_pain",
    )
    withhold_chunk = RetrievedChunk(
        doc_id="SYN_DOC",
        section="Test Section",
        chunk_id="SYN_01_NODE_1",
        parent_id="SYN_01",
        text=f"1. IF clinical indication present:\n   THEN {withhold_verb} {drug_id} immediately.",
        population="adult",
        syndrome="chest_pain",
    )

    admin_step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Perform immediate medication administration",
        drug_id=drug_id,
        requested_dose=ExplicitDose(amount=Decimal("1"), unit=DoseUnit.mg),
        route=Route.iv,
        citations=[
            SpanCitation(
                doc_id="SYN_DOC",
                section="Test Section",
                chunk_id="SYN_01_NODE_1",
                quoted_span=f"THEN {admin_verb} {drug_id} immediately.",
            )
        ],
    )
    withhold_step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.withhold,
        narrative_instruction="Withhold medication immediately",
        drug_id=drug_id,
        citations=[
            SpanCitation(
                doc_id="SYN_DOC",
                section="Test Section",
                chunk_id="SYN_01_NODE_1",
                quoted_span=f"THEN {withhold_verb} {drug_id} immediately.",
            )
        ],
    )

    ok_adm_on_adm, _ = verify_step_support(admin_step, [admin_chunk], registry)
    ok_adm_on_wh, _ = verify_step_support(admin_step, [withhold_chunk], registry)
    ok_wh_on_wh, _ = verify_step_support(withhold_step, [withhold_chunk], registry)
    ok_wh_on_adm, _ = verify_step_support(withhold_step, [admin_chunk], registry)

    assert ok_adm_on_adm is True
    assert ok_adm_on_wh is False
    assert ok_wh_on_wh is True
    assert ok_wh_on_adm is False


def test_unparsed_clause_with_drug_cannot_support() -> None:
    """FG-01: Clause mentioning a formulary drug without a bindable action cue fails closed."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_97",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF baseline telemetry is reviewed:\n"
            "   THEN metoprolol receptor pharmacology is documented in reference notes."
        ),
        population="adult",
        syndrome="chest_pain",
    )
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Document receptor pharmacology in reference notes",
        drug_id="metoprolol",
        requested_dose=ExplicitDose(amount=Decimal("5"), unit=DoseUnit.mg),
        route=Route.iv,
        citations=[
            SpanCitation(
                doc_id="EMERG_CHEST_PAIN",
                section="Acute Coronary Syndromes Screening",
                chunk_id="CHEST_PAIN_01_NODE_97",
                quoted_span=(
                    "THEN metoprolol receptor pharmacology is documented in reference notes."
                ),
            )
        ],
    )
    ok, reason = verify_step_support(step, [chunk], registry)
    assert ok is False
    assert "UNPARSED_DRUG_CLAUSE" in reason


def test_diagnostic_step_requires_action_binding() -> None:
    """FG-16: Non-drug step (diagnostic/monitor/maneuver) requires matching action verb binding."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_1",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF the adult patient reports acute ischemic chest discomfort:\n"
            "   THEN obtain immediate 12-lead electrocardiogram and attach continuous "
            "cardiac monitor."
        ),
        population="adult",
        syndrome="chest_pain",
    )
    # Narrative shares content nouns ('12-lead electrocardiogram', 'continuous cardiac')
    # but has NO bound non-drug action verb matching the THEN clause ('obtain', 'attach', 'monitor')
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.diagnostic,
        narrative_instruction=(
            "Archive historical 12-lead electrocardiogram billing records for "
            "continuous cardiac audit"
        ),
        citations=[
            SpanCitation(
                doc_id="EMERG_CHEST_PAIN",
                section="Acute Coronary Syndromes Screening",
                chunk_id="CHEST_PAIN_01_NODE_1",
                quoted_span=(
                    "THEN obtain immediate 12-lead electrocardiogram and attach continuous "
                    "cardiac monitor."
                ),
            )
        ],
    )
    ok, reason = verify_step_support(step, [chunk], registry)
    assert ok is False
    assert "NON_DRUG_ACTION_MISMATCH" in reason


def test_generic_word_overlap_insufficient() -> None:
    """FG-16: Sharing only generic stopwords/boilerplate fails the content-token overlap gate."""
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_1",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF the adult patient reports acute ischemic chest discomfort:\n"
            "   THEN obtain immediate 12-lead electrocardiogram and attach continuous "
            "cardiac monitor."
        ),
        population="adult",
        syndrome="chest_pain",
    )
    cit = SpanCitation(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_1",
        quoted_span=(
            "THEN obtain immediate 12-lead electrocardiogram and attach continuous cardiac monitor."
        ),
    )
    # Shares 'the', 'and', 'to', 'for', 'in', 'with', 'patient' -> stopwords only!
    ok, overlap, reason = verify_citation(
        cit,
        [chunk],
        "The patient is to be in the room and with the family for comfort",
    )
    assert ok is False
    assert overlap < 0.15
    assert reason is not None


def test_span_must_cover_then_clause() -> None:
    """FG-16: Citation quoting only IF condition (0% of THEN clause) is rejected."""
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_1",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF the adult patient reports acute ischemic chest discomfort:\n"
            "   THEN obtain immediate 12-lead electrocardiogram and attach continuous "
            "cardiac monitor."
        ),
        population="adult",
        syndrome="chest_pain",
    )
    cit = SpanCitation(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_1",
        quoted_span="IF the adult patient reports acute ischemic chest discomfort",
    )
    ok, _, reason = verify_citation(
        cit,
        [chunk],
        "Assess acute ischemic chest discomfort",
    )
    assert ok is False
    assert reason is not None
    assert "THEN_CLAUSE_COVERAGE" in reason


def test_non_drug_step_with_no_action_verbs_in_chunk_fails_closed() -> None:
    """N2: Non-drug step citing a THEN clause with NO verified action verbs must fail closed."""
    registry = ClinicalRegistry.load_from_directory(get_data_dir())
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_98",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF telemetry review is completed:\n"
            "   THEN standard protocol references and documentation guidelines apply."
        ),
        population="adult",
        syndrome="chest_pain",
    )
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.diagnostic,
        narrative_instruction="Perform comprehensive diagnostic telemetry review",
        citations=[
            SpanCitation(
                doc_id="EMERG_CHEST_PAIN",
                section="Acute Coronary Syndromes Screening",
                chunk_id="CHEST_PAIN_01_NODE_98",
                quoted_span="THEN standard protocol references and documentation guidelines apply.",
            )
        ],
    )
    ok, reason = verify_step_support(step, [chunk], registry)
    assert ok is False
    assert "NON_DRUG_NO_ACTION_VERBS" in reason


def test_clause_parser_binds_multiple_occurrences_of_same_drug() -> None:
    """P2: parse_clause_drug_actions binds all occurrences of a drug mentioned repeatedly."""
    from triagerag.normalize.clause_parser import parse_clause_drug_actions

    clause = "give epinephrine with repeat epinephrine in 5 minutes"
    actions = parse_clause_drug_actions(clause, enable_clause_split=False)
    epi_actions = [a for a in actions if a.drug_id == "epinephrine"]
    assert len(epi_actions) == 2
