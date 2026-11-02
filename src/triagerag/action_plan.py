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

from triagerag.contracts.enums import ActionType, StepStatus, Verdict
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
    desc = (
        f"{len(measured)} of {total} standard triage parameters measured ({pct}%). "
        f"{len(assumed)} assumed demo default(s) do not count toward measured completeness."
    )

    return DataQualityReport(
        total_parameters=total,
        measured_count=len(measured),
        assumed_count=len(assumed),
        missing_count=len(missing),
        completeness_pct=pct,
        completeness_description=desc,
        measured_fields=measured,
        assumed_fields=assumed,
        missing_fields=missing,
    )


def evaluate_confidence(
    verdict: Verdict,
    report: EngineReport,
    quality: DataQualityReport,
) -> ConfidenceReport:
    """Compute a deterministic, explainable confidence evaluation of the triage verdict.

    Safety Disclosure (Rule R1, R3, R10):
    Confidence level and heuristic score reflect deterministic rule decisiveness, case data
    completeness, and protocol verification status. They are NOT empirical clinical probabilities.
    """
    reasons: list[str] = []

    if verdict == Verdict.BLOCKED:
        level: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
        rule_evidence = "DECISIVE_INTERLOCK"
        score = Decimal("0.90")
        if quality.missing_count > 0:
            case_completeness = f"INCOMPLETE ({quality.missing_count} parameters unmeasured)"
            headline = (
                "Safety Interlock Decisive: Contraindication Identified (Case Record Incomplete)"
            )
            reasons.append(
                "Rule R11 Interlock: Absolute contraindication decisively identified from confirmed clinical records."
            )
            reasons.append(
                f"Overall intake record is incomplete ({quality.missing_count} parameter(s) unmeasured); however, Rule R11 strictly prohibits plan execution regardless of other findings."
            )
            reasons.append(
                "High confidence reflects certainty in the contraindication rule hit, NOT overall clinical case completeness."
            )
        else:
            case_completeness = "COMPLETE (100% measured)"
            headline = (
                "Safety Interlock Decisive: Absolute Contraindication Identified on Complete Case"
            )
            reasons.append(
                "Rule R11 Interlock: Absolute contraindication decisively identified from confirmed clinical records."
            )
            reasons.append(
                "Patient presentation is complete across all standard triage parameters."
            )
            reasons.append(
                "Plan execution is unconditionally prohibited under clinical safety policy."
            )

    elif verdict == Verdict.UNVERIFIED:
        level = "LOW"
        rule_evidence = "FAIL_CLOSED_INSUFFICIENT_DATA"
        score = Decimal("0.20")
        case_completeness = f"INCOMPLETE ({quality.missing_count} parameters missing/unknown)"
        headline = "Safety Status Unverified: Intake Clinical Data Incomplete"
        if quality.missing_fields:
            missing_sample = ", ".join(quality.missing_fields[:3])
            reasons.append(
                f"Required clinical parameters missing or unobtainable: {missing_sample}."
            )
        reasons.append(
            "Under fail-closed Rule R2, missing parameters cannot be presumed normal or safe."
        )
        reasons.append("Mandatory deferral to attending clinician before initiating treatment.")

    elif verdict == Verdict.CHECKED_ALERTS:
        if quality.missing_count > 0:
            level = "LOW"
            score = Decimal("0.50")
            rule_evidence = "CLINICAL_WARNINGS_ON_INCOMPLETE_DATA"
            case_completeness = f"INCOMPLETE ({quality.missing_count} parameters unmeasured)"
            headline = "Clinical Warnings Identified on Incomplete Presentation (Attending Review Required)"
            reasons.append(
                f"Plan evaluated with safety warnings, but {quality.missing_count} parameter(s) remain unmeasured."
            )
            reasons.append(
                "Attending clinician evaluation required to assess warnings against missing baseline vitals."
            )
        elif quality.assumed_count > 0:
            level = "MEDIUM"
            score = Decimal("0.60")
            rule_evidence = "CLINICAL_WARNINGS_WITH_ASSUMED_DEFAULTS"
            case_completeness = f"PARTIAL ({quality.assumed_count} demo defaults)"
            headline = "Clinical Warnings Identified (Relies on Assumed Demo Defaults)"
            reasons.append(
                f"Plan evaluated with safety warnings; {quality.assumed_count} parameter(s) relied on assumed demo defaults."
            )
            reasons.append("Requires documented clinician override and vital signs verification.")
        else:
            level = "MEDIUM"
            score = Decimal("0.75")
            rule_evidence = "CLINICAL_WARNINGS_ON_COMPLETE_DATA"
            case_completeness = "COMPLETE (100% measured)"
            headline = "Clinical Warnings Identified on Complete Presentation (Clinician Override Required)"
            reasons.append(
                "Input data is complete; alerts indicate non-blocking clinical warnings requiring clinician override."
            )

    else:
        # CHECKED_CLEAR
        if quality.assumed_count == 0 and quality.missing_count == 0:
            level = "HIGH"
            score = Decimal("0.95")
            rule_evidence = "VERIFIED_CLEAR_ON_MEASURED_DATA"
            case_completeness = "COMPLETE (100% measured)"
            headline = "All Configured Safety Checks Verified Clear on Complete Measured Data"
            reasons.append("100% of standard triage parameters are clinically measured.")
            reasons.append(
                "Zero contraindications or formulary limit violations detected across active ruleset."
            )
        elif quality.assumed_count > 0:
            level = "MEDIUM"
            score = Decimal("0.65")
            rule_evidence = "CLEAR_WITH_ASSUMED_DEFAULTS"
            case_completeness = f"PARTIAL ({quality.assumed_count} demo defaults)"
            headline = "Safety Rules Clear with Assumed Demo Defaults (Measurements Required)"
            reasons.append(
                f"All active safety rules passed, but {quality.assumed_count} parameter(s) used conservative demo defaults."
            )
            reasons.append("Vital signs must be measured clinically before administering therapy.")
        else:
            level = "LOW"
            score = Decimal("0.35")
            rule_evidence = "CLEAR_ON_PARTIAL_DATA"
            case_completeness = f"PARTIAL ({quality.missing_count} parameters unmeasured)"
            headline = "Low Clinical Data Completeness: Clearance Cannot Be Confirmed"
            reasons.append("Unmeasured clinical parameters prevent high-confidence clearance.")

    return ConfidenceReport(
        level=level,
        score=score,
        headline=headline,
        rule_evidence=rule_evidence,
        case_completeness=case_completeness,
        reasons=reasons,
        data_quality=quality,
    )


