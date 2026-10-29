"""Deterministic clinical dose verification engine.

Safety Property (Rule R8):
All calculations use exact Decimal arithmetic with explicit units.
Enforces weight-based, fixed, and FDC dosage ceilings.
Flags >=10x or <=0.1x magnitude deviations.
Fails closed with UNVERIFIED_MISSING_CAP if limits or weight are unknown.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from triagerag.contracts.enums import ActionType, DoseUnit, RuleStatus, Severity
from triagerag.contracts.schemas import (
    Alert,
    CalculatedDoseReport,
    ExplicitDose,
    PlanStepDraft,
    SkippedCheck,
)
from triagerag.normalize.units import check_magnitude_tripwire, convert_dose

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient
    from triagerag.engine.registry import ClinicalRegistry


def _get_mass_unit_for_weight_basis(unit: DoseUnit) -> DoseUnit:
    """Map a per-kg dose unit to its base mass unit."""
    if unit == DoseUnit.mcg_per_kg:
        return DoseUnit.mcg
    if unit == DoseUnit.mg_per_kg:
        return DoseUnit.mg
    return DoseUnit.mg


def verify_dose(
    patient: Patient,
    drug_id: str,
    requested_dose: ExplicitDose,
    registry: ClinicalRegistry,
    step_number: int | None = None,
) -> CalculatedDoseReport:
    """Verify a proposed medication dose against formulary population limits and tripwires."""
    drug = registry.get_drug(drug_id)
    if drug is None:
        return CalculatedDoseReport(
            drug_id=drug_id,
            requested_dose=requested_dose,
            calculated_ceiling=None,
            calculated_recommended=None,
            magnitude_tripwire_triggered=False,
            status="UNVERIFIED_MISSING_CAP",
            notes=f"Drug '{drug_id}' not found in formulary registry",
            step_number=step_number,
        )

    pop_cat = str(patient.age.population_category)
    pop_rule = drug.population_rules.get(pop_cat)

    if (
        pop_rule is None
        or pop_rule.status == RuleStatus.NEEDS_SOURCE
        or pop_rule.per_dose_max is None
    ):
        return CalculatedDoseReport(
            drug_id=drug_id,
            requested_dose=requested_dose,
            calculated_ceiling=None,
            calculated_recommended=None,
            magnitude_tripwire_triggered=False,
            status="UNVERIFIED_MISSING_CAP",
            notes=f"Missing or unverified formulary dosage limits for population '{pop_cat}'",
            step_number=step_number,
        )

    # Calculate limits based on dosing basis (weight vs fixed)
    if pop_rule.dose_basis == "weight":
        if patient.weight_kg.source == "unknown" or patient.weight_kg.value is None:
            return CalculatedDoseReport(
                drug_id=drug_id,
                requested_dose=requested_dose,
                calculated_ceiling=None,
                calculated_recommended=None,
                magnitude_tripwire_triggered=False,
                status="UNVERIFIED_MISSING_CAP",
                notes=("Weight-based dose verification cannot proceed: patient weight is unknown"),
                step_number=step_number,
            )

        weight = patient.weight_kg.value
        target_unit = _get_mass_unit_for_weight_basis(pop_rule.unit)

        calc_max_amount = pop_rule.per_dose_max * weight
        if pop_rule.daily_max is not None and calc_max_amount > pop_rule.daily_max:
            calc_max_amount = pop_rule.daily_max

        calc_min_amount = (
            pop_rule.per_dose_min * weight if pop_rule.per_dose_min is not None else None
        )
        calculated_ceiling = ExplicitDose(amount=calc_max_amount, unit=target_unit)
        calculated_recommended = (
            ExplicitDose(amount=calc_min_amount, unit=target_unit)
            if calc_min_amount is not None
            else None
        )
    else:
        # Fixed dose
        calc_max_amount = pop_rule.per_dose_max
        calc_min_amount = pop_rule.per_dose_min
        calculated_ceiling = ExplicitDose(amount=calc_max_amount, unit=pop_rule.unit)
        calculated_recommended = (
            ExplicitDose(amount=calc_min_amount, unit=pop_rule.unit)
            if calc_min_amount is not None
            else None
        )

    # Convert requested dose to same unit as calculated ceiling for exact comparison
    actual_requested = requested_dose
    if requested_dose.unit == DoseUnit.mg_per_kg:
        if patient.weight_kg.source == "unknown" or patient.weight_kg.value is None:
            return CalculatedDoseReport(
                drug_id=drug_id,
                requested_dose=requested_dose,
                calculated_ceiling=calculated_ceiling,
                calculated_recommended=calculated_recommended,
                magnitude_tripwire_triggered=False,
                status="UNVERIFIED_MISSING_CAP",
                notes="Weight-based dose verification cannot proceed: patient weight is unknown",
                step_number=step_number,
            )
        actual_requested = ExplicitDose(
            amount=requested_dose.amount * patient.weight_kg.value, unit=DoseUnit.mg
        )
    elif requested_dose.unit == DoseUnit.mcg_per_kg:
        if patient.weight_kg.source == "unknown" or patient.weight_kg.value is None:
            return CalculatedDoseReport(
                drug_id=drug_id,
                requested_dose=requested_dose,
                calculated_ceiling=calculated_ceiling,
                calculated_recommended=calculated_recommended,
                magnitude_tripwire_triggered=False,
                status="UNVERIFIED_MISSING_CAP",
                notes="Weight-based dose verification cannot proceed: patient weight is unknown",
                step_number=step_number,
            )
        actual_requested = ExplicitDose(
            amount=requested_dose.amount * patient.weight_kg.value, unit=DoseUnit.mcg
        )

    try:
        req_converted = convert_dose(actual_requested, calculated_ceiling.unit)
    except ValueError as e:
        return CalculatedDoseReport(
            drug_id=drug_id,
            requested_dose=requested_dose,
            calculated_ceiling=calculated_ceiling,
            calculated_recommended=calculated_recommended,
            magnitude_tripwire_triggered=False,
            status="UNVERIFIED_MISSING_CAP",
            notes=f"Unit conversion failed: {e}",
            step_number=step_number,
        )

    tripwire = check_magnitude_tripwire(req_converted.amount, calculated_ceiling.amount)

    # Determine status
    status: Literal[
        "OK", "EXCEEDS_CEILING", "BELOW_MINIMUM", "MAGNITUDE_WARNING", "UNVERIFIED_MISSING_CAP"
    ]
    if req_converted.amount > calculated_ceiling.amount:
        status = "EXCEEDS_CEILING"
        notes = (
            f"Requested {req_converted.amount} {calculated_ceiling.unit} exceeds "
            f"maximum per-dose limit {calculated_ceiling.amount} {calculated_ceiling.unit}"
        )
    elif calc_min_amount is not None and req_converted.amount < calc_min_amount:
        status = "BELOW_MINIMUM"
        notes = (
            f"Requested {req_converted.amount} {calculated_ceiling.unit} is below "
            f"minimum effective dose {calc_min_amount} {calculated_ceiling.unit}"
        )
    elif tripwire:
        status = "MAGNITUDE_WARNING"
        notes = "Magnitude tripwire triggered (>=10x or <=0.1x of standard limit)"
    else:
        status = "OK"
        notes = "Dose within verified limits"

    if patient.weight_kg.source == "estimated":
        notes += " [Patient weight is ESTIMATED]"

    return CalculatedDoseReport(
        drug_id=drug_id,
        requested_dose=requested_dose,
        calculated_ceiling=calculated_ceiling,
        calculated_recommended=calculated_recommended,
        magnitude_tripwire_triggered=tripwire,
        status=status,
        notes=notes,
        step_number=step_number,
    )


def verify_cumulative_daily_exposure(
    patient: Patient,
    steps: list[PlanStepDraft],
    registry: ClinicalRegistry,
) -> tuple[list[Alert], list[SkippedCheck]]:
    """Verify that total 24h drug exposure across plan steps and history stays within limits.

    Safety Property (Rule R8, Review Section 5):
    - Identifies all proposed administration steps for each drug.
    - Inspects patient medication history within 24 hours of assessed_at.
    - Sums cumulative exposure in exact Decimal units.
    - If medication history is unobtainable/unknown, emits SkippedCheck (fail-closed).
    - If cumulative exposure exceeds formulary daily_max, emits HIGH severity alert.
    """
    alerts: list[Alert] = []
    skipped_checks: list[SkippedCheck] = []

    # 1. Group proposed administration doses by drug_id
    plan_doses_by_drug: dict[str, list[tuple[int, ExplicitDose]]] = {}
    for step in steps:
        if step.action_type == ActionType.administer and step.drug_id and step.requested_dose:
            did = step.drug_id.lower()
            plan_doses_by_drug.setdefault(did, []).append((step.step_number, step.requested_dose))

    if not plan_doses_by_drug:
        return alerts, skipped_checks

    pop_cat = str(patient.age.population_category)

    for drug_id, proposed_doses in plan_doses_by_drug.items():
        drug = registry.get_drug(drug_id)
        if drug is None:
            continue

        pop_rule = drug.population_rules.get(pop_cat)
        if (
            pop_rule is None
            or pop_rule.status == RuleStatus.NEEDS_SOURCE
            or pop_rule.daily_max is None
        ):
            continue

        target_unit = (
            _get_mass_unit_for_weight_basis(pop_rule.unit)
            if pop_rule.dose_basis == "weight"
            else pop_rule.unit
        )
        daily_max_amount = pop_rule.daily_max

        # Check patient weight for weight-based doses
        patient_weight: Decimal | None = None
        if patient.weight_kg.source != "unknown" and patient.weight_kg.value is not None:
            patient_weight = patient.weight_kg.value

        plan_total = Decimal("0.0")
        conversion_error = False

        for step_num, dose in proposed_doses:
            actual_dose = dose
            if dose.unit in (DoseUnit.mg_per_kg, DoseUnit.mcg_per_kg):
                if patient_weight is None:
                    skipped_checks.append(
                        SkippedCheck(
                            rule_id=f"CUMULATIVE_DOSE_{drug_id.upper()}",
                            rule_type="cumulative_dose_limit",
                            reason=(
                                f"Patient weight unknown; cannot calculate weight-based "
                                f"dose for step {step_num}"
                            ),
                            missing_fields=["weight_kg"],
                            provenance=pop_rule.provenance,
                        )
                    )
                    conversion_error = True
                    break
                base_unit = DoseUnit.mg if dose.unit == DoseUnit.mg_per_kg else DoseUnit.mcg
                actual_dose = ExplicitDose(amount=dose.amount * patient_weight, unit=base_unit)

            try:
                converted = convert_dose(actual_dose, target_unit)
                plan_total += converted.amount
            except ValueError as e:
                skipped_checks.append(
                    SkippedCheck(
                        rule_id=f"CUMULATIVE_DOSE_{drug_id.upper()}",
                        rule_type="cumulative_dose_limit",
                        reason=f"Unit conversion failed during cumulative evaluation: {e}",
                        missing_fields=["unit_conversion"],
                        provenance=pop_rule.provenance,
                    )
                )
                conversion_error = True
                break

        if conversion_error:
            continue

        # Inspect prior 24h medication history
        prior_total = Decimal("0.0")
        if patient.medication_history_status in ("unobtainable", "unknown"):
            skipped_checks.append(
                SkippedCheck(
                    rule_id=f"CUMULATIVE_DOSE_{drug_id.upper()}",
                    rule_type="cumulative_dose_limit",
                    reason=(
                        f"Patient prior medication history is "
                        f"'{patient.medication_history_status}'; cumulative 24h exposure "
                        f"for '{drug_id}' cannot be confirmed safe"
                    ),
                    missing_fields=["medication_history"],
                    provenance=pop_rule.provenance,
                )
            )
        elif patient.medication_history_status == "confirmed_list":
            drug_identifiers = {drug_id} | {ing.lower() for ing in drug.ingredient_ids}
            for med in patient.medications:
                med_matches = med.raw_text.lower() in drug_identifiers or any(
                    ing.ingredient_id.lower() in drug_identifiers for ing in med.ingredients
                )
                if not med_matches:
                    continue

                is_within_24h = True
                if med.last_dose_time is not None:
                    delta_seconds = (patient.assessed_at - med.last_dose_time).total_seconds()
                    if delta_seconds < 0 or delta_seconds > 86400:
                        is_within_24h = False

                if is_within_24h:
                    if med.dose_taken is not None:
                        try:
                            conv_prior = convert_dose(med.dose_taken, target_unit)
                            prior_total += conv_prior.amount
                        except ValueError:
                            skipped_checks.append(
                                SkippedCheck(
                                    rule_id=f"CUMULATIVE_DOSE_{drug_id.upper()}",
                                    rule_type="cumulative_dose_limit",
                                    reason=(
                                        f"Prior dose unit conversion failed for '{med.raw_text}'"
                                    ),
                                    missing_fields=["dose_taken_unit"],
                                    provenance=pop_rule.provenance,
                                )
                            )
                    else:
                        skipped_checks.append(
                            SkippedCheck(
                                rule_id=f"CUMULATIVE_DOSE_{drug_id.upper()}",
                                rule_type="cumulative_dose_limit",
                                reason=(
                                    f"Patient history records medication '{med.raw_text}' "
                                    "within 24h but dose taken is unknown; exposure unverified"
                                ),
                                missing_fields=["dose_taken"],
                                provenance=pop_rule.provenance,
                            )
                        )

        cumulative_total = plan_total + prior_total

        if cumulative_total > daily_max_amount:
            # Determine the exact step that pushes cumulative exposure over the daily limit
            running_total = prior_total
            breach_step_number: int | None = None
            for s_num, d in proposed_doses:
                act_d = d
                if (
                    d.unit in (DoseUnit.mg_per_kg, DoseUnit.mcg_per_kg)
                    and patient_weight is not None
                ):
                    bu = DoseUnit.mg if d.unit == DoseUnit.mg_per_kg else DoseUnit.mcg
                    act_d = ExplicitDose(amount=d.amount * patient_weight, unit=bu)
                try:
                    conv_d = convert_dose(act_d, target_unit)
                    running_total += conv_d.amount
                except ValueError:
                    continue
                if running_total > daily_max_amount:
                    breach_step_number = s_num
                    break

            if breach_step_number is None and proposed_doses:
                breach_step_number = proposed_doses[-1][0]

            alerts.append(
                Alert(
                    rule_id=f"CUMULATIVE_DAILY_DOSE_{drug_id.upper()}",
                    severity=Severity.HIGH,
                    rule_type="cumulative_dose_limit",
                    drug_ids=[drug_id],
                    consequence=(
                        f"Cumulative 24-hour exposure for '{drug_id}' "
                        f"({cumulative_total} {target_unit}) exceeds maximum daily limit "
                        f"({daily_max_amount} {target_unit}) [Plan: {plan_total} {target_unit}, "
                        f"Prior 24h: {prior_total} {target_unit}]"
                    ),
                    action=(
                        f"Reduce cumulative dose of '{drug_id}' across repeated administrations "
                        f"to within daily limit of {daily_max_amount} {target_unit}"
                    ),
                    provenance=pop_rule.provenance,
                    unverified=True,
                    step_number=breach_step_number,
                )
            )

    return alerts, skipped_checks
