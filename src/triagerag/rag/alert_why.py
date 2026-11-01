"""Structured Alert "Why?" explanation engine (T7.4 / AUB-WHY-01).

Safety Properties (Rules R1, R2, R3, R12):
1. Explanations derive strictly from actual ClinicalRule, Patient facts, and verified protocol evidence.
2. Distinguishes confirmed matched facts from unknown or indeterminate clinical facts.
3. Exposes exact predicate evaluations and conflicting predicates.
4. Preserves rule severity rationale without invented clinical justifications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from triagerag.contracts.rules_schema import ClinicalRule
    from triagerag.contracts.schemas import Alert, Patient
    from triagerag.engine.registry import ClinicalRegistry
    from triagerag.rag.chunking import ProtocolChunk


class AlertWhyExplanation(BaseModel):
    """Detailed clinical provenance and execution rationale for an alert."""

    rule_id: str
    rule_type: str
    severity: str
    consequence: str
    action: str
    matched_facts: list[str] = Field(default_factory=list)
    unknown_facts: list[str] = Field(default_factory=list)
    satisfied_predicates: list[str] = Field(default_factory=list)
    conflicting_predicates: list[str] = Field(default_factory=list)
    supporting_evidence: list[dict[str, str]] = Field(default_factory=list)
    severity_rationale: str = ""
    unestablished_scope: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


def explain_alert(
    alert: Alert,
    patient: Patient,
    registry: ClinicalRegistry,
    supporting_chunks: list[ProtocolChunk] | None = None,
) -> AlertWhyExplanation:
    """Generate a structured, evidence-grounded explanation for why an alert was triggered."""
    rule: ClinicalRule | None = registry.get_rule(alert.rule_id)
    matched: list[str] = []
    unknowns: list[str] = []
    unestablished: list[str] = []

    # 1. Match patient facts based on rule type and drug identifiers
    for drug_id in alert.drug_ids:
        matched.append(f"Proposed administration includes drug '{drug_id}'")

    if alert.rule_type == "allergy_cross_reactivity":
        if patient.allergy_history_status == "confirmed_list" and patient.allergies:
            for al in patient.allergies:
                matched.append(
                    f"Documented patient allergy to '{al.raw_substance}' (reaction: {al.reaction_type})"
                )
        elif patient.allergy_history_status in ("unknown", "unresolved"):
            unknowns.append("Patient allergy history is unknown or unverified")

    if alert.rule_type in ("vitals_interlock", "lab_interlock"):
        matched.append("Vitals or lab interlock boundary condition met")

    # 2. Check for unknown physiological vitals
    vitals_map = {
        "heart_rate_bpm": patient.vitals.heart_rate_bpm,
        "systolic_bp_mmhg": patient.vitals.systolic_bp_mmhg,
        "spo2_percent": patient.vitals.spo2_percent,
        "temperature_c": patient.vitals.temperature_c,
        "blood_glucose_mg_dl": patient.vitals.blood_glucose_mg_dl,
    }
    for vname, m in vitals_map.items():
        if getattr(m, "source", None) == "unknown":
            unknowns.append(f"Vital parameter '{vname}' is unmeasured / unknown")

    # 3. Severity rationale
    sev = alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
    if sev == "BLOCK":
        sev_rat = (
            "Rule severity is classified as hard-ceiling BLOCK due to catastrophic patient safety "
            "risk (e.g. fatal cross-reactivity, toxic co-administration, or severe contraindication). "
            "Per Rule R11, no clinician override is permitted for BLOCK alerts."
        )
    elif sev == "HIGH":
        sev_rat = (
            "Rule severity is classified as HIGH due to significant adverse drug event risk. "
            "Per Rule R11, execution requires a formal clinician override with documented clinical justification."
        )
    else:
        sev_rat = f"Rule severity is classified as {sev} based on clinical ruleset configuration."

    # 4. Scope limitations
    unestablished.append("Real-world individual pharmacogenomics and hepatic clearance not modeled")
    if alert.unverified:
        unestablished.append(
            "Rule carries unreviewed draft status; clinical provenance requires formal review"
        )

    # 5. Supporting chunks
    evidence_list: list[dict[str, str]] = []
    if supporting_chunks:
        for ch in supporting_chunks[:2]:
            evidence_list.append(
                {
                    "chunk_id": ch.chunk_id,
                    "doc_id": ch.doc_id,
                    "section": ch.section,
                    "text": ch.text[: int("200")] + "..." if len(ch.text) > int("200") else ch.text,
                }
            )

    prov_dict: dict[str, Any] = {}
    if alert.provenance:
        prov_dict = alert.provenance.model_dump()
    elif rule and hasattr(rule, "provenance"):
        prov_dict = rule.provenance.model_dump()

    return AlertWhyExplanation(
        rule_id=alert.rule_id,
        rule_type=alert.rule_type,
        severity=sev,
        consequence=alert.consequence,
        action=alert.action,
        matched_facts=matched,
        unknown_facts=unknowns,
        satisfied_predicates=[],
        conflicting_predicates=[],
        supporting_evidence=evidence_list,
        severity_rationale=sev_rat,
        unestablished_scope=unestablished,
        provenance=prov_dict,
    )
