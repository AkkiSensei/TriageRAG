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
    AbstainCode,
    ScoreBand,
    Severity,
    StepStatus,
)
from triagerag.contracts.schemas import (
    CalculatedDoseReport,
    Clock,
    EngineReport,
    OrchestratorConfig,
    OverrideRecord,
    PlanContext,
    PlanDraft,
    Provenance,
    ProviderMetadata,
    RetrievalReport,
    ScoreResult,
    SkippedCheck,
    SystemClock,
    TriageResponse,
    VerifiedStep,
)
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.engine.scores import calculate_early_warning_score
from triagerag.engine.verdict import resolve_verdict
from triagerag.llm.draft import draft_plan_safe
from triagerag.llm.repair import attempt_plan_repair, sanitize_repair_violations
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
    from triagerag.rag.index import Retriever

logger = logging.getLogger(__name__)

_UNAVAILABLE_SCORE_PROVENANCE = Provenance(
    source_doc="SYNTHETIC_EWS_TABLE_PLACEHOLDER",
    section_ref="TO_BE_RESOLVED",
    version_or_date="2026-DRAFT",
)


def compute_patient_hash(patient: Patient) -> str:
    """Compute one-way SHA-256 hash of patient data for de-identified audit chaining."""
    patient_json = patient.model_dump_json()
    return hashlib.sha256(patient_json.encode("utf-8")).hexdigest()


