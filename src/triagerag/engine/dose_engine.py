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

from triagerag.contracts.enums import ActionType, DoseUnit, Route, RuleStatus, Severity
from triagerag.contracts.schemas import (
    Alert,
    CalculatedDoseReport,
    ExplicitDose,
    PlanStepDraft,
    SkippedCheck,
)
from triagerag.normalize.units import check_magnitude_tripwire, convert_dose

if TYPE_CHECKING:
    from triagerag.contracts.data_schemas import FormularyDrug
    from triagerag.contracts.schemas import Patient
    from triagerag.engine.registry import ClinicalRegistry


def _get_mass_unit_for_weight_basis(unit: DoseUnit) -> DoseUnit:
    """Map a per-kg dose unit to its base mass unit."""
    if unit == DoseUnit.mcg_per_kg:
        return DoseUnit.mcg
    if unit == DoseUnit.mg_per_kg:
        return DoseUnit.mg
    return DoseUnit.mg


def calculate_administration_volume(
    drug: FormularyDrug,
    dose: ExplicitDose,
    patient: Patient | None = None,
    step: PlanStepDraft | None = None,
) -> Decimal | None:
    """Calculate liquid volume in mL for administration based on concentration.

    Safety Property (Rule R8):
    Uses exact Decimal arithmetic.
    Prefers step-specified concentration; falls back to formulary concentration table.
    """
    actual_dose = dose
    if dose.unit in (DoseUnit.mg_per_kg, DoseUnit.mcg_per_kg):
        if (
            patient is None
            or patient.weight_kg.source == "unknown"
            or patient.weight_kg.value is None
        ):
            return None
        base_unit = DoseUnit.mg if dose.unit == DoseUnit.mg_per_kg else DoseUnit.mcg
        actual_dose = ExplicitDose(amount=dose.amount * patient.weight_kg.value, unit=base_unit)

    # 1. Step-level explicit concentration (mg/mL)
    if step is not None and step.concentration_mg_per_ml is not None:
        conc = step.concentration_mg_per_ml
        if conc <= Decimal("0"):
            return None
        try:
            dose_mg = convert_dose(actual_dose, DoseUnit.mg)
            return dose_mg.amount / conc
        except ValueError:
            return None

    # 2. Formulary concentration table
    if not drug.concentrations:
        return None

    matching_concs = drug.concentrations
    if step is not None and step.route is not None:
        route_concs = [c for c in drug.concentrations if c.route == step.route]
        if route_concs:
            matching_concs = route_concs

    selected_conc = matching_concs[0]
    if selected_conc.amount <= Decimal("0") or selected_conc.volume_ml <= Decimal("0"):
        return None

    try:
        dose_in_conc_unit = convert_dose(actual_dose, selected_conc.unit)
        return (dose_in_conc_unit.amount / selected_conc.amount) * selected_conc.volume_ml
    except ValueError:
        return None


