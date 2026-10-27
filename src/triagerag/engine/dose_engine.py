"""Deterministic clinical dose verification engine.

Safety Property (Rule R8):
All calculations use exact Decimal arithmetic with explicit units.
Enforces weight-based, fixed, and FDC dosage ceilings.
Flags >=10x or <=0.1x magnitude deviations.
Fails closed with UNVERIFIED_MISSING_CAP if limits or weight are unknown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from triagerag.contracts.enums import DoseUnit, RuleStatus
from triagerag.contracts.schemas import CalculatedDoseReport, ExplicitDose
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
    )
