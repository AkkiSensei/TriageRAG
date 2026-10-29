"""Differential testing for TriageRAG rule engine (ENG-09, WP-0).

Compares production evaluate_baseline against an independent, deliberately naïve
reference interpreter over Hypothesis-generated patients.
Validates that 0 divergences occur across >=1,000 synthetic patient permutations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from triagerag.config import get_data_dir
from triagerag.contracts.enums import AgeUnit
from triagerag.contracts.rules_schema import (
    AllergyCrossReactivityRule,
    ClassInteractionRule,
    DuplicationRule,
    PairRule,
    PopulationRule,
    VitalsInterlockRule,
)
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    IngredientStrength,
    Measured,
    MedicationEntry,
    Patient,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.engine.rule_engine import evaluate_baseline

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
REGISTRY = ClinicalRegistry.load_from_directory(get_data_dir())

AVAILABLE_DRUGS = sorted(REGISTRY.formulary_drugs.keys())
AVAILABLE_ALLERGENS = ["penicillin", "amoxicillin", "ampicillin", "cephalexin", "aspirin"]
REACTION_TYPES = ["anaphylaxis_ige", "severe_cutaneous_scar", "unknown", "mild_rash"]


def naive_reference_baseline(
    patient: Patient,
    registry: ClinicalRegistry,
) -> tuple[set[str], set[str]]:
    """Deliberately simple, independent reference implementation of rule evaluation semantics.

    Returns:
        (alert_rule_ids, skip_rule_ids)
    """
    # 1. Resolve active drugs and active classes naively
    active_drugs: set[str] = set()
    active_classes: set[str] = set()
    for m in patient.medications:
        if m.resolved:
            d_name = m.raw_text.strip().lower()
            active_drugs.add(d_name)
            drug = registry.get_drug(d_name)
            if drug:
                active_drugs.add(drug.drug_id)
                active_drugs.update(drug.ingredient_ids)
                active_classes.update(drug.classes)
            for ing in m.ingredients:
                active_drugs.add(ing.ingredient_id)
                active_classes.update(registry.get_classes_for_ingredient(ing.ingredient_id))

    alert_ids: set[str] = set()
    skip_ids: set[str] = set()

    med_unresolved = patient.medication_history_status in (
        "incomplete",
        "unknown_unobtainable",
    ) or any(not m.resolved for m in patient.medications)
    allergy_unresolved = patient.allergy_history_status in (
        "incomplete",
        "unknown_unobtainable",
    ) or any(not a.resolved for a in patient.allergies)

    for rule in registry.rules:
        # Check rule applicability to patient
        if isinstance(rule, PairRule):
            is_rel = (
                rule.drug_a in active_drugs
                or rule.drug_b in active_drugs
                or (med_unresolved and "medications" in (rule.requires_fields or []))
            )
            if not is_rel:
                continue
            if med_unresolved and "medications" in (rule.requires_fields or []):
                skip_ids.add(rule.id)
            elif rule.drug_a in active_drugs and rule.drug_b in active_drugs:
                alert_ids.add(rule.id)

        elif isinstance(rule, ClassInteractionRule):
            is_rel = (
                rule.class_a in active_classes
                or rule.class_b in active_classes
                or (med_unresolved and "medications" in (rule.requires_fields or []))
            )
            if not is_rel:
                continue
            if med_unresolved and "medications" in (rule.requires_fields or []):
                skip_ids.add(rule.id)
            elif rule.class_a in active_classes and rule.class_b in active_classes:
                if rule.lookback_hours_by_ingredient:
                    triggered = False
                    missing_ts = False
                    missing_entry = False
                    for m in patient.medications:
                        for ing in m.ingredients:
                            ing_id = ing.ingredient_id
                            classes = registry.get_classes_for_ingredient(ing_id)
                            if rule.class_a in classes or rule.class_b in classes:
                                if ing_id in rule.lookback_hours_by_ingredient:
                                    limit = rule.lookback_hours_by_ingredient[ing_id]
                                    if m.last_dose_time is None:
                                        missing_ts = True
                                    else:
                                        elapsed = (
                                            patient.assessed_at - m.last_dose_time
                                        ).total_seconds() / 3600.0
                                        if Decimal(str(elapsed)) <= limit:
                                            triggered = True
                                else:
                                    missing_entry = True
                    # Confirmed trigger beats missing timestamp (ENG-01)
                    if triggered:
                        alert_ids.add(rule.id)
                    elif missing_ts or missing_entry:
                        skip_ids.add(rule.id)
                else:
                    alert_ids.add(rule.id)

        elif isinstance(rule, DuplicationRule):
            is_rel = rule.class_name in active_classes or (
                med_unresolved and "medications" in (rule.requires_fields or [])
            )
            if not is_rel:
                continue
            if med_unresolved and "medications" in (rule.requires_fields or []):
                skip_ids.add(rule.id)
            else:
                # Count distinct drugs in class
                in_class = {
                    d
                    for d in active_drugs
                    if rule.class_name in registry.get_classes_for_ingredient(d)
                }
                for d in active_drugs:
                    cand = registry.get_drug(d)
                    if cand and rule.class_name in cand.classes:
                        in_class.add(cand.drug_id)
                if len(in_class) >= 2:
                    alert_ids.add(rule.id)

        elif isinstance(rule, VitalsInterlockRule):
            is_rel = rule.drug_id in active_drugs
            if not is_rel:
                continue
            if rule.threshold_value is None and rule.threshold_str is None:
                skip_ids.add(rule.id)
                continue
            val = getattr(patient.vitals, rule.vital_name, None)
            if val is None or getattr(val, "source", None) == "unknown":
                skip_ids.add(rule.id)
            else:
                num = getattr(val, "value", None)
                if num is not None and rule.threshold_value is not None:
                    dec_val = Decimal(str(num))
                    thresh = rule.threshold_value
                    if (
                        rule.operator == "lt"
                        and dec_val < thresh
                        or rule.operator == "lte"
                        and dec_val <= thresh
                        or rule.operator == "gt"
                        and dec_val > thresh
                        or rule.operator == "gte"
                        and dec_val >= thresh
                        or rule.operator == "eq"
                        and dec_val == thresh
                    ):
                        alert_ids.add(rule.id)

        elif isinstance(rule, PopulationRule):
            is_rel = rule.drug_id in active_drugs
            if not is_rel:
                continue
            if "pregnancy" in (rule.requires_fields or []) and patient.pregnancy == "unknown":
                skip_ids.add(rule.id)
            elif (
                rule.contraindicated_pregnancy
                and patient.pregnancy == "yes"
                or (
                    rule.contraindicated_population
                    and patient.age.population_category == rule.contraindicated_population
                )
            ):
                alert_ids.add(rule.id)

        elif isinstance(rule, AllergyCrossReactivityRule):
            is_rel = rule.target_class in active_classes or (
                allergy_unresolved and "allergies" in (rule.requires_fields or [])
            )
            if not is_rel:
                continue
            if allergy_unresolved and "allergies" in (rule.requires_fields or []):
                skip_ids.add(rule.id)
            else:
                rule_alert = False
                rule_skip = False
                for a in patient.allergies:
                    a_sub = a.normalized_allergen_id or a.raw_substance.lower()
                    a_classes = set(registry.get_classes_for_ingredient(a_sub))
                    if a.allergen_class:
                        a_classes.add(a.allergen_class)
                    if a_sub in registry.formulary_drugs:
                        a_classes.update(registry.formulary_drugs[a_sub].classes)

                    if rule.allergen_class in a_classes:
                        if (
                            a.reaction_type in rule.reaction_types
                            or "unknown" in rule.reaction_types
                        ) and rule.target_class in active_classes:
                            rule_alert = True
                            break
                        elif a.reaction_type == "unknown" and "unknown" not in rule.reaction_types:
                            rule_skip = True

                if rule_alert:
                    alert_ids.add(rule.id)
                elif rule_skip:
                    skip_ids.add(rule.id)

    return alert_ids, skip_ids


# --------------------------------------------------------------------------- Hypothesis Generator
@st.composite
def patient_strategy(draw: st.DrawFn) -> Patient:
    age_val = draw(st.integers(min_value=1, max_value=90))
    sex = draw(st.sampled_from(["male", "female"]))
    preg = "not_applicable" if sex == "male" else draw(st.sampled_from(["yes", "no", "unknown"]))
    weight = draw(st.sampled_from(["50", "70", "85", "100"]))

    # Meds
    chosen_drugs = draw(
        st.lists(
            st.sampled_from(AVAILABLE_DRUGS),
            unique=True,
            max_size=3,
        )
    )
    med_list: list[MedicationEntry] = []
    for d in chosen_drugs:
        hours_ago = draw(st.sampled_from([None, 2.0, 10.0, 24.0, 48.0, 72.0]))
        med_list.append(
            MedicationEntry(
                raw_text=d,
                ingredients=[IngredientStrength(ingredient_id=d)],
                resolved=True,
                last_dose_time=None if hours_ago is None else NOW - timedelta(hours=hours_ago),
            )
        )

    # Allergies
    chosen_allergens = draw(
        st.lists(
            st.sampled_from(AVAILABLE_ALLERGENS),
            unique=True,
            max_size=2,
        )
    )
    allergy_list: list[AllergyEntry] = []
    for a in chosen_allergens:
        rx = draw(st.sampled_from(REACTION_TYPES))
        allergy_list.append(
            AllergyEntry(
                raw_substance=a,
                normalized_allergen_id=a,
                reaction_type=rx,  # type: ignore[arg-type]
                resolved=True,
            )
        )

    sbp_val = draw(st.sampled_from([None, 85, 100, 120, 150]))
    hr_val = draw(st.sampled_from([None, 45, 60, 80, 110]))

    return Patient(
        assessed_at=NOW,
        age=Age(value=Decimal(age_val), unit=AgeUnit.years),
        sex=sex,  # type: ignore[arg-type]
        pregnancy=preg,  # type: ignore[arg-type]
        weight_kg=Measured[Decimal](value=Decimal(weight), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=(
                Measured[int]()
                if sbp_val is None
                else Measured[int](value=sbp_val, source="measured")
            ),
            heart_rate_bpm=(
                Measured[int]()
                if hr_val is None
                else Measured[int](value=hr_val, source="measured")
            ),
        ),
        allergy_history_status="confirmed_list" if allergy_list else "confirmed_none",
        allergies=allergy_list,
        medication_history_status="confirmed_list" if med_list else "confirmed_none",
        medications=med_list,
        chief_complaint_untrusted="differential_test",
    )


@settings(max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(p=patient_strategy())
def test_differential_engine_vs_reference_interpreter_1000_cases(p: Patient) -> None:
    """Differential property test asserting 0 divergences across >=1,000 synthetic patients."""
    prod_alerts, prod_skips, _, _ = evaluate_baseline(p, REGISTRY)
    prod_alert_ids = {a.rule_id for a in prod_alerts}
    prod_skip_ids = {s.rule_id for s in prod_skips}

    ref_alert_ids, ref_skip_ids = naive_reference_baseline(p, REGISTRY)

    assert prod_alert_ids == ref_alert_ids, (
        f"Alert divergence on patient:\n"
        f"Meds: {[m.raw_text for m in p.medications]}\n"
        f"Allergies: {[a.raw_substance for a in p.allergies]}\n"
        f"Prod alerts: {sorted(prod_alert_ids)}\n"
        f"Ref alerts:  {sorted(ref_alert_ids)}\n"
        f"Diff: {prod_alert_ids ^ ref_alert_ids}"
    )
    assert prod_skip_ids == ref_skip_ids, (
        f"Skip divergence on patient:\n"
        f"Prod skips: {sorted(prod_skip_ids)}\n"
        f"Ref skips:  {sorted(ref_skip_ids)}\n"
        f"Diff: {prod_skip_ids ^ ref_skip_ids}"
    )