def _build_immediate_actions(
    report: EngineReport,
    verdict: Verdict,
    response: TriageResponse | None = None,
) -> list[ActionStep]:
    actions: list[ActionStep] = []

    # First, capture any machine-verified withhold instructions from verified protocol steps
    if response and response.verified_steps:
        for vs in response.verified_steps:
            if (
                vs.status == StepStatus.APPROVED
                and vs.draft.action_type in (ActionType.withhold, "withhold")
                and vs.citation_verified
            ):
                drug_label = vs.draft.drug_id or "Medication"
                reason_desc = (
                    vs.support_reason
                    or f"Machine-verified protocol directive to withhold {drug_label}."
                )
                actions.append(
                    ActionStep(
                        title=f"WITHHOLD -- {drug_label}",
                        description=f"Verified protocol instruction: WITHHOLD {drug_label}. {reason_desc}",
                        reason="Evidence-verified protocol withholding directive (non-administration action).",
                        rule_id=None,
                        urgency="immediate",
                    )
                )

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
        if not any("STOP" in a.title for a in actions):
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

    # In BLOCKED or UNVERIFIED state, strictly inhibit medication administration (Rule R11, R2)
    if response.engine.verdict in (Verdict.BLOCKED, Verdict.UNVERIFIED):
        return []

    for vs in response.verified_steps:
        draft = vs.draft
        if draft.drug_id is None:
            continue

        # CRITICAL SAFETY GATE: Only individually APPROVED steps with verified citations become instructions
        if vs.status != StepStatus.APPROVED:
            continue
        if not vs.citation_verified:
            continue
        # CRITICAL SAFETY GATE: Only 'administer' action types can enter medication administration instructions.
        # Withhold, monitor, diagnostic, maneuver steps must NEVER be represented as administration instructions.
        if draft.action_type not in (ActionType.administer, "administer"):
            continue

        dose_str = "Not specified"
        route_str = "Not specified"
        dose_source = "Standard protocol dosage"
        if draft.requested_dose:
            dose_str = f"{draft.requested_dose.amount} {draft.requested_dose.unit.value}"
            if (
                response.patient
                and getattr(response.patient.weight_kg, "source", "") == "measured"
                and response.patient.weight_kg.value is not None
            ):
                dose_source = (
                    f"Protocol dose ({dose_str}) verified against measured weight "
                    f"({response.patient.weight_kg.value} kg)"
                )
            elif (
                response.patient
                and getattr(response.patient.weight_kg, "source", "") == "estimated"
                and response.patient.weight_kg.value is not None
            ):
                dose_source = (
                    f"Protocol dose ({dose_str}) checked against estimated weight "
                    f"({response.patient.weight_kg.value} kg, demo default)"
                )
            else:
                dose_source = f"Standard fixed protocol dose ({dose_str}); weight not documented"

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

        # Clinical rationale derived directly from machine verification artifacts
        if vs.support_reason:
            why_chosen = vs.support_reason
        elif draft.citations:
            cit = draft.citations[0]
            doc_ref = cit.doc_id or protocol_title or "Protocol"
            sec_ref = f", section '{cit.section}'" if cit.section else ""
            why_chosen = (
                f"Proposed under protocol '{doc_ref}'{sec_ref}; machine-verified "
                f"with citation overlap score {vs.citation_overlap_score}."
            )
        else:
            why_chosen = (
                f"Step verified and approved against retrieved protocol '{protocol_title or 'Emergency Protocol'}'. "
                f"Citation overlap score: {vs.citation_overlap_score}."
            )

        # Excluded alternatives derived directly from actual case artifacts
        why_not: list[str] = []
        for other_step in response.verified_steps:
            if (
                other_step.draft.step_number != draft.step_number
                and other_step.status != StepStatus.APPROVED
            ):
                other_drug = other_step.draft.drug_id or f"Step {other_step.draft.step_number}"
                reasons = (
                    "; ".join(other_step.rejection_reasons)
                    if other_step.rejection_reasons
                    else "rejected by safety verifier"
                )
                why_not.append(f"{other_drug} [{other_step.status.value}]: {reasons}")

        for alert in response.engine.baseline_alerts:
            if alert.rule_type in ("allergy", "ddi", "contraindication") and (
                not draft.drug_id or draft.drug_id.lower() not in alert.consequence.lower()
            ):
                why_not.append(f"{alert.rule_id} [{alert.severity.value}]: {alert.consequence}")

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


