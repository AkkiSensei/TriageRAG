"""Default vital policy for TriageRAG demo mode.

Safety Property (Rule R2, R4):
  All demo defaults are tagged [ASSUMED DEMO DEFAULT] -- never presented as measured data.
  Missing vitals filled with conservative population-appropriate values only.
  The assumption_tags list MUST accompany every response that uses defaults.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient

# Conservative demo defaults by population category.
# These are broad placeholder values for demo purposes only.
# They carry source="estimated" so engine treats them as uncertain.
# Provenance: AGENT_DRAFT_UNSOURCED -- never present as measured clinical data.
DEFAULT_DEMO_VITALS_BY_AGE_GROUP: dict[str, dict[str, int | Decimal | None]] = {
    "adult": {
        "heart_rate_bpm": 80,
        "systolic_bp_mmhg": 120,
        "diastolic_bp_mmhg": 80,
        "respiratory_rate_bpm": 18,
        "spo2_percent": 98,
        "temperature_c": Decimal("37.0"),
        "gcs_total": None,  # keep unknown -- GCS never assumed
    },
    "paediatric": {
        "heart_rate_bpm": 100,
        "systolic_bp_mmhg": 100,
        "diastolic_bp_mmhg": 65,
        "respiratory_rate_bpm": 22,
        "spo2_percent": 98,
        "temperature_c": Decimal("37.0"),
        "gcs_total": None,
    },
    "neonate": {
        "heart_rate_bpm": 140,
        "systolic_bp_mmhg": 65,
        "diastolic_bp_mmhg": 40,
        "respiratory_rate_bpm": 40,
        "spo2_percent": 97,
        "temperature_c": Decimal("37.0"),
        "gcs_total": None,
    },
}

DEFAULT_DEMO_WEIGHT_KG: dict[str, Decimal] = {
    "adult": Decimal("70"),
    "paediatric": Decimal("20"),
    "neonate": Decimal("3.5"),
}

_VITAL_LABELS: dict[str, str] = {
    "heart_rate_bpm": "Heart rate",
    "systolic_bp_mmhg": "Systolic BP",
    "diastolic_bp_mmhg": "Diastolic BP",
    "respiratory_rate_bpm": "Respiratory rate",
    "spo2_percent": "SpO2",
    "temperature_c": "Temperature",
    "gcs_total": "GCS",
}


def apply_demo_defaults(patient: Patient) -> tuple[Patient, list[str]]:
    """Fill unknown vitals with conservative demo defaults and return assumption tags.

    Rules:
    - Only fills Measured fields where source == "unknown" (value is None).
    - Does NOT override measured or estimated values.
    - Returns an immutable-safe copy of Patient via model_copy.
    - Returns assumption_tags: list of human-readable strings labelled [ASSUMED DEMO DEFAULT].
    - GCS is never filled (unknown is safer than assuming consciousness).
    """
    from triagerag.contracts.schemas import Measured

    try:
        pop = patient.age.population_category
        pop_str = pop.value if hasattr(pop, "value") else str(pop)
    except Exception:
        pop_str = "adult"

    _pop_map = {
        "adult": "adult",
        "child": "paediatric",
        "paediatric": "paediatric",
        "neonate": "neonate",
    }
    pop_key = _pop_map.get(pop_str.lower(), "adult")
    defaults = DEFAULT_DEMO_VITALS_BY_AGE_GROUP.get(
        pop_key, DEFAULT_DEMO_VITALS_BY_AGE_GROUP["adult"]
    )
    weight_default = DEFAULT_DEMO_WEIGHT_KG.get(pop_key, DEFAULT_DEMO_WEIGHT_KG["adult"])

    assumption_tags: list[str] = []
    vitals_updates: dict[str, object] = {}
    vitals = patient.vitals

    for field_name, default_val in defaults.items():
        if default_val is None:
            continue  # GCS -- never assume
        current = getattr(vitals, field_name, None)
        if current is None or not isinstance(current, Measured):
            continue
        if current.source == "unknown":
            vitals_updates[field_name] = Measured(value=default_val, source="estimated")
            label = _VITAL_LABELS.get(field_name, field_name)
            unit_suffix = ""
            if "heart_rate" in field_name:
                unit_suffix = " bpm"
            elif "systolic" in field_name or "diastolic" in field_name:
                unit_suffix = " mmHg"
            elif "respiratory" in field_name:
                unit_suffix = "/min"
            elif "spo2" in field_name:
                unit_suffix = "%"
            elif "temperature" in field_name:
                unit_suffix = " C"

            assumption_tags.append(
                f"[ASSUMED DEMO DEFAULT] {label}: {default_val}{unit_suffix} (not measured)"
            )

    weight_updates: dict[str, object] = {}
    if patient.weight_kg.source == "unknown":
        weight_updates["weight_kg"] = Measured(value=weight_default, source="estimated")
        assumption_tags.append(f"[ASSUMED DEMO DEFAULT] Weight: {weight_default} kg (not measured)")

    if not vitals_updates and not weight_updates:
        return patient, []

    new_vitals = vitals.model_copy(update=vitals_updates) if vitals_updates else vitals
    updated = patient.model_copy(update={"vitals": new_vitals, **weight_updates})
    return updated, assumption_tags
