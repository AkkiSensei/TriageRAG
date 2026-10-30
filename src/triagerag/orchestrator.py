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
    TriageExplanation,
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

    explanation = build_triage_explanation(
        engine=engine_report,
        retrieval=retrieval_report,
        verified_steps=verified_steps,
        patient=normalized_patient,
        provider_info=prov_meta,
        llm_fallback_mode=llm_fallback_mode,
        include_complaint_in_llm=cfg.include_complaint_in_llm,
    )

    return TriageResponse(
        engine=engine_report,
        verified_steps=verified_steps,
        retrieval=retrieval_report,
        overrides=overrides_list,
        llm_fallback_mode=llm_fallback_mode,
        audit_hash=audit_hash,
        provider_info=prov_meta,
        explanation=explanation,
    )


def build_triage_explanation(
    *,
    engine: EngineReport,
    retrieval: RetrievalReport | None,
    verified_steps: list[VerifiedStep],
    patient: Any,
    provider_info: ProviderMetadata,
    llm_fallback_mode: bool,
    include_complaint_in_llm: bool = False,
) -> TriageExplanation:
    """Construct an understandable explanation grounded in engine/retrieval output."""
    verdict_str = engine.verdict.value if hasattr(engine.verdict, "value") else str(engine.verdict)

    # 1. Headline
    headline_map = {
        "BLOCKED": "BLOCKED: Absolute Safety Interlock Triggered",
        "UNVERIFIED": "UNVERIFIED: Insufficient or Unresolved Clinical Data",
        "CHECKED_ALERTS": "CHECKED WITH ALERTS: Clinical Warnings Require Review",
        "CHECKED_CLEAR": "CHECKED CLEAR: No Configured Safety Rules Triggered",
    }
    headline = headline_map.get(verdict_str, f"Triage Result: {verdict_str}")

    # 2. Plain Language Summary
    if verdict_str == "BLOCKED":
        plain_language_summary = (
            "A deterministic clinical safety rule blocked this proposal. One or more active "
            "medications, severe contraindications, or dose tripwires prohibit requested orders. "
            "Under safety rule R11, absolute BLOCK interlocks cannot be overridden."
        )
    elif verdict_str == "UNVERIFIED":
        plain_language_summary = (
            "The system could not establish a verified clinical plan. Essential physiological "
            "parameters, medication history, or protocol evidence were missing or below retrieval "
            "thresholds. Under fail-closed safety rule R2, no unverified orders can proceed."
        )
    elif verdict_str == "CHECKED_ALERTS":
        plain_language_summary = (
            "Deterministic safety checks were completed and identified non-blocking warnings "
            "(such as duplicate therapies, moderate interactions, or elevated scores). "
            "Clinician review and logged override justifications are required before proceeding."
        )
    else:  # CHECKED_CLEAR
        plain_language_summary = (
            "All applicable deterministic rules in the active ruleset fired clear without "
            "triggering alerts. Disclaimer: This confirms compliance with configured prototype "
            "rules, not absolute clinical safety."
        )

    # 3. Outcome Reasons
    outcome_reasons: list[str] = []
    all_alerts = engine.baseline_alerts + engine.plan_alerts
    for a in all_alerts:
        sev = a.severity.value if hasattr(a.severity, "value") else str(a.severity)
        drugs_str = f" involving {', '.join(a.drug_ids)}" if a.drug_ids else ""
        outcome_reasons.append(
            f"[{sev}] Rule '{a.rule_id}'{drugs_str}: {a.action}. Consequence: {a.consequence}"
        )

    for v_step in verified_steps:
        step_desc = v_step.draft.narrative_instruction
        if len(step_desc) > 80:
            step_desc = f"{step_desc[:77]}..."
        if v_step.status == StepStatus.BLOCKED_STRUCK_THROUGH:
            outcome_reasons.append(
                f"[STRUCK THROUGH] Proposed step {v_step.draft.step_number} ('{step_desc}') was "
                f"blocked: {'; '.join(v_step.rejection_reasons)}"
            )
        elif v_step.status == StepStatus.CITATION_UNVERIFIED:
            outcome_reasons.append(
                f"[UNVERIFIED CITATION] Proposed step {v_step.draft.step_number} ('{step_desc}') "
                f"rejected: Supporting evidence could not be verified in retrieved protocol text."
            )
        elif v_step.status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION:
            outcome_reasons.append(
                f"[CONFIRMATION REQUIRED] Proposed step {v_step.draft.step_number} ('{step_desc}') "
                f"requires explicit confirmation as protocol was inferred from vitals (ADR-0007)."
            )

    if retrieval and retrieval.abstained:
        ac_val = (
            retrieval.abstain_code.value
            if hasattr(retrieval.abstain_code, "value")
            else str(retrieval.abstain_code)
        )
        outcome_reasons.append(
            f"[RETRIEVAL ABSTAINED] Protocol retrieval did not proceed: {retrieval.reason} "
            f"(Code: {ac_val})"
        )

    if not outcome_reasons:
        outcome_reasons.append("No active alerts, blocked steps, or abstentions were recorded.")

    # 4. Retrieval Explanation
    if retrieval is None:
        retrieval_explanation = "Protocol retrieval was not executed for this run."
    elif retrieval.abstained:
        ac_val = (
            retrieval.abstain_code.value
            if hasattr(retrieval.abstain_code, "value")
            else str(retrieval.abstain_code)
        )
        retrieval_explanation = (
            f"Retrieval abstained under safety gate '{ac_val}': {retrieval.reason}. "
            f"Query: '{retrieval.query or '(empty)'}', Filters: {retrieval.filters}."
        )
    elif (
        str(getattr(retrieval.abstain_code, "value", retrieval.abstain_code)) == "SYNDROME_INFERRED"
    ):
        retrieval_explanation = (
            f"No syndrome was explicitly specified by the clinician. Retrieval inferred candidate "
            f"protocol from abnormal vitals flags using {retrieval.backend.upper()} backend. "
            f"In accordance with ADR-0007, all passing steps require clinician confirmation."
        )
    else:
        syn = retrieval.filters.get("syndrome", "unknown") if retrieval.filters else "unknown"
        pop = retrieval.filters.get("population", "unknown") if retrieval.filters else "unknown"
        retrieval_explanation = (
            f"Successfully retrieved {len(retrieval.chunks)} protocol chunks using "
            f"{retrieval.backend.upper()} partitioned by population '{pop}' and filtered by "
            f"syndrome '{syn}'. Lexical ranking scores reflect token matching against controlled "
            f"vocabulary, not clinical confidence probabilities."
        )

    # 5. Evidence Summary
    if retrieval and retrieval.chunks:
        top_c = retrieval.chunks[0]
        evidence_summary = (
            f"Top retrieved evidence: Document '{top_c.doc_id}', Section '{top_c.section}' "
            f'(Rank 1). Excerpt: "{top_c.text[:140]}..."'
        )
    else:
        evidence_summary = "No protocol evidence chunks were retrieved or verified for this case."

    # 6. Completed Checks
    completed_checks: list[str] = [
        f"Evaluated {engine.checks_run} registered safety rules across formulary and ontology",
        "Deterministic contraindication and drug-drug interaction screening",
        "Allergy and cross-reactivity interlock evaluation",
        "Weight-based dose ceiling and 10x/1000x magnitude tripwire checks",
    ]
    if engine.score and engine.score.total_score is not None:
        band_val = (
            engine.score.band.value
            if hasattr(engine.score.band, "value")
            else str(engine.score.band)
        )
        completed_checks.append(
            f"Calculated physiological risk score: {engine.score.score_name} = "
            f"{engine.score.total_score} (Band: {band_val})"
        )
    if verified_steps:
        completed_checks.append(
            f"Machine-verified {len(verified_steps)} proposed protocol steps against "
            f"retrieved evidence and formulary limits"
        )

    # 7. Unresolved Checks
    unresolved_checks: list[str] = []
    for skip in engine.checks_skipped:
        missing_str = f" (Missing: {', '.join(skip.missing_fields)})" if skip.missing_fields else ""
        unresolved_checks.append(f"Rule '{skip.rule_id}': {skip.reason}{missing_str}")
    for ent in engine.unresolved_entities:
        unresolved_checks.append(
            f"Unresolved entity: '{ent}' could not be mapped to formulary or ontology"
        )
    for gap in engine.coverage_gaps:
        unresolved_checks.append(f"Known ruleset coverage gap: {gap}")

    # 8. Generation Disclosure
    generation_disclosure = (
        f"Plan generation mode: '{provider_info.generation_mode}' (Deterministic mock profile: "
        f"'{provider_info.requested_profile or 'default'}', repair cycles: "
        f"{provider_info.repair_cycles}). No external generative AI models or cloud APIs are used."
    )
    complaint_text = getattr(patient, "chief_complaint_untrusted", "") or ""
    if complaint_text:
        if include_complaint_in_llm:
            generation_disclosure += (
                " Patient narrative was passed inside a delimited clinical context block "
                "only per explicit opt-in."
            )
        else:
            generation_disclosure += (
                " Patient narrative was excluded from drafting context under Rule R7 isolation."
            )

    # 9. Permitted UI Actions
    if verdict_str == "BLOCKED":
        permitted_ui_actions = [
            "Review contraindicated medication and select alternative protocol therapy",
            "Consult senior clinical staff or full reference guideline",
            "Rule R11: Overrides are strictly prohibited for BLOCK verdicts",
        ]
    elif verdict_str == "UNVERIFIED":
        permitted_ui_actions = [
            "Provide missing patient vitals, weight, or history to enable unverified checks",
            "Explicitly select or confirm suspected clinical syndrome",
            "Re-run triage verification after data entry",
        ]
    elif verdict_str == "CHECKED_ALERTS":
        permitted_ui_actions = [
            "Review non-blocking alerts and drug interactions",
            "Enter logged clinician override with rationale if proceeding with HIGH warnings",
            "Administer verified steps with continuous monitoring",
        ]
    else:  # CHECKED_CLEAR
        permitted_ui_actions = [
            "Review verified protocol steps and order administration",
            "Confirm patient identification and presentation consistency",
            "Re-assess vitals according to protocol observation schedule",
        ]

    return TriageExplanation(
        headline=headline,
        plain_language_summary=plain_language_summary,
        outcome_reasons=outcome_reasons,
        retrieval_explanation=retrieval_explanation,
        evidence_summary=evidence_summary,
        completed_checks=completed_checks,
        unresolved_checks=unresolved_checks,
        generation_disclosure=generation_disclosure,
        permitted_ui_actions=permitted_ui_actions,
    )
