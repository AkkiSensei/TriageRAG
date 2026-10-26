"""Clinical unit parsing, boundary checks, and exact Decimal unit conversion.

Safety Property (Rule R8):
Unit conversions use exact Decimal multipliers without floating-point math.
Ambiguous unit abbreviations (e.g. naked 'u', 'cc', 'mgs') are strictly rejected.
Magnitude tripwires detect >=10x or <=0.1x deviations.
"""

from __future__ import annotations

import re
from decimal import Decimal

from triagerag.contracts.enums import DoseUnit
from triagerag.contracts.schemas import ExplicitDose

# Disallowed dangerous medical abbreviations (ISMP List of Error-Prone Abbreviations)
DANGEROUS_ABBREVIATIONS = {
    "u": "Dangerous abbreviation 'u' for units; write 'IU'",
    "cc": "Dangerous abbreviation 'cc'; write 'mL'",
    "ug": "Dangerous abbreviation 'ug' for microgram; write 'mcg'",
    "mgs": "Ambiguous plural 'mgs'; write 'mg'",
    "mcgs": "Ambiguous plural 'mcgs'; write 'mcg'",
}

# Controlled exact Decimal unit conversion multipliers to base units:
# Base mass: mg
# Base volume: mL
MASS_CONVERSIONS_TO_MG: dict[DoseUnit, Decimal] = {
    DoseUnit.mcg: Decimal("0.001"),
    DoseUnit.mg: Decimal("1"),
    DoseUnit.g: Decimal("1000"),
}

PER_KG_CONVERSIONS_TO_MG_PER_KG: dict[DoseUnit, Decimal] = {
    DoseUnit.mcg_per_kg: Decimal("0.001"),
    DoseUnit.mg_per_kg: Decimal("1"),
}


def parse_dose_string(dose_str: str) -> ExplicitDose:
    """Parse a dose string (e.g. '500 mg', '0.5 g') into ExplicitDose with Decimal amount.

    Rejects ambiguous, dangerous, or unparseable unit strings.
    """
    clean_str = dose_str.strip()
    if not clean_str:
        raise ValueError("Cannot parse empty dose string")

    # Match numeric portion and unit portion
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/_]+)$", clean_str)
    if not match:
        raise ValueError(f"Invalid dose string format: '{dose_str}'")

    amount_str, unit_str = match.groups()
    amount = Decimal(amount_str)

    if amount <= Decimal("0"):
        raise ValueError(f"Dose amount must be positive, got: {amount}")

    unit_lower = unit_str.lower()
    if unit_lower in DANGEROUS_ABBREVIATIONS:
        raise ValueError(DANGEROUS_ABBREVIATIONS[unit_lower])

    # Map to DoseUnit
    unit_map: dict[str, DoseUnit] = {
        "mcg": DoseUnit.mcg,
        "mg": DoseUnit.mg,
        "g": DoseUnit.g,
        "ml": DoseUnit.mL,
        "iu": DoseUnit.IU,
        "mcg/kg": DoseUnit.mcg_per_kg,
        "mg/kg": DoseUnit.mg_per_kg,
        "mcg/kg/min": DoseUnit.mcg_per_kg_min,
        "mg/kg/hr": DoseUnit.mg_per_kg_hr,
    }

    if unit_lower not in unit_map:
        raise ValueError(f"Unrecognized or unsupported clinical dose unit: '{unit_str}'")

    return ExplicitDose(amount=amount, unit=unit_map[unit_lower])


def convert_dose(dose: ExplicitDose, target_unit: DoseUnit) -> ExplicitDose:
    """Convert an ExplicitDose to a target DoseUnit using exact Decimal math."""
    if dose.unit == target_unit:
        return ExplicitDose(amount=dose.amount, unit=target_unit)

    # Mass conversions
    if dose.unit in MASS_CONVERSIONS_TO_MG and target_unit in MASS_CONVERSIONS_TO_MG:
        val_in_mg = dose.amount * MASS_CONVERSIONS_TO_MG[dose.unit]
        target_amount = val_in_mg / MASS_CONVERSIONS_TO_MG[target_unit]
        return ExplicitDose(amount=target_amount, unit=target_unit)

    # Weight-based mass conversions
    if (
        dose.unit in PER_KG_CONVERSIONS_TO_MG_PER_KG
        and target_unit in PER_KG_CONVERSIONS_TO_MG_PER_KG
    ):
        val_in_mg_kg = dose.amount * PER_KG_CONVERSIONS_TO_MG_PER_KG[dose.unit]
        target_amount = val_in_mg_kg / PER_KG_CONVERSIONS_TO_MG_PER_KG[target_unit]
        return ExplicitDose(amount=target_amount, unit=target_unit)

    raise ValueError(f"Cannot convert incompatible units: from '{dose.unit}' to '{target_unit}'")


def check_magnitude_tripwire(
    requested: Decimal, reference: Decimal, factor: Decimal = Decimal("10")
) -> bool:
    """Trigger a tripwire warning if requested is >= factor * reference or <= reference / factor."""
    if reference <= Decimal("0") or requested <= Decimal("0"):
        return True
    ratio = requested / reference
    return ratio >= factor or ratio <= (Decimal("1") / factor)
