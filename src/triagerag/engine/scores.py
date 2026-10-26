"""Deterministic early-warning scoring engine (NEWS2/PEWS).

Safety Property:
Never defaults missing vital signs to normal. If any required physiological vital
is missing or unknown, emits ScoreBand.UNSCORED with an explicit list of missing vitals.
Scores Consciousness using AVPU+C including New Confusion 'C'.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from triagerag.contracts.enums import ScoreBand
from triagerag.contracts.schemas import ScoreResult

if TYPE_CHECKING:
    from triagerag.contracts.data_schemas import EWSTable
    from triagerag.contracts.schemas import Patient


def calculate_early_warning_score(patient: Patient, table: EWSTable) -> ScoreResult:
    """Calculate physiological early-warning score strictly from patient vitals and scoring table.

    Returns ScoreBand.UNSCORED if any parameter is unknown or missing.
    """
    v = patient.vitals
    vitals_map: dict[str, Any] = {
        "heart_rate_bpm": v.heart_rate_bpm.value,
        "systolic_bp_mmhg": v.systolic_bp_mmhg.value,
        "respiratory_rate_bpm": v.respiratory_rate_bpm.value,
        "spo2_percent": v.spo2_percent.value,
        "supplemental_o2": (
            v.supplemental_o2.value if v.supplemental_o2.value in ("yes", "no") else None
        ),
        "temperature_c": v.temperature_c.value,
        "consciousness": v.consciousness.value,
    }

    # Identify all distinct parameters required by this table
    required_parameters = {row.parameter for row in table.rows}
    missing_vitals: list[str] = []

    for param in sorted(required_parameters):
        val = vitals_map.get(param)
        if val is None:
            missing_vitals.append(param)

    # Fail closed on missing vitals
    if missing_vitals:
        return ScoreResult(
            score_name=table.table_name,
            total_score=None,
            band=ScoreBand.UNSCORED,
            subscores={},
            missing_vitals=missing_vitals,
            provenance=table.provenance,
        )

    # Calculate subscore for each parameter
    subscores: dict[str, int] = {}
    has_extreme_individual_score = False

    for param in sorted(required_parameters):
        val = vitals_map[param]
        matched_score: int | None = None

        for row in table.rows:
            if row.parameter != param:
                continue

            # Check string value match
            if row.string_value is not None:
                if str(val) == row.string_value:
                    matched_score = row.score
                    break
            # Check numeric range match
            elif row.min_value is not None and row.max_value is not None:
                dec_val = Decimal(str(val))
                if row.min_value <= dec_val <= row.max_value:
                    matched_score = row.score
                    break

        if matched_score is None:
            # Value outside authored bounds; treat as unscored / missing
            missing_vitals.append(f"{param}_out_of_bounds")
            matched_score = 0

        subscores[param] = matched_score
        if matched_score >= 3:
            has_extreme_individual_score = True

    if missing_vitals:
        return ScoreResult(
            score_name=table.table_name,
            total_score=None,
            band=ScoreBand.UNSCORED,
            subscores=subscores,
            missing_vitals=missing_vitals,
            provenance=table.provenance,
        )

    total_score = sum(subscores.values())

    # Map total score to band
    resolved_band = ScoreBand.UNSCORED
    for band_key, (low, high) in table.bands.items():
        if low <= total_score <= high:
            resolved_band = band_key
            break

    # In adult EWS, any individual extreme score of 3 triggers high clinical risk (RED)
    if (
        table.population == "adult"
        and has_extreme_individual_score
        and resolved_band != ScoreBand.RED
    ):
        resolved_band = ScoreBand.RED

    return ScoreResult(
        score_name=table.table_name,
        total_score=total_score,
        band=resolved_band,
        subscores=subscores,
        missing_vitals=[],
        provenance=table.provenance,
    )
