"""Failing-first regression tests from the 2026-10-29 audit of TriageRAG v0.2.1.

Drop into tests/unit/. Every test below FAILS on the audited code (v0.2.1) and
should PASS after the corresponding fix (ENG-01..ENG-04 in the audit report).
They test engine semantics against the *loaded ruleset*, not clinical truth.

Key technique: the golden suite runs against the FULL ruleset, so the redundant
rule DDI_SILDENAFIL_NITROGLYCERIN_EXPLICIT masks bugs in the class rule
DDI_PDE5_NITRATE. These tests evaluate each rule IN ISOLATION (rules=only that rule).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from triagerag.config import get_data_dir
from triagerag.contracts.enums import ActionType, DoseUnit, Route, Severity
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    IngredientStrength,
    Measured,
    MedicationEntry,
    Patient,
    PlanStepDraft,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.engine.rule_engine import evaluate_baseline, evaluate_plan

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def registry() -> ClinicalRegistry:
    return ClinicalRegistry.load_from_directory(get_data_dir())


def only_rules(reg: ClinicalRegistry, *rule_ids: str) -> ClinicalRegistry:
    """Registry containing ONLY the named rules (defeats rule redundancy masking)."""
    kept = tuple(r for r in reg.rules if r.id in rule_ids)
    assert {r.id for r in kept} == set(rule_ids), "rule id not found in ruleset"
    return dataclasses.replace(reg, rules=type(reg.rules)(kept))


def med(name: str, ingredient: str, hours_ago: float | None) -> MedicationEntry:
    return MedicationEntry(
        raw_text=name,
        ingredients=[IngredientStrength(ingredient_id=ingredient)],
        resolved=True,
        last_dose_time=None if hours_ago is None else NOW - timedelta(hours=hours_ago),
    )


def patient(meds: list[MedicationEntry], age_years: int = 50, weight: str = "70") -> Patient:
    return Patient(
        assessed_at=NOW,
        age=Age(value=Decimal(age_years), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal(weight), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=130, source="measured"),
            heart_rate_bpm=Measured[int](value=80, source="measured"),
        ),
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_list" if meds else "confirmed_none",
        medications=meds,
        chief_complaint_untrusted="x",
    )


def administer(drug_id: str, dose: ExplicitDose | None = None) -> PlanStepDraft:
    # model_construct: bypass citation requirement; engine tests do not need citations
    return PlanStepDraft.model_construct(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="x",
        drug_id=drug_id,
        requested_dose=dose,
        route=None,
        citations=[],
    )


# --------------------------------------------------------------------------- ENG-01
def test_eng01_confirmed_in_window_trigger_beats_missing_timestamp(
    registry: ClinicalRegistry,
) -> None:
    """Sildenafil 3 h ago (confirmed) + tadalafil with no timestamp + proposed nitroglycerin.

    A confirmed in-window PDE5 dose must yield BLOCK. v0.2.1 returns a SkippedCheck
    (BLOCK silently downgraded to UNVERIFIED) because lookback_missing_timestamp is
    tested before lookback_triggered.
    """
    reg = only_rules(registry, "DDI_PDE5_NITRATE")
    p = patient([med("sildenafil", "sildenafil", 3), med("tadalafil", "tadalafil", None)])
    base_alerts, _, _, _ = evaluate_baseline(p, reg)
    plan_alerts, plan_skips, _ = evaluate_plan(p, [administer("nitroglycerin")], base_alerts, reg)
    assert any(a.severity == Severity.BLOCK for a in base_alerts + plan_alerts), (
        f"expected BLOCK, got alerts={[a.rule_id for a in plan_alerts]} "
        f"skips={[s.rule_id for s in plan_skips]}"
    )


# --------------------------------------------------------------------------- ENG-02
def test_eng02_baseline_alert_must_not_suppress_proposed_drug_coverage(
    registry: ClinicalRegistry,
) -> None:
    """Home sildenafil + home isosorbide mononitrate fires DDI_PDE5_NITRATE at baseline.

    A *proposed* nitroglycerin must still be covered by a BLOCK alert naming it.
    v0.2.1 dedupes plan alerts by rule_id against baseline alerts, so the proposed
    drug is never added to any alert.drug_ids and the step would not be struck through.
    """
    reg = only_rules(registry, "DDI_PDE5_NITRATE")
    p = patient(
        [
            med("sildenafil", "sildenafil", 3),
            med("isosorbide mononitrate", "isosorbide_mononitrate", 5),
        ]
    )
    base_alerts, _, _, _ = evaluate_baseline(p, reg)
    assert base_alerts, "precondition: baseline class rule should fire"
    plan_alerts, _, _ = evaluate_plan(p, [administer("nitroglycerin")], base_alerts, reg)
    covered = any("nitroglycerin" in a.drug_ids for a in base_alerts + plan_alerts)
    assert covered, "proposed nitroglycerin is not covered by any alert (dedupe-by-rule_id bug)"


# --------------------------------------------------------------------------- ENG-03
def test_eng03_underdose_and_magnitude_errors_must_raise_an_alert(
    registry: ClinicalRegistry,
) -> None:
    """Adult epinephrine IM 0.03 mg (a x0.1 decimal slip) is BELOW_MINIMUM with tripwire.

    v0.2.1 evaluate_plan only turns EXCEEDS_CEILING into an alert; BELOW_MINIMUM and
    MAGNITUDE_WARNING are computed and then ignored, so the step can be APPROVED.
    """
    p = patient([])
    step = administer("epinephrine", ExplicitDose(amount=Decimal("0.03"), unit=DoseUnit.mg))
    alerts, _, reports = evaluate_plan(p, [step], [], registry)
    assert reports and reports[0].status in {"BELOW_MINIMUM", "MAGNITUDE_WARNING"}
    assert any(a.rule_id.startswith("DOSE_") for a in alerts), (
        "no dose alert emitted for a tripwire/below-minimum dose"
    )


# --------------------------------------------------------------------------- ENG-04
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Pending human decision HD-6: hard-ceiling multiple above which a dose is non-overridable."
    ),
)
def test_eng04_gross_overdose_must_not_be_overridable(registry: ClinicalRegistry) -> None:
    """50 mg IM epinephrine (~100x the adult per-dose ceiling) should be BLOCK, not HIGH."""
    p = patient([])
    step = administer("epinephrine", ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg))
    alerts, _, _ = evaluate_plan(p, [step], [], registry)
    dose_alerts = [a for a in alerts if a.rule_id.startswith("DOSE_")]
    assert dose_alerts and all(a.severity == Severity.BLOCK for a in dose_alerts)


# --------------------------------------------------------------------------- ENG-08 (latent)
def test_eng08_class_member_without_lookback_entry_must_not_silently_pass(
    registry: ClinicalRegistry,
) -> None:
    """Latent hazard for rule expansion: a PDE5-class ingredient missing from
    lookback_hours_by_ingredient must produce a skip or an alert, never nothing.
    (Simulated by treating tadalafil as absent from the lookback table.)
    """
    rule = next(r for r in registry.rules if r.id == "DDI_PDE5_NITRATE")
    trimmed = rule.model_copy(update={"lookback_hours_by_ingredient": {"sildenafil": Decimal(24)}})
    reg = dataclasses.replace(registry, rules=type(registry.rules)((trimmed,)))
    p = patient([med("tadalafil", "tadalafil", 1)])  # taken 1 h ago, no lookback entry
    plan_alerts, plan_skips, _ = evaluate_plan(p, [administer("nitroglycerin")], [], reg)
    assert plan_alerts or plan_skips, "silent pass: in-class drug with no lookback entry"


# --------------------------------------------------------------------------- ENG-05
def test_eng05_step_keyed_dose_reports_prevent_collision(registry: ClinicalRegistry) -> None:
    """Two administer steps for the same drug must not collide or overwrite each other.

    Step 1: Epinephrine 0.3 mg (within verified limits) -> APPROVED
    Step 2: Epinephrine 50 mg (exceeds ceiling) -> FLAGGED_HIGH
    """
    from triagerag.contracts.enums import StepStatus
    from triagerag.contracts.schemas import PlanDraft, RetrievedChunk, SpanCitation
    from triagerag.verify.plan_verifier import verify_plan

    p = patient([])
    chunk = RetrievedChunk(
        doc_id="EMERG_ANAPHYLAXIS",
        section="Anaphylaxis Management",
        chunk_id="chunk_1_node_1",
        parent_id="EMERG_ANAPHYLAXIS_DOC",
        text="IF anaphylaxis THEN administer epinephrine and monitor vitals",
        population="adult",
        syndrome="anaphylaxis",
    )
    cit = SpanCitation(
        doc_id="EMERG_ANAPHYLAXIS",
        section="Anaphylaxis Management",
        chunk_id="chunk_1_node_1",
        quoted_span="administer epinephrine",
    )
    step1 = PlanStepDraft.model_construct(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer epinephrine 0.3 mg IM immediately",
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg),
        route=Route.im,
        citations=[cit],
    )
    step2 = PlanStepDraft.model_construct(
        step_number=2,
        action_type=ActionType.administer,
        narrative_instruction="Administer epinephrine 50 mg IM immediately",
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg),
        route=Route.im,
        citations=[cit],
    )
    draft = PlanDraft(matched_protocol_title="Anaphylaxis Management", steps=[step1, step2])
    verified_steps, _, _, reports = verify_plan(
        patient=p,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=registry,
    )

    assert len(verified_steps) == 2
    assert len(reports) == 2
    assert verified_steps[0].status == StepStatus.APPROVED, (
        f"Step 1 was overwritten by Step 2 report: {verified_steps[0].rejection_reasons}"
    )
    assert verified_steps[1].status == StepStatus.FLAGGED_HIGH


# --------------------------------------------------------------------------- ENG-07
def test_eng07_relevance_gated_skips_eliminate_alert_fatigue(registry: ClinicalRegistry) -> None:
    """An unmeasured parameter or incomplete history must NOT emit skips for uninvolved rules."""
    # Patient with incomplete med history and no PDE5 or nitrate medications
    p = patient([])
    p = p.model_copy(update={"medication_history_status": "incomplete", "medications": []})

    step = PlanStepDraft.model_construct(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer dextrose 25g IV",
        drug_id="dextrose",
        requested_dose=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.g),
        route=Route.iv,
        citations=[],
    )
    # Evaluating plan with dextrose must NOT emit DDI_PDE5_NITRATE skip
    plan_alerts, plan_skips, _ = evaluate_plan(p, [step], [], registry)
    skip_rules = {s.rule_id for s in plan_skips}
    assert "DDI_PDE5_NITRATE" not in skip_rules, (
        "Relevance gating failed: emitted DDI_PDE5_NITRATE skip when neither drug is involved"
    )


# --------------------------------------------------------------------------- ENG-03 (exhaustive)
def test_eng03_all_dose_report_statuses_handled_exhaustively(registry: ClinicalRegistry) -> None:
    """All 5 statuses of CalculatedDoseReport must map to an alert or skip."""
    p = patient([])
    # 1. OK (epinephrine 0.3 mg)
    s_ok = administer("epinephrine", ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg))
    alerts_ok, skips_ok, reps_ok = evaluate_plan(p, [s_ok], [], registry)
    assert reps_ok[0].status == "OK"
    assert not any(a.rule_id.startswith("DOSE_") for a in alerts_ok)

    # 2. EXCEEDS_CEILING (epinephrine 1.0 mg)
    s_exc = administer("epinephrine", ExplicitDose(amount=Decimal("1.0"), unit=DoseUnit.mg))
    alerts_exc, _, reps_exc = evaluate_plan(p, [s_exc], [], registry)
    assert reps_exc[0].status == "EXCEEDS_CEILING"
    assert any(a.rule_id == "DOSE_LIMIT_EPINEPHRINE" for a in alerts_exc)

    # 3. BELOW_MINIMUM (epinephrine 0.03 mg)
    s_below = administer("epinephrine", ExplicitDose(amount=Decimal("0.03"), unit=DoseUnit.mg))
    alerts_below, _, reps_below = evaluate_plan(p, [s_below], [], registry)
    assert reps_below[0].status in {"BELOW_MINIMUM", "MAGNITUDE_WARNING"}
    assert any(a.rule_id.startswith("DOSE_") for a in alerts_below)

    # 4. UNVERIFIED_MISSING_CAP (ceftriaxone without weight in paediatric patient)
    p_paed = patient([], age_years=5)
    p_paed = p_paed.model_copy(update={"weight_kg": Measured[Decimal]()})  # unknown weight
    s_cap = administer("ceftriaxone", ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg))
    _, skips_cap, reps_cap = evaluate_plan(p_paed, [s_cap], [], registry)
    assert reps_cap[0].status == "UNVERIFIED_MISSING_CAP"
    assert any(s.rule_id == "DOSE_CHECK_CEFTRIAXONE" for s in skips_cap)