def run_triage(
    patient: Patient,
    *,
    registry: ClinicalRegistry,
    llm: LLMProvider | None = None,
    index: Retriever | None = None,
    overrides: list[OverrideRecord] | None = None,
    config: OrchestratorConfig | dict[str, Any] | None = None,
    clock: Clock | None = None,
    provider_info: ProviderMetadata | None = None,
) -> TriageResponse:
    """Execute complete emergency triage decision support pipeline.

    Every external dependency (LLM, retrieval) is guarded with fault isolation.
    Failures degrade gracefully to llm_fallback_mode=True and never produce false clearance.
    """
    if config is None:
        cfg = OrchestratorConfig()
    elif isinstance(config, OrchestratorConfig):
        cfg = config
    elif isinstance(config, dict):
        cfg = OrchestratorConfig(**config)
    else:
        raise TypeError(f"Invalid config type: {type(config)}")

    active_clock: Clock = clock if clock is not None else SystemClock()
    overrides_list = overrides or []

    prov_meta = (
        provider_info.model_copy()
        if provider_info is not None
        else ProviderMetadata(
            generation_mode="deterministic_mock",
            requested_profile=getattr(llm, "profile", None) if llm else None,
            retrieval_backend="bm25",
        )
    )

    # 1. Normalize patient data
    normalized_patient = normalize_patient(patient, registry.resolver)

    # 2. Early-warning physiological scoring
    pop_str = str(normalized_patient.age.population_category).lower()
    score_table = registry.get_scoring_table(pop_str)
    if score_table:
        score_result = calculate_early_warning_score(normalized_patient, score_table)
    else:
        # Neonate or unconfigured population table
        score_result = ScoreResult(
            score_name=f"EWS_{pop_str.upper()}_UNAVAILABLE",
            total_score=None,
            band=ScoreBand.UNSCORED,
            missing_vitals=["population_table"],
            provenance=_UNAVAILABLE_SCORE_PROVENANCE,
        )

    # 3. Pass 1 deterministic checks (home medications, allergies, vitals interlocks)
    baseline_alerts, baseline_skips, checks_run, unverified_rules = evaluate_baseline(
        normalized_patient, registry
    )

    # Fail closed on missing/unscored vitals in physiological scoring (Rule R2)
    if score_result.band == ScoreBand.UNSCORED and score_result.missing_vitals:
        baseline_skips.append(
            SkippedCheck(
                rule_id=score_result.score_name or f"EWS_{pop_str.upper()}",
                rule_type="physiological_scoring",
                reason=(
                    "Early-warning physiological score could not be calculated due to "
                    f"missing/unknown vitals: {', '.join(score_result.missing_vitals)}"
                ),
                missing_fields=list(score_result.missing_vitals),
                provenance=score_result.provenance,
            )
        )

    # Fail closed on unknown intake history & unknown patient parameters (Rule R2)
    if normalized_patient.medication_history_status in (
        "incomplete",
        "unknown_unobtainable",
    ) and not any("medications" in s.missing_fields for s in baseline_skips):
        baseline_skips.append(
            SkippedCheck(
                rule_id="INTAKE_MEDICATION_HISTORY",
                rule_type="history_verification",
                reason=(
                    "Medication history status is "
                    f"'{normalized_patient.medication_history_status}' (fail closed)"
                ),
                missing_fields=["medications"],
                provenance=_UNAVAILABLE_SCORE_PROVENANCE,
            )
        )

    if normalized_patient.allergy_history_status in (
        "incomplete",
        "unknown_unobtainable",
    ) and not any("allergies" in s.missing_fields for s in baseline_skips):
        baseline_skips.append(
            SkippedCheck(
                rule_id="INTAKE_ALLERGY_HISTORY",
                rule_type="history_verification",
                reason=(
                    "Allergy history status is "
                    f"'{normalized_patient.allergy_history_status}' (fail closed)"
                ),
                missing_fields=["allergies"],
                provenance=_UNAVAILABLE_SCORE_PROVENANCE,
            )
        )

    if (
        normalized_patient.sex in ("female", "other", "unknown")
        and normalized_patient.pregnancy == "unknown"
        and not any("pregnancy" in s.missing_fields for s in baseline_skips)
    ):
        baseline_skips.append(
            SkippedCheck(
                rule_id="INTAKE_PREGNANCY_STATUS",
                rule_type="population_verification",
                reason=(
                    "Patient pregnancy status is unknown for "
                    f"{normalized_patient.sex} patient (fail closed)"
                ),
                missing_fields=["pregnancy"],
                provenance=_UNAVAILABLE_SCORE_PROVENANCE,
            )
        )

    if (
        normalized_patient.weight_kg.source == "unknown"
        or normalized_patient.weight_kg.value is None
    ) and not any("weight_kg" in s.missing_fields for s in baseline_skips):
        baseline_skips.append(
            SkippedCheck(
                rule_id="INTAKE_PATIENT_WEIGHT",
                rule_type="vitals_verification",
                reason="Patient weight is unknown or unmeasured (fail closed)",
                missing_fields=["weight_kg"],
                provenance=_UNAVAILABLE_SCORE_PROVENANCE,
            )
        )

    for allergy in normalized_patient.allergies:
        sub_name = allergy.normalized_allergen_id or allergy.raw_substance
        if allergy.reaction_type == "unknown" and not any(
            "reaction_type" in s.missing_fields and sub_name.lower() in s.reason.lower()
            for s in baseline_skips
        ):
            baseline_skips.append(
                SkippedCheck(
                    rule_id=f"INTAKE_ALLERGY_REACTION_{sub_name.upper()}",
                    rule_type="allergy_crossreactivity",
                    reason=(f"Allergy reaction type for '{sub_name}' is unknown (fail closed)"),
                    missing_fields=["reaction_type"],
                    provenance=_UNAVAILABLE_SCORE_PROVENANCE,
                )
            )

    for med in normalized_patient.medications:
        if not med.resolved and not any(
            "medications_resolved" in s.missing_fields and med.raw_text in s.reason
            for s in baseline_skips
        ):
            baseline_skips.append(
                SkippedCheck(
                    rule_id=f"UNRESOLVED_MEDICATION_{med.raw_text.upper()}",
                    rule_type="entity_resolution",
                    reason=(
                        f"Medication '{med.raw_text}' could not be resolved to formulary/classes"
                    ),
                    missing_fields=["medications_resolved"],
                    provenance=_UNAVAILABLE_SCORE_PROVENANCE,
                )
            )

    for allergy in normalized_patient.allergies:
        if not allergy.resolved and not any(
            "allergies_resolved" in s.missing_fields and allergy.raw_substance in s.reason
            for s in baseline_skips
        ):
            baseline_skips.append(
                SkippedCheck(
                    rule_id=f"UNRESOLVED_ALLERGEN_{allergy.raw_substance.upper()}",
                    rule_type="entity_resolution",
                    reason=(
                        f"Allergen substance '{allergy.raw_substance}' could not be "
                        "resolved to ontology classes"
                    ),
                    missing_fields=["allergies_resolved"],
                    provenance=_UNAVAILABLE_SCORE_PROVENANCE,
                )
            )

    # Known coverage gaps: renal and hepatic impairment (Rule R2, Section 5)
    if normalized_patient.renal_impairment == "yes" and not any(
        "renal" in s.rule_id.lower() for s in baseline_skips
    ):
        baseline_skips.append(
            SkippedCheck(
                rule_id="COVERAGE_GAP_RENAL_IMPAIRMENT",
                rule_type="coverage_gap",
                reason=(
                    "Patient has documented renal impairment; ruleset has no renal "
                    "dose titration adjustment rules (Rule R2)"
                ),
                missing_fields=["renal_rules"],
                provenance=_UNAVAILABLE_SCORE_PROVENANCE,
            )
        )

    if normalized_patient.hepatic_impairment == "yes" and not any(
        "hepatic" in s.rule_id.lower() for s in baseline_skips
    ):
        baseline_skips.append(
            SkippedCheck(
                rule_id="COVERAGE_GAP_HEPATIC_IMPAIRMENT",
                rule_type="coverage_gap",
                reason=(
                    "Patient has documented hepatic impairment; ruleset has no hepatic "
                    "contraindication rules (Rule R2)"
                ),
                missing_fields=["hepatic_rules"],
                provenance=_UNAVAILABLE_SCORE_PROVENANCE,
            )
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
            abstain_code=AbstainCode.INDEX_UNAVAILABLE,
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
                abstain_code=AbstainCode.INDEX_UNAVAILABLE,
                reason=f"Retrieval error: {e}",
            )
    prov_meta.retrieval_backend = retrieval_report.backend

    # 5. LLM Plan Drafting (guarded with fallback)
    llm_fallback_mode = False
    plan_draft: PlanDraft | None = None

    if llm is None or retrieval_report.abstained or not retrieval_report.chunks:
        llm_fallback_mode = True
    else:
        include_complaint = cfg.include_complaint_in_llm
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

    # 6. Machine Verification & Pass 2 (guarded with repair loop, Rules R1, R7)
    verified_steps: list[VerifiedStep] = []
    plan_alerts: list[Any] = []
    plan_skips: list[SkippedCheck] = []
    dose_reports: list[CalculatedDoseReport] = []

    if plan_draft and not llm_fallback_mode:
        v_steps, p_alerts, p_skips, d_reports = verify_plan(
            patient=normalized_patient,
            draft=plan_draft,
            baseline_alerts=baseline_alerts,
            retrieved_chunks=retrieval_report.chunks,
            registry=registry,
            retrieval_abstain_code=retrieval_report.abstain_code,
        )
        verified_steps = v_steps
        plan_alerts = p_alerts
        plan_skips = list(p_skips)
        dose_reports = d_reports

        # Repair loop: If repairable violations exist and LLM is active
        # Feeds back strictly structured violation codes (never echoes untrusted patient complaint)
        repair_attempts = 0
        while repair_attempts < cfg.max_repair_cycles:
            raw_violations: list[str] = []
            for s in verified_steps:
                if s.status not in (
                    StepStatus.APPROVED,
                    StepStatus.REQUIRES_CLINICIAN_CONFIRMATION,
                ):
                    raw_violations.extend(s.rejection_reasons)

            if not raw_violations or llm is None:
                break

            structured_violations = sanitize_repair_violations(raw_violations)
            if not structured_violations:
                break

            repair_attempts += 1
            prov_meta.repair_attempted = True
            prov_meta.repair_cycles = repair_attempts
            try:
                assert plan_context is not None
                repaired_draft = attempt_plan_repair(
                    llm=llm,
                    context=plan_context,
                    draft=plan_draft,
                    violations=structured_violations,
                )
                v_steps, p_alerts, p_skips, d_reports = verify_plan(
                    patient=normalized_patient,
                    draft=repaired_draft,
                    baseline_alerts=baseline_alerts,
                    retrieved_chunks=retrieval_report.chunks,
                    registry=registry,
                    retrieval_abstain_code=retrieval_report.abstain_code,
                )
                verified_steps = v_steps
                plan_alerts = p_alerts
                plan_skips = list(p_skips)
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
                    rule = registry.get_rule(override.rule_id)
                    is_block_override = (
                        v_step.status == StepStatus.BLOCKED_STRUCK_THROUGH
                        or (rule is not None and rule.severity == Severity.BLOCK)
                        or any(
                            a.severity == Severity.BLOCK
                            for a in (baseline_alerts + plan_alerts)
                            if (
                                a.rule_id == override.rule_id
                                or a.rule_id in v_step.triggered_rule_ids
                            )
                        )
                    )
                    if is_block_override:
                        msg = (
                            f"Rule R11 Violation: Step {override.step_number} is "
                            f"contraindicated by a BLOCK rule ({override.rule_id}) and "
                            f"cannot be overridden by {override.clinician_id}"
                        )
                        raise PermissionError(msg)
                    if v_step.status in (
                        StepStatus.FLAGGED_HIGH,
                        StepStatus.REQUIRES_CLINICIAN_CONFIRMATION,
                    ):
                        # HIGH override is permitted when logged
                        # FG-03 / HD-4: Inferred syndrome can never reach APPROVED
                        new_status = (
                            StepStatus.REQUIRES_CLINICIAN_CONFIRMATION
                            if retrieval_report.abstain_code == AbstainCode.SYNDROME_INFERRED
                            else StepStatus.APPROVED
                        )
                        verified_steps[i] = VerifiedStep(
                            draft=v_step.draft,
                            status=new_status,
                            triggered_rule_ids=v_step.triggered_rule_ids,
                            rejection_reasons=[
                                f"OVERRIDDEN by {override.clinician_id}: {override.reason}"
                            ],
                            citation_verified=v_step.citation_verified,
                            citation_overlap_score=v_step.citation_overlap_score,
                            support_reason=v_step.support_reason,
                        )

    # 8. Verdict Lattice Resolution (Section 4)
    all_alerts = baseline_alerts + plan_alerts
    all_skips = baseline_skips + plan_skips
    has_block = any(a.severity == Severity.BLOCK for a in all_alerts) or any(
        s.status == StepStatus.BLOCKED_STRUCK_THROUGH for s in verified_steps
    )
    unresolved_entities = [m.raw_text for m in normalized_patient.medications if not m.resolved] + [
        a.raw_substance for a in normalized_patient.allergies if not a.resolved
    ]
    has_unverified_steps = any(
        s.status in (StepStatus.UNVERIFIED_MISSING_DATA, StepStatus.CITATION_UNVERIFIED)
        for s in verified_steps
    )
    has_skip_or_unresolved = (
        len(all_skips) > 0 or len(unresolved_entities) > 0 or has_unverified_steps
    )
    has_alert = len(all_alerts) > 0

    overall_verdict = resolve_verdict(
        has_block=has_block,
        has_skip_or_unresolved=has_skip_or_unresolved,
        has_alert=has_alert,
        has_unverified_steps=has_unverified_steps,
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
        checks_skipped=all_skips,
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
    audit_log_path = cfg.audit_log_path
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
            formulary_version=registry.formulary_version,
            retrieved_chunk_ids=chunk_ids,
            provider_name=prov_name,
            model_name=str(mod_name),
            verdict=str(overall_verdict),
            alert_ids=[a.rule_id for a in all_alerts],
            skipped_rule_ids=[s.rule_id for s in baseline_skips],
            override_records=overrides_dicts,
            timestamp_iso=active_clock.now().isoformat(),
            retrieval_query=retrieval_report.query,
            retrieval_filters=dict(retrieval_report.filters),
            retrieval_stage_scores=dict(retrieval_report.stage_scores),
            corpus_hash=retrieval_report.corpus_hash,
            index_version=retrieval_report.index_version,
            config_hash=retrieval_report.config_hash,
            abstain_code=retrieval_report.abstain_code.value,
        )

    return TriageResponse(
        engine=engine_report,
        verified_steps=verified_steps,
        retrieval=retrieval_report,
        overrides=overrides_list,
        llm_fallback_mode=llm_fallback_mode,
        audit_hash=audit_hash,
        provider_info=prov_meta,
    )