def _build_unapproved_draft_steps(response: TriageResponse) -> list[str]:
    """Capture proposed draft steps that failed verification or are prohibited."""
    unapproved: list[str] = []
    verdict = response.engine.verdict

    for vs in response.verified_steps:
        draft = vs.draft
        drug_label = draft.drug_id or (
            draft.action_type.value
            if hasattr(draft.action_type, "value")
            else str(draft.action_type)
        )
        dose_label = (
            f" {draft.requested_dose.amount} {draft.requested_dose.unit.value}"
            if draft.requested_dose
            else ""
        )
        route_label = f" {draft.route.value.upper()}" if draft.route else ""
        step_desc = f"Step {draft.step_number} ({drug_label}{dose_label}{route_label})"

        if verdict == Verdict.BLOCKED or vs.status == StepStatus.BLOCKED_STRUCK_THROUGH:
            reasons = (
                "; ".join(vs.rejection_reasons)
                if vs.rejection_reasons
                else "Absolute contraindication interlock active"
            )
            unapproved.append(
                f"{step_desc} [BLOCKED]: {reasons} -- Administration strictly prohibited (Rule R11)."
            )
        elif verdict == Verdict.UNVERIFIED or vs.status == StepStatus.UNVERIFIED_MISSING_DATA:
            unapproved.append(
                f"{step_desc} [UNVERIFIED]: Clinical presentation incomplete under fail-closed Rule R2 -- Administration prohibited."
            )
        elif vs.status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION:
            reasons = (
                "; ".join(vs.rejection_reasons)
                if vs.rejection_reasons
                else "Requires attending clinician assessment"
            )
            unapproved.append(
                f"{step_desc} [REQUIRES_CLINICIAN_CONFIRMATION]: {reasons} -- NOT approved for administration without attending signoff."
            )
        elif vs.status == StepStatus.FLAGGED_HIGH:
            reasons = (
                "; ".join(vs.rejection_reasons)
                if vs.rejection_reasons
                else "High-severity safety warning flagged"
            )
            unapproved.append(
                f"{step_desc} [FLAGGED_HIGH]: {reasons} -- NOT approved for administration without documented override."
            )
        elif not vs.citation_verified:
            unapproved.append(
                f"{step_desc} [CITATION_UNVERIFIED]: Evidence citation unverified against protocol corpus -- Administration prohibited."
            )
        elif vs.status != StepStatus.APPROVED:
            reasons = (
                "; ".join(vs.rejection_reasons)
                if vs.rejection_reasons
                else "Failed machine verification"
            )
            unapproved.append(f"{step_desc} [{vs.status.value}]: {reasons} -- NOT approved.")

    return unapproved


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


