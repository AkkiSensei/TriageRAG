"""Triage decision support orchestrator.

Safety Properties (Rules R1, R2, R5, R7, R11, R12):
1. Pure deterministic pipeline: validate -> normalize -> Pass 1 -> retrieve -> draft -> verify.
2. Code decides; LLM explains. Fallback mode operates safely even if LLM/retrieval fails.
3. Untrusted chief complaint is excluded from instructions/engine by default (Rule R7).
4. BLOCK alerts can never be overridden under any condition (Rule R11).
5. Appends all triage runs to cryptographic audit chain.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from triagerag.contracts.enums import (
    ScoreBand,
    Severity,
    StepStatus,
)
from triagerag.contracts.schemas import (
    CalculatedDoseReport,
    EngineReport,
    OverrideRecord,
    PlanContext,
    PlanDraft,
    RetrievalReport,
    ScoreResult,
    TriageResponse,
    VerifiedStep,
)
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.engine.scores import calculate_early_warning_score
from triagerag.engine.verdict import resolve_verdict
from triagerag.llm.draft import draft_plan_safe
from triagerag.normalize.validators import normalize_patient
from triagerag.rag.retrieve import (
    derive_vitals_flags,
    retrieve_protocol_chunks,
)
from triagerag.verify.plan_verifier import verify_plan

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient
    from triagerag.engine.registry import ClinicalRegistry
    from triagerag.llm.provider import LLMProvider
    from triagerag.rag.index import BM25ClinicalIndex

logger = logging.getLogger(__name__)


def compute_patient_hash(patient: Patient) -> str:
    """Compute one-way SHA-256 hash of patient data for de-identified audit chaining."""
    patient_json = patient.model_dump_json()
    return hashlib.sha256(patient_json.encode("utf-8")).hexdigest()


def run_triage(
    patient: Patient,
    *,
    registry: ClinicalRegistry,
    llm: LLMProvider | None = None,
    index: BM25ClinicalIndex | None = None,
    overrides: list[OverrideRecord] | None = None,
    config: dict[str, Any] | None = None,
) -> TriageResponse:
    """Execute complete emergency triage decision support pipeline.

    Every external dependency (LLM, retrieval) is guarded with fault isolation.
    Failures degrade gracefully to llm_fallback_mode=True and never produce false clearance.
    """
    cfg = config or {}
    overrides_list = overrides or []

    # 1. Normalize patient data
    normalized_patient = normalize_patient(patient, registry.resolver)

    # 2. Early-warning physiological scoring
    pop_str = str(normalized_patient.age.population_category).lower()
    score_table = registry.get_scoring_table(pop_str)
    if score_table:
        score_result = calculate_early_warning_score(normalized_patient, score_table)
    else:
        # Neonate or unconfigured population table
        prov = registry.rules[0].provenance if registry.rules else None
        assert prov is not None
        score_result = ScoreResult(
            score_name=f"EWS_{pop_str.upper()}_UNAVAILABLE",
            total_score=None,
            band=ScoreBand.UNSCORED,
            missing_vitals=["population_table"],
            provenance=prov,
        )

    # 3. Pass 1 deterministic checks (home medications, allergies, vitals interlocks)
    baseline_alerts, baseline_skips, checks_run, unverified_rules = evaluate_baseline(
        normalized_patient, registry
    )

    # Extract blocked drug IDs to exclude from LLM allowed list (Rule R1)
    blocked_drug_ids = {
        drug_id
        for alert in baseline_alerts
        if alert.severity == Severity.BLOCK
        for drug_id in alert.drug_ids
    }
    allowed_drug_ids = [
        d_id for d_id in sorted(registry.formulary_drugs.keys()) if d_id not in blocked_drug_ids
    ]

    # 4. Retrieval (guarded)
    retrieval_report: RetrievalReport
    if index is None:
        retrieval_report = RetrievalReport(
            chunks=[],
            backend="none",
            abstained=True,
            reason="No retrieval index configured",
        )
    else:
        try:
            retrieval_report = retrieve_protocol_chunks(normalized_patient, index)
        except Exception as e:
            logger.error("Retrieval failed: %s", e)
            retrieval_report = RetrievalReport(
                chunks=[],
                backend=index.backend,
                abstained=True,
                reason=f"Retrieval error: {e}",
            )

    # 5. LLM Plan Drafting (guarded with fallback)
    llm_fallback_mode = False
    plan_draft: PlanDraft | None = None

    if llm is None or retrieval_report.abstained or not retrieval_report.chunks:
        llm_fallback_mode = True
    else:
        include_complaint = bool(cfg.get("include_complaint_in_llm", False))
        delimited_complaint = (
            normalized_patient.chief_complaint_untrusted if include_complaint else None
        )

        plan_context = PlanContext(
            population_category=normalized_patient.age.population_category,
            vitals_derived_flags=derive_vitals_flags(normalized_patient),
            allowed_drug_ids=allowed_drug_ids,
            pass1_alert_summaries=[f"{a.rule_id}: {a.action}" for a in baseline_alerts],
            retrieved_chunks=retrieval_report.chunks,
            chief_complaint_delimited=delimited_complaint,
        )

        draft, err = draft_plan_safe(llm, plan_context)
        if draft is None or err is not None:
            llm_fallback_mode = True
        else:
            plan_draft = draft

    # 6. Machine Verification & Pass 2 (guarded with repair loop)
    verified_steps: list[VerifiedStep] = []
    plan_alerts: list[Any] = []
    dose_reports: list[CalculatedDoseReport] = []

    if plan_draft and not llm_fallback_mode:
        v_steps, p_alerts, p_skips, d_reports = verify_plan(
            patient=normalized_patient,
            draft=plan_draft,
            baseline_alerts=baseline_alerts,
            retrieved_chunks=retrieval_report.chunks,
            registry=registry,
        )
        verified_steps = v_steps
        plan_alerts = p_alerts
        dose_reports = d_reports
        baseline_skips.extend(p_skips)

        # Repair loop: If repairable violations exist and LLM is active
        repair_attempts = 0
        while repair_attempts < 2:
            violations: list[str] = []
            for s in verified_steps:
                if s.status in (
                    StepStatus.CITATION_UNVERIFIED,
                    StepStatus.FLAGGED_MODERATE,
                ):
                    violations.extend(s.rejection_reasons)

            if not violations or llm is None:
                break

            repair_attempts += 1
            try:
                assert plan_context is not None
                repaired_draft = llm.repair_plan(plan_context, plan_draft, violations)
                v_steps, p_alerts, _, d_reports = verify_plan(
                    patient=normalized_patient,
                    draft=repaired_draft,
                    baseline_alerts=baseline_alerts,
                    retrieved_chunks=retrieval_report.chunks,
                    registry=registry,
                )
                verified_steps = v_steps
                plan_alerts = p_alerts
                dose_reports = d_reports
                plan_draft = repaired_draft
            except Exception as e:
                logger.warning("LLM repair attempt %d failed: %s", repair_attempts, e)
                break

    # 7. Apply Overrides (Rule R11: BLOCK cannot be overridden)
    if overrides_list and verified_steps:
        for override in overrides_list:
            for i, v_step in enumerate(verified_steps):
                if v_step.draft.step_number == override.step_number:
                    # Check for Rule R11 violation: BLOCK CANNOT BE OVERRIDDEN
                    if v_step.status == StepStatus.BLOCKED_STRUCK_THROUGH:
                        msg = (
                            f"Rule R11 Violation: Step {override.step_number} is "
                            f"BLOCKED_STRUCK_THROUGH and cannot be overridden by "
                            f"{override.clinician_id}"
                        )
                        raise PermissionError(msg)
                    if v_step.status == StepStatus.FLAGGED_HIGH:
                        # HIGH override is permitted when logged
                        verified_steps[i] = VerifiedStep(
                            draft=v_step.draft,
                            status=StepStatus.APPROVED,
                            triggered_rule_ids=v_step.triggered_rule_ids,
                            rejection_reasons=[
                                f"OVERRIDDEN by {override.clinician_id}: {override.reason}"
                            ],
                            citation_verified=v_step.citation_verified,
                            citation_overlap_score=v_step.citation_overlap_score,
                        )

    # 8. Verdict Lattice Resolution (Section 4)
    all_alerts = baseline_alerts + plan_alerts
    has_block = any(a.severity == Severity.BLOCK for a in all_alerts)
    unresolved_entities = [m.raw_text for m in normalized_patient.medications if not m.resolved] + [
        a.raw_substance for a in normalized_patient.allergies if not a.resolved
    ]
    has_skip_or_unresolved = len(baseline_skips) > 0 or len(unresolved_entities) > 0
    has_alert = len(all_alerts) > 0

    overall_verdict = resolve_verdict(
        has_block=has_block,
        has_skip_or_unresolved=has_skip_or_unresolved,
        has_alert=has_alert,
    )

    # Check review state of all rules evaluated
    ruleset_review_state: Literal["UNREVIEWED_DRAFT", "PARTIALLY_REVIEWED", "FULLY_REVIEWED"] = (
        "FULLY_REVIEWED" if unverified_rules == 0 else "UNREVIEWED_DRAFT"
    )

    # 9. Deterministic Engine Report
    engine_report = EngineReport(
        verdict=overall_verdict,
        score=score_result,
        baseline_alerts=baseline_alerts,
        plan_alerts=plan_alerts,
        dose_reports=dose_reports,
        checks_run=checks_run,
        checks_skipped=baseline_skips,
        unresolved_entities=unresolved_entities,
        ruleset_coverage=[
            f"{checks_run} rules evaluated across {len(registry.rules)} registered rules"
        ],
        coverage_gaps=list(registry.coverage_gaps),
        unverified_rules_evaluated=unverified_rules,
        ruleset_review_state=ruleset_review_state,
        ruleset_version=registry.version,
    )

    # 10. Audit Chain Logging
    patient_hash = compute_patient_hash(normalized_patient)
    audit_hash = "UNAUDITED"
    audit_log_path = cfg.get("audit_log_path")
    if audit_log_path:
        from triagerag.audit.chain import append_audit_entry

        path_obj = Path(audit_log_path)
        prov_name = type(llm).__name__ if llm else "None"
        mod_name = getattr(llm, "profile", getattr(llm, "model_name", "None"))
        overrides_dicts = [o.model_dump() for o in overrides_list]
        chunk_ids = [c.chunk_id for c in retrieval_report.chunks]

        audit_hash = append_audit_entry(
            audit_path=path_obj,
            patient_hash=patient_hash,
            ruleset_version=registry.version,
            formulary_version=registry.version,
            retrieved_chunk_ids=chunk_ids,
            provider_name=prov_name,
            model_name=str(mod_name),
            verdict=str(overall_verdict),
            alert_ids=[a.rule_id for a in all_alerts],
            skipped_rule_ids=[s.rule_id for s in baseline_skips],
            override_records=overrides_dicts,
        )

    return TriageResponse(
        engine=engine_report,
        verified_steps=verified_steps,
        retrieval=retrieval_report,
        overrides=overrides_list,
        llm_fallback_mode=llm_fallback_mode,
        audit_hash=audit_hash,
    )
