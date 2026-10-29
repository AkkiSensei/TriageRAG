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

from triagerag.contracts.enums import AbstainCode, ActionType, Severity, StepStatus
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
    retrieval_abstain_code: AbstainCode = AbstainCode.NONE,
    *,
    ignore_syndrome_inferred: bool = False,
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
    # Key dose reports by (step_number, drug_id) to prevent multi-step collisions (ENG-05)
    dose_by_step = {
        (r.step_number, r.drug_id): r for r in dose_reports if r.step_number is not None
    }
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
            unapproved_rule_id = f"FORMULARY_VALIDITY_{str(step.drug_id).upper()}"
            if not any(a.rule_id == unapproved_rule_id for a in plan_alerts):
                from triagerag.contracts.schemas import Provenance

                prov = (
                    registry.rules[0].provenance
                    if registry.rules
                    else Provenance(
                        source_doc="SYNTHETIC_FORMULARY_DRAFT",
                        section_ref="TO_BE_RESOLVED",
                        version_or_date="2026-DRAFT",
                    )
                )
                plan_alerts.append(
                    Alert(
                        rule_id=unapproved_rule_id,
                        severity=Severity.BLOCK,
                        rule_type="formulary_validity",
                        drug_ids=[step.drug_id] if step.drug_id else [],
                        consequence=(
                            f"Unknown or unapproved drug_id '{step.drug_id}' not found in "
                            "verified formulary"
                        ),
                        action=f"Do not administer unlisted agent '{step.drug_id}'",
                        provenance=prov,
                        unverified=True,
                    )
                )
                all_alerts = baseline_alerts + plan_alerts
        elif step.action_type == ActionType.administer and step.drug_id and step.route:
            drug_entry = registry.get_drug(step.drug_id)
            if drug_entry:
                allowed_routes = [r.lower() for r in drug_entry.routes]
                if step.route.value.lower() not in allowed_routes:
                    if status != StepStatus.BLOCKED_STRUCK_THROUGH:
                        status = StepStatus.FLAGGED_HIGH
                    rejection_reasons.append(
                        f"Route '{step.route.value}' not approved for '{step.drug_id}'. "
                        f"Allowed routes: {drug_entry.routes}"
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
            step_drug_id = step.drug_id.lower()
            step_drug_identifiers = {step_drug_id}
            drug_obj = registry.get_drug(step.drug_id)
            if drug_obj:
                for ing in drug_obj.ingredient_ids:
                    step_drug_identifiers.add(ing.lower())

            # Check for alerts matching this drug or its active ingredients
            for alert in all_alerts:
                # If alert is specific to a particular step, only match that step (ENG-05)
                if alert.step_number is not None and alert.step_number != step.step_number:
                    continue
                alert_drug_ids = {did.lower() for did in alert.drug_ids}
                if step_drug_identifiers & alert_drug_ids:
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

            # Check dose report for this specific step (step-keyed lookup, ENG-05)
            d_rep = dose_by_step.get((step.step_number, step.drug_id)) or dose_by_drug.get(
                step.drug_id
            )
            if d_rep:
                # Exhaustive handling of all dose calculation statuses (ENG-03)
                if d_rep.status in ("EXCEEDS_CEILING", "MAGNITUDE_WARNING"):
                    if status != StepStatus.BLOCKED_STRUCK_THROUGH:
                        status = StepStatus.FLAGGED_HIGH
                    rejection_reasons.append(d_rep.notes)
                elif d_rep.status == "BELOW_MINIMUM":
                    if status not in (
                        StepStatus.BLOCKED_STRUCK_THROUGH,
                        StepStatus.FLAGGED_HIGH,
                    ):
                        status = (
                            StepStatus.FLAGGED_HIGH
                            if d_rep.magnitude_tripwire_triggered
                            else StepStatus.FLAGGED_MODERATE
                        )
                    rejection_reasons.append(d_rep.notes)
                elif d_rep.status == "UNVERIFIED_MISSING_CAP":
                    if status not in (
                        StepStatus.BLOCKED_STRUCK_THROUGH,
                        StepStatus.FLAGGED_HIGH,
                        StepStatus.FLAGGED_MODERATE,
                    ):
                        status = StepStatus.UNVERIFIED_MISSING_DATA
                    rejection_reasons.append(d_rep.notes)

        elif step.action_type == ActionType.withhold:
            # Withholding a blocked drug is safe and correct (Section 6)
            pass

        # 5. Citation status overrides if not already blocked
        if not citations_ok and status != StepStatus.BLOCKED_STRUCK_THROUGH:
            status = StepStatus.CITATION_UNVERIFIED

        # 6. Syndrome inferred confirmation gate (FG-03, HD-4, ADR 0007)
        if (
            status == StepStatus.APPROVED
            and retrieval_abstain_code == AbstainCode.SYNDROME_INFERRED
            and not ignore_syndrome_inferred
        ):
            status = StepStatus.REQUIRES_CLINICIAN_CONFIRMATION
            rejection_reasons.append(
                "Syndrome inferred from physiological flags (SYNDROME_INFERRED); "
                "requires explicit clinician confirmation before approval"
            )

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