def _build_rejected_alternatives(
    verdict: Verdict,
    unapproved_steps: list[str] | None = None,
) -> list[str]:
    """Plain-language explanations of why other lattice states or proposed steps were rejected."""
    alternatives: list[str] = []

    if verdict == Verdict.BLOCKED:
        alternatives.extend(
            [
                "Rejected CHECKED_CLEAR: Rule R11 strictly prohibits clearing a plan when an active BLOCK alert is present.",
                "Rejected CHECKED_ALERTS: Absolute contraindication interlocks cannot be overridden by clinician discretion.",
                "Rejected UNVERIFIED: Sufficient structured clinical parameters were verified to definitively prove contraindication.",
            ]
        )
    elif verdict == Verdict.UNVERIFIED:
        alternatives.extend(
            [
                "Rejected CHECKED_CLEAR: Rule R2 fail-closed boundary prohibits assuming safety when required parameters are missing.",
                "Rejected BLOCKED: Incomplete data prevents confirming active contraindications; missing parameters trigger UNVERIFIED.",
                "Rejected CHECKED_ALERTS: Partial safety cannot be granted while unverified safety interlocks remain unperformed.",
            ]
        )
    elif verdict == Verdict.CHECKED_ALERTS:
        alternatives.extend(
            [
                "Rejected CHECKED_CLEAR: High-severity clinical warnings fired, requiring active clinician override before administration.",
                "Rejected BLOCKED: Fired alerts are classified as HIGH (clinical warning), not non-overridable BLOCK contraindications.",
                "Rejected UNVERIFIED: Patient parameters were sufficiently resolved to verify all applicable safety rules.",
            ]
        )
    else:
        alternatives.extend(
            [
                "Rejected BLOCKED: Zero drug-drug, allergy, or physiological contraindication rules fired.",
                "Rejected CHECKED_ALERTS: Zero clinical warnings or formulary ceiling violations detected.",
                "Rejected UNVERIFIED: All intake histories and vital signs required for active rulesets were successfully verified.",
            ]
        )

    if unapproved_steps:
        for u in unapproved_steps:
            alternatives.append(f"Rejected Proposed Step: {u}")

    return alternatives


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

    unapproved = _build_unapproved_draft_steps(response)

    return ActionPlan(
        immediate_actions=_build_immediate_actions(report, verdict, response),
        medications=_build_medications(response),
        unapproved_draft_steps=unapproved,
        monitoring_steps=_build_monitoring(report),
        escalation_steps=_build_escalation(report, verdict),
        assumptions=tags,
        rule_hits=_build_rule_hits(report),
        missing_data=_build_missing_data(report),
        decision_summary=_build_decision_summary(verdict, report, confidence),
        confidence=confidence,
        protocol_match_summary=protocol_match_summary,
        why_decision=_build_why_decision(verdict, report, response),
        rejected_alternatives=_build_rejected_alternatives(verdict, unapproved),
    )
