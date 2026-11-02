"""Deterministic action plan and clinical credibility engine for TriageRAG.

Safety Property (Rule R1, R2, R11):
  All action plans are derived from deterministic engine output only.
  No LLM text is used to determine actions, urgency, medications, or escalation.
  Plans from BLOCKED or UNVERIFIED states are appropriately conservative.
  BLOCK-level alerts strictly inhibit medication administration.
  Confidence and data quality evaluations are purely deterministic.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from triagerag.contracts.enums import StepStatus, Verdict
from triagerag.contracts.schemas import (
    ActionPlan,
    ActionStep,
    ConfidenceReport,
    DataQualityReport,
    EscalationStep,
    MedicationInstruction,
    MonitoringStep,
)

if TYPE_CHECKING:
    from triagerag.contracts.schemas import EngineReport, Patient, TriageResponse

_SCORE_MONITORING: dict[str, tuple[str, str]] = {
    "RED": (
        "Every 5 minutes",
        "Continuous physiological monitoring; escalate immediately to senior clinician",
    ),
    "ORANGE": (
        "Every 15 minutes",
        "Close observation; escalate if any vital sign parameter deteriorates",
    ),
    "YELLOW": (
        "Every 30 minutes",
        "Routine observation; escalate if new symptoms develop or score worsens",
    ),
    "GREEN": ("Every 60 minutes", "Standard observation; escalate if patient condition changes"),
    "UNKNOWN": (
        "Every 30 minutes",
        "Physiological status unverified; perform full vital signs reassessment",
    ),
}


def evaluate_data_quality(
    patient: Patient | None,
    assumption_tags: list[str] | None = None,
) -> DataQualityReport:
    """Evaluate completeness and provenance of patient input parameters."""
    if patient is None:
        return DataQualityReport(
            total_parameters=0,
            measured_count=0,
            assumed_count=0,
            missing_count=0,
            completeness_pct=Decimal("0.0"),
            measured_fields=[],
            assumed_fields=[],
            missing_fields=["Patient record missing"],
        )

    measured: list[str] = []
    assumed: list[str] = []
    missing: list[str] = []

    # 1. Vitals audit
    vital_items = [
        ("heart_rate_bpm", "Heart rate"),
        ("systolic_bp_mmhg", "Systolic BP"),
        ("diastolic_bp_mmhg", "Diastolic BP"),
        ("respiratory_rate_bpm", "Respiratory rate"),
        ("spo2_percent", "Oxygen saturation (SpO2)"),
        ("temperature_c", "Temperature"),
    ]
    vitals = patient.vitals
    for f_name, label in vital_items:
        v = getattr(vitals, f_name, None)
        if v is None:
            missing.append(label)
        elif getattr(v, "source", "") == "measured" and v.value is not None:
            measured.append(f"{label}: {v.value}")
        elif getattr(v, "source", "") == "estimated" and v.value is not None:
            assumed.append(f"{label}: {v.value} (assumed demo default)")
        else:
            missing.append(label)

    # 2. Consciousness / neurological status
    c = getattr(vitals, "consciousness", None)
    gcs = getattr(vitals, "gcs_total", None)
    if c is not None and getattr(c, "source", "") == "measured" and c.value is not None:
        val = getattr(c.value, "value", str(c.value))
        measured.append(f"Consciousness: {val}")
    elif gcs is not None and getattr(gcs, "source", "") == "measured" and gcs.value is not None:
        measured.append(f"GCS: {gcs.value}")
    else:
        missing.append("Consciousness/GCS")

    # 3. Patient weight
    if (
        getattr(patient.weight_kg, "source", "") == "measured"
        and patient.weight_kg.value is not None
    ):
        measured.append(f"Weight: {patient.weight_kg.value} kg")
    elif (
        getattr(patient.weight_kg, "source", "") == "estimated"
        and patient.weight_kg.value is not None
    ):
        assumed.append(f"Weight: {patient.weight_kg.value} kg (assumed demo default)")
    else:
        missing.append("Weight")

    # 4. Allergy history
    if patient.allergy_history_status in ("confirmed_none", "confirmed_nkda", "confirmed_list"):
        st_label = (
            "NKDA"
            if patient.allergy_history_status == "confirmed_nkda"
            else f"{len(patient.allergies)} documented"
        )
        measured.append(f"Allergy history ({st_label})")
    else:
        missing.append(f"Allergy history ({patient.allergy_history_status})")

    # 5. Medication history
    if patient.medication_history_status in ("confirmed_none", "confirmed_nkda", "confirmed_list"):
        st_label = (
            "None"
            if patient.medication_history_status == "confirmed_none"
            else f"{len(patient.medications)} active"
        )
        measured.append(f"Medication history ({st_label})")
    else:
        missing.append(f"Medication history ({patient.medication_history_status})")

    # 6. Demographics
    age_unit = getattr(patient.age.unit, "value", str(patient.age.unit))
    measured.append(f"Age: {patient.age.value} {age_unit}")
    measured.append(f"Sex: {patient.sex}")

    # 7. Explicit assumption tags (demo defaults applied)
    if assumption_tags:
        for tag in assumption_tags:
            clean = tag.replace("[ASSUMED DEMO DEFAULT]", "").replace("(not measured)", "").strip()
            prefix = clean.lower().split(":")[0].strip()
            if not any(prefix in a.lower() for a in assumed):
                assumed.append(f"{clean} (assumed demo default)")
                for m in list(missing):
                    if prefix in m.lower():
                        missing.remove(m)

    total = len(measured) + len(assumed) + len(missing)
    pct = Decimal(str(round((len(measured) / total) * 100, 1))) if total > 0 else Decimal("0.0")

    return DataQualityReport(
        total_parameters=total,
        measured_count=len(measured),
        assumed_count=len(assumed),
        missing_count=len(missing),
        completeness_pct=pct,
        measured_fields=measured,
        assumed_fields=assumed,
        missing_fields=missing,
    )


def evaluate_confidence(
    verdict: Verdict,
    report: EngineReport,
    quality: DataQualityReport,
) -> ConfidenceReport:
    """Compute a deterministic, explainable confidence evaluation of the triage verdict."""
    reasons: list[str] = []

    if verdict == Verdict.BLOCKED:
        level: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
        score = Decimal("0.95")
        headline = "HIGH CONFIDENCE -- Absolute Safety Interlock Triggered"
        reasons.append(
            "Definitive drug-drug or physiologic contraindication identified from confirmed patient records."
        )
        reasons.append(
            "Rule R11 strictly prohibits plan execution when an absolute BLOCK rule fires."
        )

    elif verdict == Verdict.UNVERIFIED:
        level = "LOW"
        score = Decimal("0.30")
        headline = "LOW CONFIDENCE -- Incomplete Clinical Data (Fail-Closed Safety)"
        if quality.missing_fields:
            missing_sample = ", ".join(quality.missing_fields[:3])
            reasons.append(
                f"Required clinical parameters missing or unobtainable: {missing_sample}."
            )
        reasons.append("Under Rule R2, missing parameters cannot be presumed safe.")
        reasons.append("Mandatory deferral to attending clinician before initiating treatment.")

    elif verdict == Verdict.CHECKED_ALERTS:
        if quality.assumed_count > 0:
            level = "MEDIUM"
            score = Decimal("0.70")
            headline = "MEDIUM CONFIDENCE -- Clinical Alerts Flagged with Assumed Defaults"
            reasons.append(
                f"Plan evaluated with safety warnings, but {quality.assumed_count} parameter(s) relied on assumed demo defaults."
            )
            reasons.append("Requires documented clinician override and vital signs verification.")
        else:
            level = "HIGH"
            score = Decimal("0.85")
            headline = "HIGH CONFIDENCE -- Clinical Alerts Require Attending Review"
            reasons.append(
                "Input data is complete; alerts indicate non-blocking clinical warnings requiring clinician override."
            )

    else:
        # CHECKED_CLEAR
        if quality.assumed_count == 0 and quality.missing_count == 0:
            level = "HIGH"
            score = Decimal("0.95")
            headline = "HIGH CONFIDENCE -- All Safety Checks Verified on Measured Data"
            reasons.append(
                "100% of required physiological vitals and clinical histories are measured."
            )
            reasons.append(
                "Zero contraindications or formulary limit violations detected across active ruleset."
            )
        elif quality.assumed_count > 0:
            level = "MEDIUM"
            score = Decimal("0.70")
            headline = "MEDIUM CONFIDENCE -- Verified Clear Using Assumed Demo Defaults"
            reasons.append(
                f"All active safety rules passed, but {quality.assumed_count} vital(s) used conservative demo defaults."
            )
            reasons.append("Vital signs must be measured clinically before administering therapy.")
        else:
            level = "LOW"
            score = Decimal("0.40")
            headline = "LOW CONFIDENCE -- Low Clinical Data Completeness"
            reasons.append("Low parameter completeness prevents high-confidence clearance.")

    return ConfidenceReport(
        level=level,
        score=score,
        headline=headline,
        reasons=reasons,
        data_quality=quality,
    )


def _build_immediate_actions(report: EngineReport, verdict: Verdict) -> list[ActionStep]:
    actions: list[ActionStep] = []

    if verdict == Verdict.BLOCKED:
        block_rules = [a for a in report.baseline_alerts if a.severity.value == "BLOCK"]
        for alert in block_rules:
            actions.append(
                ActionStep(
                    title=f"STOP -- Blocked by {alert.rule_id}",
                    description=f"Rule {alert.rule_id} ({alert.rule_type}) has issued a BLOCK. Do not proceed.",
                    reason=f"Hard clinical safety interlock {alert.rule_id} triggered. Administration contraindicated.",
                    rule_id=alert.rule_id,
                    urgency="immediate",
                )
            )
        if not actions:
            actions.append(
                ActionStep(
                    title="STOP -- Administration blocked",
                    description="A BLOCK safety rule fired. Do not administer the planned medication.",
                    reason="Hard clinical safety interlock prevented plan execution.",
                    urgency="immediate",
                )
            )

    elif verdict == Verdict.UNVERIFIED:
        actions.append(
            ActionStep(
                title="Escalate -- Insufficient data for safe plan verification",
                description="One or more required fields are missing or unresolved. Defer treatment decisions to the attending clinician.",
                reason="Engine cannot verify safety without complete patient data (Rule R2: fail-closed).",
                urgency="urgent",
            )
        )

    else:
        # CHECKED_CLEAR or CHECKED_ALERTS
        high_alerts = [a for a in report.baseline_alerts if a.severity.value in ("HIGH", "BLOCK")]
        if high_alerts:
            for alert in high_alerts:
                actions.append(
                    ActionStep(
                        title=f"Caution -- {alert.rule_id} ({alert.severity.value})",
                        description="Rule requires clinician evaluation and documented override before proceeding.",
                        reason=f"Rule {alert.rule_id} ({alert.rule_type}) flagged a potential safety concern.",
                        rule_id=alert.rule_id,
                        urgency="urgent",
                    )
                )
        else:
            actions.append(
                ActionStep(
                    title="Proceed with protocol",
                    description="No blocking safety alerts detected. Follow the matched protocol steps below.",
                    reason="All intake safety checks passed clear.",
                    urgency="routine",
                )
            )

    return actions


def _build_medications(response: TriageResponse) -> list[MedicationInstruction]:
    meds: list[MedicationInstruction] = []
    protocol_title = response.retrieved_protocol_title or (
        response.retrieval.chunks[0].doc_id
        if response.retrieval and response.retrieval.chunks
        else None
    )

    # In BLOCKED or UNVERIFIED state, strictly inhibit medication administration
    if response.engine.verdict in (Verdict.BLOCKED, Verdict.UNVERIFIED):
        return []

    for vs in response.verified_steps:
        draft = vs.draft
        if draft.drug_id is None:
            continue

        # Inhibit blocked steps
        if vs.status == StepStatus.BLOCKED_STRUCK_THROUGH or "BLOCK" in vs.status.value:
            continue

        dose_str = "Not specified"
        route_str = "Not specified"
        dose_source = "Protocol standard titration"
        if draft.requested_dose:
            dose_str = f"{draft.requested_dose.amount} {draft.requested_dose.unit.value}"
            dose_source = f"Standard emergency protocol dose ({dose_str})"
            if (
                response.patient
                and getattr(response.patient.weight_kg, "source", "") == "estimated"
            ):
                dose_source += f" checked against weight {response.patient.weight_kg.value} kg (assumed demo default)"
            elif (
                response.patient and getattr(response.patient.weight_kg, "source", "") == "measured"
            ):
                dose_source += (
                    f" checked against measured weight {response.patient.weight_kg.value} kg"
                )

        if draft.route:
            route_str = draft.route.value

        timing_str = "Immediate"
        if draft.relative_time_minutes is not None and draft.relative_time_minutes > 0:
            timing_str = f"At T+{draft.relative_time_minutes} min"
        elif draft.frequency_hours:
            timing_str = f"Every {draft.frequency_hours}h"

        warnings = list(vs.rejection_reasons) if vs.rejection_reasons else []
        contraindications = [
            a.rule_id
            for a in (response.engine.baseline_alerts + response.engine.plan_alerts)
            if a.rule_id and draft.drug_id and draft.drug_id.lower() in a.rule_id.lower()
        ]

        # Clinical rationale for why this drug was selected & why alternatives were avoided
        drug_name_lower = draft.drug_id.lower()
        if "epinephrine" in drug_name_lower:
            why_chosen = f"First-line alpha/beta-agonist indicated for acute anaphylaxis under protocol '{protocol_title or 'Emergency Management'}'."
            why_not = [
                "Antihistamines withheld as monotherapy because they do not reverse respiratory or cardiovascular collapse.",
                "Oral route contraindicated due to airway compromise risk.",
            ]
        elif "ceftriaxone" in drug_name_lower:
            why_chosen = f"Broad-spectrum 3rd generation cephalosporin indicated under '{protocol_title or 'Infection Management'}'; dissimilar R1 side-chain permits clinician override despite penicillin allergy history."
            why_not = [
                "Direct aminopenicillins strictly contraindicated due to documented penicillin allergy history.",
                "Narrow-spectrum beta-lactams excluded by allergy cross-reactivity interlocks.",
            ]
        elif "nitroglycerin" in drug_name_lower:
            why_chosen = f"Coronary vasodilator indicated for acute chest pain under '{protocol_title or 'Chest Pain Management'}'."
            why_not = [
                "Calcium channel blockers deferred until initial response to nitrates is assessed.",
            ]
        else:
            why_chosen = f"Formulary intervention aligned with presentation under '{protocol_title or 'Emergency Protocol'}'."
            why_not = ["Alternative agents excluded by deterministic safety filters."]

        meds.append(
            MedicationInstruction(
                medication_name=draft.drug_id,
                dose=dose_str,
                route=route_str,
                timing=timing_str,
                indication=draft.narrative_instruction[:200]
                if draft.narrative_instruction
                else "See protocol",
                contraindications=contraindications,
                warnings=warnings,
                source_protocol=protocol_title,
                why_chosen=why_chosen,
                why_not_alternatives=why_not,
                dose_computation_source=dose_source,
            )
        )

    return meds


def _build_monitoring(report: EngineReport) -> list[MonitoringStep]:
    steps: list[MonitoringStep] = []
    band = report.score.band.value if report.score else "UNKNOWN"
    freq, trigger = _SCORE_MONITORING.get(band, _SCORE_MONITORING["UNKNOWN"])

    steps.append(
        MonitoringStep(
            monitor="Vital signs (HR, BP, RR, SpO2)",
            frequency=freq,
            trigger=trigger,
            reason=f"Early warning score band is {band} -- requires scheduled physiological vigilance.",
        )
    )

    if report.baseline_alerts:
        steps.append(
            MonitoringStep(
                monitor="Treatment response & safety alert resolution",
                frequency="Following each clinical intervention",
                trigger="Any unexpected clinical deterioration or adverse reaction",
                reason="Active baseline alerts require continuous observation for resolution or escalation.",
            )
        )

    return steps


def _build_escalation(report: EngineReport, verdict: Verdict) -> list[EscalationStep]:
    steps: list[EscalationStep] = []

    if verdict == Verdict.BLOCKED:
        steps.append(
            EscalationStep(
                when="Immediately",
                escalate_to="Senior Attending Clinician / Specialist",
                reason="A BLOCK safety rule fired. Proposed therapy is contraindicated and requires expert review.",
            )
        )
    elif verdict == Verdict.UNVERIFIED:
        steps.append(
            EscalationStep(
                when="Before administering any medication",
                escalate_to="Attending Triage Officer / Clinician",
                reason="Critical patient data is unverified or missing (Rule R2). Mandatory clinical review required.",
            )
        )

    band = report.score.band.value if report.score else "UNKNOWN"
    if band in ("RED", "ORANGE"):
        steps.append(
            EscalationStep(
                when=f"Early warning score band is {band}",
                escalate_to="Medical Emergency Team / Resuscitation Specialist",
                reason=f"Physiological score band {band} denotes critical physiological instability.",
            )
        )

    return steps


def _build_rule_hits(report: EngineReport) -> list[str]:
    hits: list[str] = []
    for alert in report.baseline_alerts:
        hits.append(
            f"{alert.rule_id} [{alert.severity.value}]: {alert.rule_type} -- {alert.consequence}"
        )
    for alert in report.plan_alerts:
        hits.append(
            f"{alert.rule_id} [{alert.severity.value}]: {alert.rule_type} -- {alert.consequence}"
        )
    return hits


def _build_missing_data(report: EngineReport) -> list[str]:
    missing: list[str] = []
    for skip in report.checks_skipped:
        missing.append(f"Check skipped: {skip.rule_id} -- {skip.reason}")
    for entity in report.unresolved_entities:
        missing.append(f"Unresolved entity: {entity}")
    if report.unverified_reason:
        missing.append(f"Unverified reason: {report.unverified_reason}")
    return missing


def _build_decision_summary(
    verdict: Verdict,
    report: EngineReport,
    confidence: ConfidenceReport,
) -> str:
    band = report.score.band.value if report.score else "UNKNOWN"
    alert_count = len(report.baseline_alerts) + len(report.plan_alerts)
    quality = confidence.data_quality
    assumed_note = (
        f" Note: {quality.assumed_count} parameter(s) used conservative demo defaults."
        if quality.assumed_count > 0
        else ""
    )

    if verdict == Verdict.BLOCKED:
        blockers = [a.rule_id for a in report.baseline_alerts if a.severity.value == "BLOCK"]
        block_text = f" ({', '.join(blockers)})" if blockers else ""
        return (
            f"Administration is strictly BLOCKED by safety interlock{block_text}. "
            f"EWS band: {band}. Confidence: {confidence.level}. "
            f"Do not administer organic nitrates or contraindicated therapy without specialist review."
        )
    elif verdict == Verdict.UNVERIFIED:
        missing_count = quality.missing_count
        return (
            f"Decision is UNVERIFIED due to {missing_count} missing or unresolved clinical parameter(s). "
            f"EWS band: {band}.{assumed_note} "
            f"Fail-closed safety active (Rule R2): escalate to attending clinician before initiating treatment."
        )
    elif alert_count > 0:
        return (
            f"Plan verified with {alert_count} alert(s) requiring clinician review. "
            f"EWS band: {band}. Confidence: {confidence.level}.{assumed_note} "
            "Proceed only after documented clinician override of highlighted warnings."
        )
    else:
        return (
            f"All intake safety checks verified clear across {report.checks_run} evaluated rules. "
            f"EWS band: {band}. Confidence: {confidence.level}.{assumed_note} "
            "Follow protocol instructions below. Monitor and escalate per schedule."
        )


def _build_why_decision(verdict: Verdict, report: EngineReport, response: TriageResponse) -> str:
    """Human-readable plain English clinical explanation of why this verdict was reached."""
    if verdict == Verdict.BLOCKED:
        for alert in report.baseline_alerts:
            if alert.severity.value == "BLOCK":
                return (
                    f"This decision was BLOCKED because safety rule '{alert.rule_id}' fired: {alert.consequence} "
                    f"Under non-negotiable rule R11, absolute contraindication interlocks cannot be overridden."
                )
        return "This decision was BLOCKED because an absolute clinical contraindication interlock triggered."

    elif verdict == Verdict.UNVERIFIED:
        reason = (
            report.unverified_reason
            or "Essential clinical vitals or medication history are incomplete."
        )
        return (
            f"This decision is UNVERIFIED because: {reason}. "
            "Under fail-closed safety rule R2, missing parameters cannot be presumed normal or safe."
        )

    elif verdict == Verdict.CHECKED_ALERTS:
        alerts = [
            f"{a.rule_id} ({a.consequence})"
            for a in report.baseline_alerts
            if a.severity.value == "HIGH"
        ]
        alert_str = "; ".join(alerts) if alerts else "one or more clinical warnings"
        return (
            f"This plan was checked with warnings: {alert_str}. "
            "Under clinical governance, high alerts do not completely block care but require documented clinician assessment and override."
        )

    else:
        return (
            "All deterministic safety interlocks (drug-drug interactions, allergy cross-reactivities, "
            "and physiological threshold limits) evaluated completely clear without triggering alerts."
        )


def _build_rejected_alternatives(verdict: Verdict) -> list[str]:
    """Plain-language explanations of why other lattice states were rejected."""
    if verdict == Verdict.BLOCKED:
        return [
            "Rejected CHECKED_CLEAR: Rule R11 strictly prohibits clearing a plan when an active BLOCK alert is present.",
            "Rejected CHECKED_ALERTS: Absolute contraindication interlocks cannot be overridden by clinician discretion.",
            "Rejected UNVERIFIED: Sufficient structured clinical parameters were verified to definitively prove contraindication.",
        ]
    elif verdict == Verdict.UNVERIFIED:
        return [
            "Rejected CHECKED_CLEAR: Rule R2 fail-closed boundary prohibits assuming safety when required parameters are missing.",
            "Rejected BLOCKED: Incomplete data prevents confirming active contraindications; missing parameters trigger UNVERIFIED.",
            "Rejected CHECKED_ALERTS: Partial safety cannot be granted while unverified safety interlocks remain unperformed.",
        ]
    elif verdict == Verdict.CHECKED_ALERTS:
        return [
            "Rejected CHECKED_CLEAR: High-severity clinical warnings fired, requiring active clinician override before administration.",
            "Rejected BLOCKED: Fired alerts are classified as HIGH (clinical warning), not non-overridable BLOCK contraindications.",
            "Rejected UNVERIFIED: Patient parameters were sufficiently resolved to verify all applicable safety rules.",
        ]
    else:
        return [
            "Rejected BLOCKED: Zero drug-drug, allergy, or physiological contraindication rules fired.",
            "Rejected CHECKED_ALERTS: Zero clinical warnings or formulary ceiling violations detected.",
            "Rejected UNVERIFIED: All intake histories and vital signs required for active rulesets were successfully verified.",
        ]


def generate_action_plan(
    response: TriageResponse,
    assumption_tags: list[str] | None = None,
) -> ActionPlan:
    """Generate a deterministic, human-readable action plan and credibility assessment.

    Pure function: no side effects, zero LLM calls (Rule R1).
    """
    tags = list(assumption_tags) if assumption_tags is not None else []
    report = response.engine
    verdict = report.verdict

    patient = response.input_patient or response.patient
    quality = evaluate_data_quality(patient, tags)
    confidence = evaluate_confidence(verdict, report, quality)

    protocol_title = response.retrieved_protocol_title or (
        response.retrieval.chunks[0].doc_id
        if response.retrieval and response.retrieval.chunks
        else None
    )
    protocol_match_summary = None
    if protocol_title:
        chunk_count = len(response.retrieval.chunks) if response.retrieval else 0
        backend = response.retrieval.backend.upper() if response.retrieval else "BM25"
        protocol_match_summary = f"Primary protocol match: '{protocol_title}' (retrieved via {backend} with {chunk_count} evidence chunk(s))."
    elif response.retrieval and response.retrieval.abstained:
        protocol_match_summary = f"Protocol retrieval abstained: {response.retrieval.abstain_code} ({response.retrieval.reason or 'No match'})."

    return ActionPlan(
        immediate_actions=_build_immediate_actions(report, verdict),
        medications=_build_medications(response),
        monitoring_steps=_build_monitoring(report),
        escalation_steps=_build_escalation(report, verdict),
        assumptions=tags,
        rule_hits=_build_rule_hits(report),
        missing_data=_build_missing_data(report),
        decision_summary=_build_decision_summary(verdict, report, confidence),
        confidence=confidence,
        protocol_match_summary=protocol_match_summary,
        why_decision=_build_why_decision(verdict, report, response),
        rejected_alternatives=_build_rejected_alternatives(verdict),
    )
