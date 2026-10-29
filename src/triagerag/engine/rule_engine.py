"""Deterministic, pure clinical rule evaluation engine.

Safety Property (Rules R1, R2, R11, R12):
Evaluates baseline patient state (Pass 1) and proposed plan steps (Pass 2).
Checks requires_fields first. Missing, unknown, or incomplete data emits SkippedCheck
and prevents false clearance.
Withhold steps are never evaluated as administrations.
Alerts are deterministically ordered by severity (BLOCK > HIGH > MODERATE > INFO) then rule_id.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from triagerag.contracts.enums import (
    ActionType,
    RuleStatus,
    Severity,
)
from triagerag.contracts.rules_schema import (
    AllergyCrossReactivityRule,
    ClassInteractionRule,
    DuplicationRule,
    PairRule,
    PopulationRule,
    VitalsInterlockRule,
)
from triagerag.contracts.schemas import (
    Alert,
    CalculatedDoseReport,
    PlanStepDraft,
    SkippedCheck,
)
from triagerag.engine.dose_engine import verify_cumulative_daily_exposure, verify_dose

if TYPE_CHECKING:
    from triagerag.contracts.rules_schema import ClinicalRule
    from triagerag.contracts.schemas import Patient
    from triagerag.engine.registry import ClinicalRegistry

SEVERITY_ORDER: dict[Severity, int] = {
    Severity.BLOCK: 0,
    Severity.HIGH: 1,
    Severity.MODERATE: 2,
    Severity.INFO: 3,
}


def _sort_alerts(alerts: list[Alert]) -> list[Alert]:
    """Sort alerts deterministically by severity priority then rule_id."""
    return sorted(alerts, key=lambda a: (SEVERITY_ORDER.get(a.severity, 99), a.rule_id))


def _extract_patient_vital(patient: Patient, vital_name: str) -> Any:
    """Extract a vital sign value or None if unknown."""
    v = patient.vitals
    vital_attr = getattr(v, vital_name, None)
    if vital_attr is None:
        return None
    if getattr(vital_attr, "source", None) == "unknown":
        return None
    return getattr(vital_attr, "value", None)


def _get_active_drug_identifiers(patient: Patient, registry: ClinicalRegistry) -> set[str]:
    """Get all normalized drug IDs and ingredient IDs from active patient medications."""
    identifiers: set[str] = set()
    for med in patient.medications:
        if med.resolved:
            resolved_key = (med.suggestion or med.raw_text).strip().lower()
            identifiers.add(resolved_key)
            if resolved_key in registry.formulary_drugs:
                drug = registry.formulary_drugs[resolved_key]
                identifiers.add(drug.drug_id)
                for ing in drug.ingredient_ids:
                    identifiers.add(ing)
            if resolved_key in registry.aliases:
                alias = registry.aliases[resolved_key]
                for ing in alias.ingredient_ids:
                    identifiers.add(ing)
            for ing_str in med.ingredients:
                identifiers.add(ing_str.ingredient_id)
    return identifiers


def _get_active_classes(patient: Patient, registry: ClinicalRegistry) -> set[str]:
    """Get all pharmacological classes present in active patient medications."""
    classes: set[str] = set()
    for med in patient.medications:
        if med.resolved:
            for ing in med.ingredients:
                for cls in registry.get_classes_for_ingredient(ing.ingredient_id):
                    classes.add(cls)
            med_key = med.raw_text.strip().lower()
            if med_key in registry.formulary_drugs:
                for cls in registry.formulary_drugs[med_key].classes:
                    classes.add(cls)
            if med_key in registry.aliases:
                for alias_ing_id in registry.aliases[med_key].ingredient_ids:
                    for cls in registry.get_classes_for_ingredient(alias_ing_id):
                        classes.add(cls)
    return classes


def _is_rule_relevant(
    rule: ClinicalRule,
    active_drugs: set[str],
    active_classes: set[str],
    patient: Patient,
    registry: ClinicalRegistry,
    proposed_drugs: set[str] | None = None,
) -> bool:
    """Relevance gate: returns True only if the rule could potentially apply.

    Prevents emitting rule-specific SkippedCheck noise for completely un-involved rules (ENG-07).
    """
    if proposed_drugs is not None:
        # In Plan Evaluation (Pass 2): rule is relevant only if at least one proposed drug
        # is involved in the rule's target drugs or classes.
        def _drug_has_class(drug_id: str, target_class: str) -> bool:
            cand_drug = registry.get_drug(drug_id)
            if cand_drug and target_class in cand_drug.classes:
                return True
            return target_class in registry.get_classes_for_ingredient(drug_id)

        if isinstance(rule, VitalsInterlockRule):
            return rule.drug_id in proposed_drugs
        if isinstance(rule, PopulationRule):
            return rule.drug_id in proposed_drugs
        if isinstance(rule, PairRule):
            return rule.drug_a in proposed_drugs or rule.drug_b in proposed_drugs
        if isinstance(rule, ClassInteractionRule):
            return any(
                _drug_has_class(d, rule.class_a) or _drug_has_class(d, rule.class_b)
                for d in proposed_drugs
            )
        if isinstance(rule, DuplicationRule):
            return any(_drug_has_class(d, rule.class_name) for d in proposed_drugs)
        if isinstance(rule, AllergyCrossReactivityRule):
            return any(_drug_has_class(d, rule.target_class) for d in proposed_drugs)
        return True

    # In Baseline Evaluation (Pass 1):
    med_history_unresolved = patient.medication_history_status in (
        "incomplete",
        "unknown_unobtainable",
    ) or any(not m.resolved for m in patient.medications)
    allergy_history_unresolved = patient.allergy_history_status in (
        "incomplete",
        "unknown_unobtainable",
    ) or any(not a.resolved for a in patient.allergies)

    if isinstance(rule, VitalsInterlockRule):
        return rule.drug_id in active_drugs or (
            med_history_unresolved and "medications" in (rule.requires_fields or [])
        )
    if isinstance(rule, PopulationRule):
        return rule.drug_id in active_drugs or (
            med_history_unresolved and "medications" in (rule.requires_fields or [])
        )
    if isinstance(rule, PairRule):
        return (
            rule.drug_a in active_drugs
            or rule.drug_b in active_drugs
            or (med_history_unresolved and "medications" in (rule.requires_fields or []))
        )
    if isinstance(rule, ClassInteractionRule):
        return (
            rule.class_a in active_classes
            or rule.class_b in active_classes
            or (med_history_unresolved and "medications" in (rule.requires_fields or []))
        )
    if isinstance(rule, DuplicationRule):
        return rule.class_name in active_classes or (
            med_history_unresolved and "medications" in (rule.requires_fields or [])
        )
    if isinstance(rule, AllergyCrossReactivityRule):
        return rule.target_class in active_classes or (
            allergy_history_unresolved and "allergies" in (rule.requires_fields or [])
        )
    return True


def _evaluate_single_rule(
    rule: ClinicalRule,
    patient: Patient,
    active_drugs: set[str],
    active_classes: set[str],
    registry: ClinicalRegistry,
    proposed_drugs: set[str] | None = None,
) -> tuple[Alert | None, SkippedCheck | None]:
    """Evaluate a single clinical rule against patient and active medication state."""
    # 0. Relevance gate first: rule only evaluated if target drugs/classes could apply (ENG-07)
    if not _is_rule_relevant(
        rule=rule,
        active_drugs=active_drugs,
        active_classes=active_classes,
        patient=patient,
        registry=registry,
        proposed_drugs=proposed_drugs,
    ):
        return None, None

    # 1. Check requires_fields first
    if rule.requires_fields:
        if "medications" in rule.requires_fields:
            if patient.medication_history_status in ("incomplete", "unknown_unobtainable"):
                return None, SkippedCheck(
                    rule_id=rule.id,
                    rule_type=rule.type,
                    reason="Medication history status is incomplete or unknown/unobtainable",
                    missing_fields=["medications"],
                    provenance=rule.provenance,
                )
            unresolved_meds = [m.raw_text for m in patient.medications if not m.resolved]
            if unresolved_meds:
                return None, SkippedCheck(
                    rule_id=rule.id,
                    rule_type=rule.type,
                    reason=f"Medication history contains unresolved entities: {unresolved_meds}",
                    missing_fields=["medications_resolved"],
                    provenance=rule.provenance,
                )

        if "allergies" in rule.requires_fields:
            if patient.allergy_history_status in ("incomplete", "unknown_unobtainable"):
                return None, SkippedCheck(
                    rule_id=rule.id,
                    rule_type=rule.type,
                    reason="Allergy history status is incomplete or unknown/unobtainable",
                    missing_fields=["allergies"],
                    provenance=rule.provenance,
                )
            unresolved_allergies = [a.raw_substance for a in patient.allergies if not a.resolved]
            if unresolved_allergies:
                return None, SkippedCheck(
                    rule_id=rule.id,
                    rule_type=rule.type,
                    reason=(
                        f"Allergy history contains unresolved substances: {unresolved_allergies}"
                    ),
                    missing_fields=["allergies_resolved"],
                    provenance=rule.provenance,
                )

        if "pregnancy" in rule.requires_fields and patient.pregnancy == "unknown":
            return None, SkippedCheck(
                rule_id=rule.id,
                rule_type=rule.type,
                reason="Patient pregnancy status is unknown",
                missing_fields=["pregnancy"],
                provenance=rule.provenance,
            )

    # 2. Check rule clinical applicability to active drugs/classes
    # A rule only applies if its target drug or class is active in patient meds or plan
    if isinstance(rule, VitalsInterlockRule) and rule.drug_id not in active_drugs:
        return None, None
    if isinstance(rule, PopulationRule) and rule.drug_id not in active_drugs:
        return None, None
    if isinstance(rule, PairRule) and (
        rule.drug_a not in active_drugs or rule.drug_b not in active_drugs
    ):
        return None, None
    if isinstance(rule, ClassInteractionRule) and (
        rule.class_a not in active_classes or rule.class_b not in active_classes
    ):
        return None, None
    if isinstance(rule, DuplicationRule) and rule.class_name not in active_classes:
        return None, None
    if isinstance(rule, AllergyCrossReactivityRule) and (
        not patient.allergies or rule.target_class not in active_classes
    ):
        return None, None

    # 3. Check remaining required fields (vitals) for applicable rules
    if rule.requires_fields:
        for req_field in rule.requires_fields:
            if req_field not in (
                "medications",
                "medication_history_status",
                "allergies",
                "allergy_history_status",
                "pregnancy",
                "age",
            ):
                val = _extract_patient_vital(patient, req_field)
                if val is None:
                    return None, SkippedCheck(
                        rule_id=rule.id,
                        rule_type=rule.type,
                        reason=f"Required vital sign '{req_field}' is unknown or missing",
                        missing_fields=[req_field],
                        provenance=rule.provenance,
                    )

    # 4. Check rule status (NEEDS_SOURCE)
    if rule.status == RuleStatus.NEEDS_SOURCE:
        return None, SkippedCheck(
            rule_id=rule.id,
            rule_type=rule.type,
            reason="Rule or threshold is marked NEEDS_SOURCE and requires clinician sourcing",
            missing_fields=["threshold"],
            provenance=rule.provenance,
        )

    # 3. Rule Type-Specific Logic
    if isinstance(rule, PairRule):
        if rule.drug_a in active_drugs and rule.drug_b in active_drugs:
            return Alert(
                rule_id=rule.id,
                severity=rule.severity,
                rule_type="pair",
                drug_ids=[rule.drug_a, rule.drug_b],
                consequence=rule.consequence,
                action=rule.action,
                provenance=rule.provenance,
                unverified=not rule.provenance.verified,
            ), None

    elif isinstance(rule, ClassInteractionRule):
        if rule.class_a in active_classes and rule.class_b in active_classes:
            affected_class_drugs: set[str] = set()
            for drug_cand in active_drugs:
                cand_drug = registry.get_drug(drug_cand)
                if cand_drug and (
                    rule.class_a in cand_drug.classes or rule.class_b in cand_drug.classes
                ):
                    affected_class_drugs.add(cand_drug.drug_id)
                    for c_ing in cand_drug.ingredient_ids:
                        affected_class_drugs.add(c_ing)
                classes = registry.get_classes_for_ingredient(drug_cand)
                if rule.class_a in classes or rule.class_b in classes:
                    affected_class_drugs.add(drug_cand)

            if rule.lookback_hours_by_ingredient:
                lookback_triggered = False
                lookback_missing_timestamp = False
                missing_lookback_entry = False
                unconfigured_ing = ""
                matched_ing = ""

                # Evaluate all medications for confirmed in-window triggers (ENG-01)
                for med in patient.medications:
                    for ing in med.ingredients:
                        ing_id = ing.ingredient_id
                        classes = registry.get_classes_for_ingredient(ing_id)
                        if rule.class_a in classes or rule.class_b in classes:
                            if ing_id in rule.lookback_hours_by_ingredient:
                                lookback_limit = rule.lookback_hours_by_ingredient[ing_id]
                                if med.last_dose_time is None:
                                    lookback_missing_timestamp = True
                                else:
                                    elapsed_hours = (
                                        patient.assessed_at - med.last_dose_time
                                    ).total_seconds() / 3600.0
                                    if Decimal(str(elapsed_hours)) <= lookback_limit:
                                        lookback_triggered = True
                                        matched_ing = ing_id
                            else:
                                # Class member with no lookback entry in rule (ENG-08)
                                missing_lookback_entry = True
                                unconfigured_ing = ing_id

                # Confirmed in-window trigger ALWAYS wins over missing timestamp (ENG-01)
                if lookback_triggered:
                    if matched_ing:
                        affected_class_drugs.add(matched_ing)
                    return Alert(
                        rule_id=rule.id,
                        severity=rule.severity,
                        rule_type="class_interaction",
                        drug_ids=sorted(affected_class_drugs),
                        consequence=rule.consequence,
                        action=rule.action,
                        provenance=rule.provenance,
                        unverified=not rule.provenance.verified,
                    ), None

                # Only if no confirmed trigger, check for missing timestamp (conservative skip)
                if lookback_missing_timestamp:
                    return None, SkippedCheck(
                        rule_id=rule.id,
                        rule_type="class_interaction",
                        reason="Medication last_dose_time is unknown for lookback check",
                        missing_fields=["last_dose_time"],
                        provenance=rule.provenance,
                    )

                # In-class drug with missing lookback entry must skip (ENG-08)
                if missing_lookback_entry:
                    return None, SkippedCheck(
                        rule_id=rule.id,
                        rule_type="class_interaction",
                        reason=(
                            f"In-class medication ingredient '{unconfigured_ing}' "
                            f"has no configured lookback window in rule '{rule.id}'"
                        ),
                        missing_fields=[f"lookback_hours_by_ingredient.{unconfigured_ing}"],
                        provenance=rule.provenance,
                    )
            else:
                return Alert(
                    rule_id=rule.id,
                    severity=rule.severity,
                    rule_type="class_interaction",
                    drug_ids=sorted(affected_class_drugs),
                    consequence=rule.consequence,
                    action=rule.action,
                    provenance=rule.provenance,
                    unverified=not rule.provenance.verified,
                ), None

    elif isinstance(rule, AllergyCrossReactivityRule):
        matched_alert: Alert | None = None
        matched_skip: SkippedCheck | None = None

        for allergy in patient.allergies:
            allergen_id = allergy.normalized_allergen_id or allergy.raw_substance.lower()
            allergen_classes = set(registry.get_classes_for_ingredient(allergen_id))
            if allergy.allergen_class:
                allergen_classes.add(allergy.allergen_class)
            if allergen_id in registry.aliases:
                for alias_ing_id in registry.aliases[allergen_id].ingredient_ids:
                    for c in registry.get_classes_for_ingredient(alias_ing_id):
                        allergen_classes.add(c)
            if allergen_id in registry.formulary_drugs:
                for c in registry.formulary_drugs[allergen_id].classes:
                    allergen_classes.add(c)

            if rule.allergen_class in allergen_classes:
                reaction_match = (
                    allergy.reaction_type in rule.reaction_types or "unknown" in rule.reaction_types
                )
                if reaction_match and rule.target_class in active_classes:
                    affected_allergy_drugs = {allergen_id}
                    for drug_cand in active_drugs:
                        cand_drug = registry.get_drug(drug_cand)
                        if cand_drug and rule.target_class in cand_drug.classes:
                            affected_allergy_drugs.add(cand_drug.drug_id)
                            for c_ing in cand_drug.ingredient_ids:
                                affected_allergy_drugs.add(c_ing)
                        elif rule.target_class in registry.get_classes_for_ingredient(drug_cand):
                            affected_allergy_drugs.add(drug_cand)

                    matched_alert = Alert(
                        rule_id=rule.id,
                        severity=rule.severity,
                        rule_type="allergy_crossreactivity",
                        drug_ids=sorted(affected_allergy_drugs),
                        consequence=rule.consequence,
                        action=rule.action,
                        provenance=rule.provenance,
                        unverified=not rule.provenance.verified,
                    )
                    break
                elif allergy.reaction_type == "unknown" and "unknown" not in rule.reaction_types:
                    if matched_skip is None:
                        matched_skip = SkippedCheck(
                            rule_id=rule.id,
                            rule_type="allergy_crossreactivity",
                            reason=(
                                f"Allergy reaction type for '{allergy.raw_substance}' is unknown"
                            ),
                            missing_fields=["reaction_type"],
                            provenance=rule.provenance,
                        )

        if matched_alert is not None:
            return matched_alert, None
        if matched_skip is not None:
            return None, matched_skip

    elif isinstance(rule, VitalsInterlockRule):
        if rule.drug_id in active_drugs:
            if rule.threshold_value is None and rule.threshold_str is None:
                return None, SkippedCheck(
                    rule_id=rule.id,
                    rule_type="vitals_interlock",
                    reason=(
                        f"Vitals interlock threshold for '{rule.drug_id}' is null (NEEDS_SOURCE)"
                    ),
                    missing_fields=["threshold"],
                    provenance=rule.provenance,
                )
            vital_val = _extract_patient_vital(patient, rule.vital_name)
            if vital_val is None:
                return None, SkippedCheck(
                    rule_id=rule.id,
                    rule_type="vitals_interlock",
                    reason=f"Vital sign '{rule.vital_name}' is unknown",
                    missing_fields=[rule.vital_name],
                    provenance=rule.provenance,
                )

            if rule.threshold_value is not None:
                dec_val = Decimal(str(vital_val))
                thresh = rule.threshold_value
                fired = False
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
                    fired = True

                if fired:
                    return Alert(
                        rule_id=rule.id,
                        severity=rule.severity,
                        rule_type="vitals_interlock",
                        drug_ids=[rule.drug_id],
                        consequence=rule.consequence,
                        action=rule.action,
                        provenance=rule.provenance,
                        unverified=not rule.provenance.verified,
                    ), None

    elif isinstance(rule, PopulationRule):
        if rule.drug_id in active_drugs:
            if rule.contraindicated_pregnancy and patient.pregnancy == "yes":
                return Alert(
                    rule_id=rule.id,
                    severity=rule.severity,
                    rule_type="population",
                    drug_ids=[rule.drug_id],
                    consequence=rule.consequence,
                    action=rule.action,
                    provenance=rule.provenance,
                    unverified=not rule.provenance.verified,
                ), None
            if (
                rule.contraindicated_population
                and patient.age.population_category == rule.contraindicated_population
            ):
                return Alert(
                    rule_id=rule.id,
                    severity=rule.severity,
                    rule_type="population",
                    drug_ids=[rule.drug_id],
                    consequence=rule.consequence,
                    action=rule.action,
                    provenance=rule.provenance,
                    unverified=not rule.provenance.verified,
                ), None

    elif isinstance(rule, DuplicationRule):
        count = 0
        matching_drugs: list[str] = []
        for med in patient.medications:
            if not med.resolved:
                continue
            matched = False
            for ing in med.ingredients:
                if rule.class_name in registry.get_classes_for_ingredient(ing.ingredient_id):
                    matched = True
                    matching_drugs.append(ing.ingredient_id)
                    break
            if not matched:
                drug_key = med.raw_text.strip().lower()
                drug = registry.get_drug(drug_key)
                if (
                    drug
                    and rule.class_name in drug.classes
                    or rule.class_name in registry.get_classes_for_ingredient(drug_key)
                ):
                    matched = True
                    matching_drugs.append(drug_key)
            if matched:
                count += 1

        matching_drugs_set = set(matching_drugs)
        for drug_cand in active_drugs:
            cand_drug = registry.get_drug(drug_cand)
            is_class_match = (cand_drug is not None and rule.class_name in cand_drug.classes) or (
                rule.class_name in registry.get_classes_for_ingredient(drug_cand)
            )
            if is_class_match and drug_cand not in matching_drugs_set:
                matching_drugs_set.add(drug_cand)
                count += 1

        if count > rule.max_concurrent:
            return Alert(
                rule_id=rule.id,
                severity=rule.severity,
                rule_type="duplication",
                drug_ids=sorted(matching_drugs_set),
                consequence=rule.consequence,
                action=rule.action,
                provenance=rule.provenance,
                unverified=not rule.provenance.verified,
            ), None

    return None, None


def evaluate_baseline(
    patient: Patient,
    registry: ClinicalRegistry,
) -> tuple[list[Alert], list[SkippedCheck], int, int]:
    """Execute Pass 1 deterministic checks on patient baseline home state.

    Returns:
        (alerts, skipped_checks, checks_run, unverified_rules_count)
    """
    active_drugs = _get_active_drug_identifiers(patient, registry)
    active_classes = _get_active_classes(patient, registry)

    alerts: list[Alert] = []
    skipped_checks: list[SkippedCheck] = []
    checks_run = 0
    unverified_rules_count = 0

    for rule in registry.rules:
        checks_run += 1
        if not rule.provenance.verified:
            unverified_rules_count += 1

        alert, skip = _evaluate_single_rule(
            rule=rule,
            patient=patient,
            active_drugs=active_drugs,
            active_classes=active_classes,
            registry=registry,
        )
        if alert:
            alerts.append(alert)
        if skip:
            skipped_checks.append(skip)

    return _sort_alerts(alerts), skipped_checks, checks_run, unverified_rules_count


def evaluate_plan(
    patient: Patient,
    steps: list[PlanStepDraft],
    baseline_alerts: list[Alert],
    registry: ClinicalRegistry,
) -> tuple[list[Alert], list[SkippedCheck], list[CalculatedDoseReport]]:
    """Execute Pass 2 deterministic verification on proposed plan steps.

    Withhold steps are never evaluated as administrations.
    Dose verification is executed on administer steps with requested doses.
    """
    alerts: list[Alert] = []
    skipped_checks: list[SkippedCheck] = []
    dose_reports: list[CalculatedDoseReport] = []

    proposed_administer_drugs: set[str] = set()
    for step in steps:
        if step.action_type == ActionType.administer and step.drug_id:
            proposed_administer_drugs.add(step.drug_id)
            drug = registry.get_drug(step.drug_id)
            if drug:
                for ing in drug.ingredient_ids:
                    proposed_administer_drugs.add(ing)

            if step.requested_dose:
                dose_report = verify_dose(
                    patient=patient,
                    drug_id=step.drug_id,
                    requested_dose=step.requested_dose,
                    registry=registry,
                    step_number=step.step_number,
                )
                dose_reports.append(dose_report)
                prov = drug.provenance if drug else registry.rules[0].provenance
                # Exhaustive dose status handling (ENG-03)
                if dose_report.status == "EXCEEDS_CEILING":
                    alerts.append(
                        Alert(
                            rule_id=f"DOSE_LIMIT_{step.drug_id.upper()}",
                            severity=Severity.HIGH,
                            rule_type="dose_limit",
                            drug_ids=[step.drug_id],
                            consequence=dose_report.notes,
                            action="Reduce dose to within verified formulary maximum ceiling",
                            provenance=prov,
                            unverified=True,
                            step_number=step.step_number,
                        )
                    )
                elif dose_report.status == "MAGNITUDE_WARNING":
                    alerts.append(
                        Alert(
                            rule_id=f"DOSE_MAGNITUDE_{step.drug_id.upper()}",
                            severity=Severity.HIGH,
                            rule_type="dose_limit",
                            drug_ids=[step.drug_id],
                            consequence=dose_report.notes,
                            action="Review dose magnitude for decimal slip or unit error",
                            provenance=prov,
                            unverified=True,
                            step_number=step.step_number,
                        )
                    )
                elif dose_report.status == "BELOW_MINIMUM":
                    sev = (
                        Severity.HIGH
                        if dose_report.magnitude_tripwire_triggered
                        else Severity.MODERATE
                    )
                    alerts.append(
                        Alert(
                            rule_id=f"DOSE_MINIMUM_{step.drug_id.upper()}",
                            severity=sev,
                            rule_type="dose_limit",
                            drug_ids=[step.drug_id],
                            consequence=dose_report.notes,
                            action="Adjust dose to meet minimum effective formulary threshold",
                            provenance=prov,
                            unverified=True,
                            step_number=step.step_number,
                        )
                    )
                elif dose_report.status == "UNVERIFIED_MISSING_CAP":
                    missing_field = (
                        "weight_kg"
                        if "weight" in dose_report.notes.lower()
                        else "formulary_dose_limit"
                    )
                    skipped_checks.append(
                        SkippedCheck(
                            rule_id=f"DOSE_CHECK_{step.drug_id.upper()}",
                            rule_type="dose_limit",
                            reason=dose_report.notes,
                            missing_fields=[missing_field],
                            provenance=prov,
                        )
                    )
                elif dose_report.status == "OK":
                    pass
                else:
                    skipped_checks.append(
                        SkippedCheck(
                            rule_id=f"DOSE_CHECK_{step.drug_id.upper()}",
                            rule_type="dose_limit",
                            reason=(
                                f"Unknown dose report status '{dose_report.status}': "
                                f"{dose_report.notes}"
                            ),
                            missing_fields=["dose_status"],
                            provenance=prov,
                        )
                    )

    # Cumulative 24-hour daily exposure evaluation (Section 5 review)
    cum_alerts, cum_skips = verify_cumulative_daily_exposure(
        patient=patient,
        steps=steps,
        registry=registry,
    )
    alerts.extend(cum_alerts)
    skipped_checks.extend(cum_skips)

    combined_drugs = _get_active_drug_identifiers(patient, registry) | proposed_administer_drugs
    combined_classes = _get_active_classes(patient, registry)
    for drug_id in proposed_administer_drugs:
        drug = registry.get_drug(drug_id)
        if drug:
            for cls in drug.classes:
                combined_classes.add(cls)

    for rule in registry.rules:
        alert, skip = _evaluate_single_rule(
            rule=rule,
            patient=patient,
            active_drugs=combined_drugs,
            active_classes=combined_classes,
            registry=registry,
            proposed_drugs=proposed_administer_drugs,
        )
        if alert:
            # ENG-02: Only suppress if an existing baseline alert already covers the exact same
            # rule and drug_ids (purely among home medications, no proposed drug involved).
            already_covered = any(
                ba.rule_id == alert.rule_id and frozenset(ba.drug_ids) == frozenset(alert.drug_ids)
                for ba in baseline_alerts
            )
            if not already_covered:
                alerts.append(alert)
        if skip and not any(bs.rule_id == skip.rule_id for bs in skipped_checks):
            skipped_checks.append(skip)

    return _sort_alerts(alerts), skipped_checks, dose_reports
