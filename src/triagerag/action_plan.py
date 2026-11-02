"""Deterministic action plan generator for TriageRAG.

Safety Property (Rule R1, R2, R11):
  All action plans are derived from deterministic engine output only.
  No LLM text is used to determine actions, urgency, medications, or escalation.
  Plans from BLOCKED or UNVERIFIED states are appropriately conservative.
  BLOCK-level alerts strictly inhibit medication administration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from triagerag.contracts.enums import StepStatus, Verdict
from triagerag.contracts.schemas import (
    ActionPlan,
    ActionStep,
    EscalationStep,
    MedicationInstruction,
    MonitoringStep,
)

if TYPE_CHECKING:
    from triagerag.contracts.schemas import EngineReport, TriageResponse

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

    # In BLOCKED or UNVERIFIED state, never recommend medications
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
        if draft.requested_dose:
            dose_str = f"{draft.requested_dose.amount} {draft.requested_dose.unit.value}"
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
        hits.append(f"{alert.rule_id} [{alert.severity.value}]: {alert.rule_type}")
    for alert in report.plan_alerts:
        hits.append(f"{alert.rule_id} [{alert.severity.value}]: {alert.rule_type}")
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
    verdict: Verdict, report: EngineReport, assumption_tags: list[str]
) -> str:
    band = report.score.band.value if report.score else "UNKNOWN"
    alert_count = len(report.baseline_alerts) + len(report.plan_alerts)
    assumed_note = (
        f" Note: {len(assumption_tags)} vital(s) used conservative demo defaults."
        if assumption_tags
        else ""
    )

    if verdict == Verdict.BLOCKED:
        return (
            f"Administration is BLOCKED. {alert_count} safety rule(s) fired, "
            f"including at least one hard BLOCK interlock. EWS band: {band}."
            f"{assumed_note} Do not proceed without senior clinician re-evaluation."
        )
    elif verdict == Verdict.UNVERIFIED:
        return (
            f"Result is UNVERIFIED. Insufficient or missing patient data prevented "
            f"safe plan verification. EWS band: {band}.{assumed_note} "
            "Escalate to attending clinician before initiating treatment."
        )
    elif alert_count > 0:
        return (
            f"Plan verified with {alert_count} alert(s) requiring clinician review. "
            f"EWS band: {band}.{assumed_note} Proceed only after reviewing highlighted warnings."
        )
    else:
        return (
            f"All intake safety checks verified clear. EWS band: {band}.{assumed_note} "
            "Follow the protocol steps below. Monitor and escalate per schedule."
        )


def generate_action_plan(
    response: TriageResponse,
    assumption_tags: list[str] | None = None,
) -> ActionPlan:
    """Generate a deterministic, human-readable action plan from the engine report.

    Pure function: no side effects, zero LLM calls (Rule R1).
    """
    tags = list(assumption_tags) if assumption_tags is not None else []
    report = response.engine
    verdict = report.verdict

    return ActionPlan(
        immediate_actions=_build_immediate_actions(report, verdict),
        medications=_build_medications(response),
        monitoring_steps=_build_monitoring(report),
        escalation_steps=_build_escalation(report, verdict),
        assumptions=tags,
        rule_hits=_build_rule_hits(report),
        missing_data=_build_missing_data(report),
        decision_summary=_build_decision_summary(verdict, report, tags),
    )