def verify_dose(
    patient: Patient,
    drug_id: str,
    requested_dose: ExplicitDose,
    registry: ClinicalRegistry,
    step_number: int | None = None,
    step: PlanStepDraft | None = None,
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
        if pop_rule.max_single_dose is not None and calc_max_amount > pop_rule.max_single_dose:
            calc_max_amount = pop_rule.max_single_dose
        elif pop_rule.daily_max is not None and calc_max_amount > pop_rule.daily_max:
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

    calculated_volume_ml = calculate_administration_volume(
        drug=drug,
        dose=actual_requested,
        patient=patient,
        step=step,
    )

    if (
        step is not None
        and step.route in (Route.im, "im")
        and calculated_volume_ml is not None
        and calculated_volume_ml > Decimal("3.0")
    ):
        notes += (
            f" [WARNING: Calculated IM volume {calculated_volume_ml:.2f} mL "
            "exceeds 3.0 mL single-site injection limit]"
        )

    if patient.weight_kg.source == "estimated":
        notes += " [Patient weight is ESTIMATED]"

    return CalculatedDoseReport(
        drug_id=drug_id,
        requested_dose=requested_dose,
        calculated_ceiling=calculated_ceiling,
        calculated_recommended=calculated_recommended,
        calculated_volume_ml=calculated_volume_ml,
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

        # Check patient weight for weight-based doses
        patient_weight: Decimal | None = None
        if patient.weight_kg.source != "unknown" and patient.weight_kg.value is not None:
            patient_weight = patient.weight_kg.value

        target_unit: DoseUnit
        if pop_rule.dose_basis == "weight":
            # If explicitly specified as an absolute mass unit:
            if pop_rule.daily_max_unit in (DoseUnit.mg, DoseUnit.g, DoseUnit.mcg):
                target_unit = pop_rule.daily_max_unit
                daily_max_amount = pop_rule.daily_max
            elif pop_rule.unit in (
                DoseUnit.mg_per_kg,
                DoseUnit.mcg_per_kg,
            ) or pop_rule.daily_max_unit in (DoseUnit.mg_per_kg, DoseUnit.mcg_per_kg):
                if patient_weight is None:
                    skipped_checks.append(
                        SkippedCheck(
                            rule_id=f"CUMULATIVE_DOSE_{drug_id.upper()}",
                            rule_type="cumulative_dose_limit",
                            reason=(
                                f"Patient weight unknown; cannot calculate weight-adjusted "
                                f"cumulative daily ceiling for '{drug_id}'"
                            ),
                            missing_fields=["weight_kg"],
                            provenance=pop_rule.provenance,
                        )
                    )
                    continue
                # Weight-based daily max ceiling normalized to absolute mass
                target_unit = DoseUnit.mg if pop_rule.unit == DoseUnit.mg_per_kg else DoseUnit.mcg
                daily_max_amount = pop_rule.daily_max * patient_weight
            else:
                target_unit = pop_rule.unit
                daily_max_amount = pop_rule.daily_max
        else:
            target_unit = pop_rule.unit
            daily_max_amount = pop_rule.daily_max

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

        # Inspect prior 24h medication history (single-encounter rolling 24h window)
        prior_total = Decimal("0.0")
        if patient.medication_history_status in ("incomplete", "unknown_unobtainable"):
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


def verify_dosing_intervals(
    patient: Patient,
    steps: list[PlanStepDraft],
    registry: ClinicalRegistry,
) -> tuple[list[Alert], list[SkippedCheck]]:
    """Verify that proposed administrations obey minimum dosing intervals and frequencies.

    Safety Property (Rule R8, AUB-ENG-02):
    - Validates step.frequency_hours against formulary min_interval_hours.
    - Validates lookback to patient.medications within min_interval_hours.
    - Fails closed if last_dose_time is missing for a recent medication in confirmed list.
    """
    alerts: list[Alert] = []
    skipped_checks: list[SkippedCheck] = []
    pop_cat = str(patient.age.population_category)

    for step in steps:
        if step.action_type != ActionType.administer or not step.drug_id:
            continue

        drug = registry.get_drug(step.drug_id)
        if drug is None:
            continue

        pop_rule = drug.population_rules.get(pop_cat)
        if pop_rule is None or pop_rule.min_interval_hours is None:
            continue

        min_interval = pop_rule.min_interval_hours

        # 1. Step-level frequency check
        if step.frequency_hours is not None and step.frequency_hours < min_interval:
            alerts.append(
                Alert(
                    rule_id=f"MIN_INTERVAL_{drug.drug_id.upper()}",
                    severity=Severity.HIGH,
                    rule_type="frequency_limit",
                    drug_ids=[drug.drug_id],
                    consequence=(
                        f"Proposed dosing frequency every {step.frequency_hours} hours for "
                        f"'{drug.drug_id}' violates minimum dosing interval of {min_interval} hours"
                    ),
                    action=(
                        f"Increase dosing interval for '{drug.drug_id}' to at least {min_interval} hours"
                    ),
                    provenance=pop_rule.provenance,
                    unverified=not pop_rule.provenance.verified,
                    step_number=step.step_number,
                )
            )

        # 2. Prior medication history lookback check
        drug_identifiers = {drug.drug_id.lower()} | {ing.lower() for ing in drug.ingredient_ids}
        if patient.medication_history_status in ("incomplete", "unknown_unobtainable"):
            skipped_checks.append(
                SkippedCheck(
                    rule_id=f"MIN_INTERVAL_{drug.drug_id.upper()}",
                    rule_type="frequency_limit",
                    reason=(
                        f"Patient prior medication history is '{patient.medication_history_status}'; "
                        f"minimum dosing interval ({min_interval}h) for '{drug.drug_id}' cannot be confirmed safe"
                    ),
                    missing_fields=["medication_history"],
                    provenance=pop_rule.provenance,
                )
            )
        elif patient.medication_history_status == "confirmed_list":
            for med in patient.medications:
                med_matches = med.raw_text.lower() in drug_identifiers or any(
                    ing.ingredient_id.lower() in drug_identifiers for ing in med.ingredients
                )
                if not med_matches:
                    continue

                if med.last_dose_time is None:
                    skipped_checks.append(
                        SkippedCheck(
                            rule_id=f"MIN_INTERVAL_{drug.drug_id.upper()}",
                            rule_type="frequency_limit",
                            reason=(
                                f"Patient history records medication '{med.raw_text}' but last dose timestamp "
                                f"is unknown; cannot verify minimum dosing interval of {min_interval} hours"
                            ),
                            missing_fields=["last_dose_time"],
                            provenance=pop_rule.provenance,
                        )
                    )
                else:
                    delta_seconds = Decimal(
                        str((patient.assessed_at - med.last_dose_time).total_seconds())
                    )
                    elapsed_hours = delta_seconds / Decimal("3600")
                    if Decimal("0") <= elapsed_hours < min_interval:
                        alerts.append(
                            Alert(
                                rule_id=f"MIN_INTERVAL_{drug.drug_id.upper()}",
                                severity=Severity.HIGH,
                                rule_type="frequency_limit",
                                drug_ids=[drug.drug_id],
                                consequence=(
                                    f"Patient received '{med.raw_text}' {elapsed_hours:.1f} hours ago; "
                                    f"minimum interval between doses of '{drug.drug_id}' is {min_interval} hours"
                                ),
                                action=(
                                    f"Delay administration of '{drug.drug_id}' until at least "
                                    f"{min_interval} hours post-prior dose"
                                ),
                                provenance=pop_rule.provenance,
                                unverified=not pop_rule.provenance.verified,
                                step_number=step.step_number,
                            )
                        )

    return alerts, skipped_checks


def verify_administration_rate(
    patient: Patient,
    steps: list[PlanStepDraft],
    registry: ClinicalRegistry,
) -> tuple[list[Alert], list[SkippedCheck]]:
    """Verify that proposed infusion and administration rates obey formulary ceilings.

    Safety Property (Rule R8, AUB-ENG-02):
    - Validates step.rate_mg_per_min against pop_rule.max_rate_mg_per_min.
    - If rate exceeds ceiling, emits HIGH alert.
    """
    alerts: list[Alert] = []
    skipped_checks: list[SkippedCheck] = []
    pop_cat = str(patient.age.population_category)

    for step in steps:
        if (
            step.action_type != ActionType.administer
            or not step.drug_id
            or step.rate_mg_per_min is None
        ):
            continue

        drug = registry.get_drug(step.drug_id)
        if drug is None:
            continue

        pop_rule = drug.population_rules.get(pop_cat)
        if pop_rule is None or pop_rule.max_rate_mg_per_min is None:
            continue

        max_rate = pop_rule.max_rate_mg_per_min
        if step.rate_mg_per_min > max_rate:
            alerts.append(
                Alert(
                    rule_id=f"RATE_LIMIT_{drug.drug_id.upper()}",
                    severity=Severity.HIGH,
                    rule_type="rate_limit",
                    drug_ids=[drug.drug_id],
                    consequence=(
                        f"Proposed administration rate of {step.rate_mg_per_min} mg/min for "
                        f"'{drug.drug_id}' exceeds maximum safe rate of {max_rate} mg/min"
                    ),
                    action=(
                        f"Reduce infusion rate of '{drug.drug_id}' to at most {max_rate} mg/min"
                    ),
                    provenance=pop_rule.provenance,
                    unverified=not pop_rule.provenance.verified,
                    step_number=step.step_number,
                )
            )

    return alerts, skipped_checks
