"""Preloaded scenarios endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from triagerag.api.schemas import ScenarioDetail, ScenarioSummary
from triagerag.contracts.scenarios import get_preloaded_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

SCENARIO_METADATA = {
    "BLOCK": {
        "id": "BLOCK",
        "title": "Drug-Drug Interaction (BLOCK)",
        "description": "Patient on Sildenafil (PDE5 inhibitor) presenting with acute chest pain.",
        "what_it_demonstrates": (
            "Rule R11: Deterministic contraindication blocking Nitroglycerin with no override "
            "allowed. Nitroglycerin is struck through."
        ),
        "expected_verdict": "BLOCKED",
    },
    "UNVERIFIED": {
        "id": "UNVERIFIED",
        "title": "Missing Vitals & Unknown History (UNVERIFIED)",
        "description": (
            "Hypotensive patient with unknown weight, missing systolic BP, and unconfirmed history."
        ),
        "what_it_demonstrates": (
            "Rule R2: Fail-closed architecture. Missing vitals emit SkippedCheck; verdict "
            "cannot be cleared."
        ),
        "expected_verdict": "UNVERIFIED",
    },
    "HIGH": {
        "id": "HIGH",
        "title": "Cross-Reactivity Alert with Clinician Override (HIGH)",
        "description": (
            "8-year-old child with severe sepsis and penicillin allergy prescribed Ceftriaxone."
        ),
        "what_it_demonstrates": (
            "HIGH severity alert requires logged clinician override with clinical rationale "
            "(dissimilar side-chain)."
        ),
        "expected_verdict": "CHECKED_ALERTS",
    },
    "CLEAN": {
        "id": "CLEAN",
        "title": "Acute Anaphylaxis Guideline Conformance (CHECKED_CLEAR)",
        "description": "30-year-old adult presenting with acute anaphylaxis, confirmed NKDA.",
        "what_it_demonstrates": (
            "Safe guideline extraction and deterministic verification approving Epinephrine IM."
        ),
        "expected_verdict": "CHECKED_CLEAR",
    },
}


@router.get("", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [ScenarioSummary(**meta) for meta in SCENARIO_METADATA.values()]


@router.get("/{scenario_id}", response_model=ScenarioDetail)
def get_scenario(scenario_id: str) -> ScenarioDetail:
    key = scenario_id.upper()
    if key not in SCENARIO_METADATA:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found. Available: BLOCK, UNVERIFIED, HIGH, CLEAN",
        )
    meta = SCENARIO_METADATA[key]
    patient, overrides = get_preloaded_scenario(key)
    return ScenarioDetail(
        id=meta["id"],
        title=meta["title"],
        description=meta["description"],
        what_it_demonstrates=meta["what_it_demonstrates"],
        expected_verdict=meta["expected_verdict"],
        patient=patient,
        overrides=overrides,
    )
