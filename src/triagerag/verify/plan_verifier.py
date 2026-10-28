"""Deterministic machine plan verifier.

Safety Property (Rules R1, R2, R11, Section 10, RAG-02):
1. BLOCK alerts permanently strike through steps (BLOCKED_STRUCK_THROUGH).
2. Withhold steps are never evaluated as administrations. Withholding a blocked drug is APPROVED.
3. HIGH alerts require explicit logged override (FLAGGED_HIGH).
4. Citations, lexical overlap, child-node specificity, drug/action-cue support, and drug scan
   must pass before any step can be APPROVED.
5. No code path exists to approve a BLOCKED step (Rule R11).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from triagerag.contracts.enums import ActionType, Severity, StepStatus
from triagerag.contracts.schemas import (
    Alert,
    CalculatedDoseReport,
    PlanDraft,
    RetrievedChunk,
    SkippedCheck,
    VerifiedStep,
)
from triagerag.engine.rule_engine import evaluate_plan
from triagerag.verify.citations import verify_citation, verify_step_support
from triagerag.verify.drug_scan import scan_narrative_for_drug_leaks

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient
    from triagerag.engine.registry import ClinicalRegistry


def verify_plan(
    patient: Patient,
    draft: PlanDraft,
    baseline_alerts: list[Alert],
    retrieved_chunks: list[RetrievedChunk],
    registry: ClinicalRegistry,
) -> tuple[list[VerifiedStep], list[Alert], list[SkippedCheck], list[CalculatedDoseReport]]:
    """Machine-verify all steps in a drafted protocol plan.

    Executes:
    1. Pass 2 clinical rule evaluation (withhold semantics enforced).
    2. Drug ID formulary validity check.
    3. Lexicon drug prose scan.
    4. Exact citation groundedness, overlap threshold, child-node rule, and step support check.
    5. StepStatus lattice mapping.
    """
    plan_alerts, plan_skips, dose_reports = evaluate_plan(
        patient=patient,
        steps=draft.steps,
        baseline_alerts=baseline_alerts,
        registry=registry,
    )

    all_alerts = baseline_alerts + plan_alerts
    all_skips = plan_skips
    dose_by_drug = {r.drug_id: r for r in dose_reports}
    chunk_map = {c.chunk_id: c for c in retrieved_chunks}

    verified_steps: list[VerifiedStep] = []

    for step in draft.steps:
        rejection_reasons: list[str] = []
        triggered_rule_ids: list[str] = []
        status: StepStatus = StepStatus.APPROVED
        citations_ok = True
        overlap_score = Decimal("0.0")
        support_reason: str | None = None

        # 1. Validate drug_id exists in formulary if administer/withhold
        if step.action_type in (ActionType.administer, ActionType.withhold) and (
            not step.drug_id or not registry.get_drug(step.drug_id)
        ):
            status = StepStatus.BLOCKED_STRUCK_THROUGH
            rejection_reasons.append(
                f"Unknown drug_id '{step.drug_id}' not found in verified formulary"
            )

        # 2. Prose drug leak scan (Section 10)
        leaks = scan_narrative_for_drug_leaks(
            narrative=step.narrative_instruction,
            bound_drug_id=step.drug_id,
            registry=registry,
        )
        if leaks:
            rejection_reasons.append(
                f"Prose drug leak detected in narrative instruction: {', '.join(leaks)}"
            )
            if status != StepStatus.BLOCKED_STRUCK_THROUGH:
                status = StepStatus.FLAGGED_MODERATE

        # 3. Groundedness citations check + drug/action-cue support check (Section 10, RAG-02)
        resolved_cited_chunks: list[RetrievedChunk] = []
        if not step.citations:
            citations_ok = False
            rejection_reasons.append("Missing mandatory chunk citation")
        else:
            for cit in step.citations:
                is_cit_valid, ov_score, cit_err = verify_citation(
                    citation=cit,
                    retrieved_chunks=retrieved_chunks,
                    narrative_instruction=step.narrative_instruction,
                )
                overlap_score = max(overlap_score, Decimal(str(ov_score)))
                if not is_cit_valid:
                    citations_ok = False
                    if cit_err:
                        rejection_reasons.append(cit_err)
                elif cit.chunk_id in chunk_map:
                    resolved_cited_chunks.append(chunk_map[cit.chunk_id])

        if citations_ok and status != StepStatus.BLOCKED_STRUCK_THROUGH:
            is_supported, support_msg = verify_step_support(
                step=step,
                cited_chunks=resolved_cited_chunks,
                registry=registry,
            )
            support_reason = support_msg
            if not is_supported:
                citations_ok = False
                rejection_reasons.append(support_msg)

        # 4. Check rule alerts impacting this specific step
        # Note: Withhold steps are NEVER treated as administrations (Section 6)
        if step.action_type == ActionType.administer and step.drug_id:
            # Check for alerts matching this drug
            for alert in all_alerts:
                if step.drug_id in alert.drug_ids:
                    triggered_rule_ids.append(alert.rule_id)
                    if alert.severity == Severity.BLOCK:
                        # Rule R11: Absolute block, no override path
                        status = StepStatus.BLOCKED_STRUCK_THROUGH
                        rejection_reasons.append(
                            f"Contraindicated by BLOCK alert [{alert.rule_id}]: {alert.consequence}"
                        )
                    elif alert.severity == Severity.HIGH:
                        if status != StepStatus.BLOCKED_STRUCK_THROUGH:
                            status = StepStatus.FLAGGED_HIGH
                            rejection_reasons.append(
                                f"Warning: HIGH severity alert [{alert.rule_id}]: "
                                f"{alert.consequence}"
                            )
                    elif alert.severity == Severity.MODERATE:
                        if status not in (
                            StepStatus.BLOCKED_STRUCK_THROUGH,
                            StepStatus.FLAGGED_HIGH,
                        ):
                            status = StepStatus.FLAGGED_MODERATE

            # Check dose report for this drug
            if step.drug_id in dose_by_drug:
                d_rep = dose_by_drug[step.drug_id]
                if d_rep.status == "EXCEEDS_CEILING":
                    if status != StepStatus.BLOCKED_STRUCK_THROUGH:
                        status = StepStatus.FLAGGED_HIGH
                    rejection_reasons.append(d_rep.notes)
                elif d_rep.status == "UNVERIFIED_MISSING_CAP":
                    if status not in (
                        StepStatus.BLOCKED_STRUCK_THROUGH,
                        StepStatus.FLAGGED_HIGH,
                    ):
                        status = StepStatus.UNVERIFIED_MISSING_DATA
                    rejection_reasons.append(d_rep.notes)

        elif step.action_type == ActionType.withhold:
            # Withholding a blocked drug is safe and correct (Section 6)
            pass

        # 5. Citation status overrides if not already blocked
        if not citations_ok and status != StepStatus.BLOCKED_STRUCK_THROUGH:
            status = StepStatus.CITATION_UNVERIFIED

        # Final verified step record
        verified_steps.append(
            VerifiedStep(
                draft=step,
                status=status,
                triggered_rule_ids=sorted(set(triggered_rule_ids)),
                rejection_reasons=rejection_reasons,
                citation_verified=citations_ok,
                citation_overlap_score=overlap_score,
                support_reason=support_reason,
            )
        )

    return verified_steps, plan_alerts, all_skips, dose_reports
