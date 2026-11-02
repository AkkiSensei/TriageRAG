"""Triage decision support orchestrator.

Safety Properties (Rules R1, R2, R5, R7, R11, R12):
1. Pure deterministic pipeline: validate -> normalize -> Pass 1 -> retrieve -> draft -> verify.
2. Code decides; LLM explains. Fallback mode operates safely even if LLM/retrieval fails.
3. Untrusted chief complaint is excluded from instructions/engine by default (Rule R7).
4. BLOCK alerts can never be overridden under any condition (Rule R11).
5. Appends all triage runs to cryptographic audit chain.
6. Pipeline decomposed into 7 typed stages with no function > 120 lines (T1.6 / AUB-OPS-02).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from triagerag.contracts.enums import (
    AbstainCode,
    ScoreBand,
    Severity,
    StepStatus,
    TrustMode,
    Verdict,
)
from triagerag.contracts.schemas import (
    Alert,
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
from triagerag.contracts.wording import get_verdict_entry
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.engine.scores import calculate_early_warning_score
from triagerag.engine.verdict import resolve_verdict_with_reason
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

__all__ = [
    "AuditStageResult",
    "DraftStageResult",
    "ExplainStageResult",
    "IntakeChecksStageResult",
    "NormaliseStageResult",
    "RetrieveStageResult",
    "VerifyStageResult",
    "build_triage_explanation",
    "compute_patient_hash",
    "run_triage",
    "run_triage_legacy",
    "run_triage_linear",
    "stage_audit",
    "stage_draft",
    "stage_explain",
    "stage_intake_checks",
    "stage_normalise",
    "stage_retrieve",
    "stage_verify",
]


@dataclass(frozen=True)
class NormaliseStageResult:
    """Output of stage 1: patient normalization and baseline physiological scoring."""

    normalized_patient: Patient
    score_result: ScoreResult
    pop_str: str


@dataclass(frozen=True)
class IntakeChecksStageResult:
    """Output of stage 2: Pass 1 deterministic intake and safety rules."""

    baseline_alerts: list[Alert]
    baseline_skips: list[SkippedCheck]
    checks_run: int
    unverified_rules: int
    blocked_drug_ids: set[str]
    allowed_drug_ids: list[str]


@dataclass(frozen=True)
class RetrieveStageResult:
    """Output of stage 3: protocol chunk retrieval and abstention evaluation."""

    retrieval_report: RetrievalReport


@dataclass(frozen=True)
class DraftStageResult:
    """Output of stage 4: LLM plan drafting and fallback coordination."""

    plan_draft: PlanDraft | None
    plan_context: PlanContext | None
    llm_fallback_mode: bool


@dataclass(frozen=True)
class VerifyStageResult:
    """Output of stage 5: machine verification, repair loop, overrides, and lattice."""

    verified_steps: list[VerifiedStep]
    plan_alerts: list[Alert]
    plan_skips: list[SkippedCheck]
    dose_reports: list[CalculatedDoseReport]
    overall_verdict: Verdict
    unverified_reason: str | None
    ruleset_review_state: Literal["UNREVIEWED_DRAFT", "PARTIALLY_REVIEWED", "FULLY_REVIEWED"]


@dataclass(frozen=True)
class AuditStageResult:
    """Output of stage 6: immutable cryptographic audit chain logging."""

    patient_hash: str
    audit_hash: str


@dataclass(frozen=True)
class ExplainStageResult:
    """Output of stage 7: deterministic engine report and explainability narrative."""

    engine_report: EngineReport
    explanation: TriageExplanation


def compute_patient_hash(patient: Patient) -> str:
    """Compute one-way SHA-256 hash of patient data for de-identified audit chaining."""
    patient_json = patient.model_dump_json()
    return hashlib.sha256(patient_json.encode("utf-8")).hexdigest()


def stage_normalise(patient: Patient, registry: ClinicalRegistry) -> NormaliseStageResult:
    """Stage 1: Normalize patient and calculate physiological risk score."""
    normalized_patient = normalize_patient(patient, registry.resolver)
    pop_str = str(normalized_patient.age.population_category).lower()
    score_table = registry.get_scoring_table(pop_str)

    if score_table:
        score_result = calculate_early_warning_score(normalized_patient, score_table)
    else:
        score_result = ScoreResult(
            score_name=f"EWS_{pop_str.upper()}_UNAVAILABLE",
            total_score=None,
            band=ScoreBand.UNSCORED,
            missing_vitals=["population_table"],
            provenance=_UNAVAILABLE_SCORE_PROVENANCE,
        )

    return NormaliseStageResult(
        normalized_patient=normalized_patient,
        score_result=score_result,
        pop_str=pop_str,
    )


def _collect_history_and_vitals_skips(
    normalized_patient: Patient,
    score_result: ScoreResult,
    pop_str: str,
    skips: list[SkippedCheck],
) -> list[SkippedCheck]:
    """Collect fail-closed skips for unscored vitals and incomplete intake history."""
    collected = list(skips)
    if score_result.band == ScoreBand.UNSCORED and score_result.missing_vitals:
        collected.append(
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

    if normalized_patient.medication_history_status in (
        "incomplete",
        "unknown_unobtainable",
    ) and not any("medications" in s.missing_fields for s in collected):
        collected.append(
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
    ) and not any("allergies" in s.missing_fields for s in collected):
        collected.append(
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
        and not any("pregnancy" in s.missing_fields for s in collected)
    ):
        collected.append(
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
    ) and not any("weight_kg" in s.missing_fields for s in collected):
        collected.append(
            SkippedCheck(
                rule_id="INTAKE_PATIENT_WEIGHT",
                rule_type="vitals_verification",
                reason="Patient weight is unknown or unmeasured (fail closed)",
                missing_fields=["weight_kg"],
                provenance=_UNAVAILABLE_SCORE_PROVENANCE,
            )
        )

    return collected


def _collect_entity_and_gap_skips(
    normalized_patient: Patient,
    skips: list[SkippedCheck],
) -> list[SkippedCheck]:
    """Collect fail-closed skips for unresolved entities and known coverage gaps."""
    collected = list(skips)
    for allergy in normalized_patient.allergies:
        sub_name = allergy.normalized_allergen_id or allergy.raw_substance
        if allergy.reaction_type == "unknown" and not any(
            "reaction_type" in s.missing_fields and sub_name.lower() in s.reason.lower()
            for s in collected
        ):
            collected.append(
                SkippedCheck(
                    rule_id=f"INTAKE_ALLERGY_REACTION_{sub_name.upper()}",
                    rule_type="allergy_crossreactivity",
                    reason=f"Allergy reaction type for '{sub_name}' is unknown (fail closed)",
                    missing_fields=["reaction_type"],
                    provenance=_UNAVAILABLE_SCORE_PROVENANCE,
                )
            )

    for med in normalized_patient.medications:
        if not med.resolved and not any(
            "medications_resolved" in s.missing_fields and med.raw_text in s.reason
            for s in collected
        ):
            collected.append(
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
            for s in collected
        ):
            collected.append(
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

    if normalized_patient.renal_impairment == "yes" and not any(
        "renal" in s.rule_id.lower() for s in collected
    ):
        collected.append(
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
        "hepatic" in s.rule_id.lower() for s in collected
    ):
        collected.append(
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

    return collected


def _collect_intake_skips(
    normalized_patient: Patient,
    score_result: ScoreResult,
    pop_str: str,
    baseline_skips: list[SkippedCheck],
) -> list[SkippedCheck]:
    """Collect fail-closed intake skips for unknown/unresolved fields (Rule R2)."""
    skips = _collect_history_and_vitals_skips(
        normalized_patient, score_result, pop_str, baseline_skips
    )
    return _collect_entity_and_gap_skips(normalized_patient, skips)


def stage_intake_checks(
    normalized_patient: Patient,
    registry: ClinicalRegistry,
    score_result: ScoreResult,
    pop_str: str,
) -> IntakeChecksStageResult:
    """Stage 2: Evaluate Pass 1 baseline rules, fail-closed gaps, and formulary filters."""
    base_alerts, base_skips, checks_run, unverified_rules = evaluate_baseline(
        normalized_patient, registry
    )
    all_intake_skips = _collect_intake_skips(normalized_patient, score_result, pop_str, base_skips)

    blocked_drug_ids = {
        drug_id
        for alert in base_alerts
        if alert.severity == Severity.BLOCK
        for drug_id in alert.drug_ids
    }
    allowed_drug_ids = [
        d_id for d_id in sorted(registry.formulary_drugs.keys()) if d_id not in blocked_drug_ids
    ]

    return IntakeChecksStageResult(
        baseline_alerts=base_alerts,
        baseline_skips=all_intake_skips,
        checks_run=checks_run,
        unverified_rules=unverified_rules,
        blocked_drug_ids=blocked_drug_ids,
        allowed_drug_ids=allowed_drug_ids,
    )


def stage_retrieve(
    normalized_patient: Patient,
    index: Retriever | None,
) -> RetrieveStageResult:
    """Stage 3: Guarded protocol retrieval and candidate chunk selection."""
    if index is None:
        report = RetrievalReport(
            chunks=[],
            backend="none",
            abstained=True,
            abstain_code=AbstainCode.INDEX_UNAVAILABLE,
            reason="No retrieval index configured",
        )
        return RetrieveStageResult(retrieval_report=report)

    try:
        report = retrieve_protocol_chunks(normalized_patient, index)
    except Exception as e:
        logger.error("Retrieval failed: %s", e)
        report = RetrievalReport(
            chunks=[],
            backend=index.backend,
            abstained=True,
            abstain_code=AbstainCode.INDEX_UNAVAILABLE,
            reason=f"Retrieval error: {e}",
        )

    return RetrieveStageResult(retrieval_report=report)


def stage_draft(
    normalized_patient: Patient,
    allowed_drug_ids: list[str],
    baseline_alerts: list[Alert],
    retrieval_report: RetrievalReport,
    llm: LLMProvider | None,
    config: OrchestratorConfig,
) -> DraftStageResult:
    """Stage 4: LLM plan drafting with fault-isolated fallback."""
    if llm is None or retrieval_report.abstained or not retrieval_report.chunks:
        return DraftStageResult(
            plan_draft=None,
            plan_context=None,
            llm_fallback_mode=True,
        )

    delimited_complaint = (
        normalized_patient.chief_complaint_untrusted if config.include_complaint_in_llm else None
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
        return DraftStageResult(
            plan_draft=None,
            plan_context=plan_context,
            llm_fallback_mode=True,
        )

    return DraftStageResult(
        plan_draft=draft,
        plan_context=plan_context,
        llm_fallback_mode=False,
    )


def _run_plan_repair_loop(
    verified_steps: list[VerifiedStep],
    plan_draft: PlanDraft,
    plan_context: PlanContext,
    normalized_patient: Patient,
    baseline_alerts: list[Alert],
    retrieval_report: RetrievalReport,
    registry: ClinicalRegistry,
    llm: LLMProvider,
    max_repair_cycles: int,
    prov_meta: ProviderMetadata,
) -> tuple[list[VerifiedStep], list[Alert], list[SkippedCheck], list[CalculatedDoseReport]]:
    """Execute iterative structured plan repair loop."""
    v_steps = verified_steps
    p_draft = plan_draft
    p_alerts: list[Alert] = []
    p_skips: list[SkippedCheck] = []
    d_reports: list[CalculatedDoseReport] = []

    repair_attempts = 0
    while repair_attempts < max_repair_cycles:
        raw_violations: list[str] = []
        for s in v_steps:
            if s.status not in (
                StepStatus.APPROVED,
                StepStatus.REQUIRES_CLINICIAN_CONFIRMATION,
            ):
                raw_violations.extend(s.rejection_reasons)

        if not raw_violations:
            break

        structured_violations = sanitize_repair_violations(raw_violations)
        if not structured_violations:
            break

        repair_attempts += 1
        prov_meta.repair_attempted = True
        prov_meta.repair_cycles = repair_attempts
        try:
            repaired_draft = attempt_plan_repair(
                llm=llm,
                context=plan_context,
                draft=p_draft,
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
            p_draft = repaired_draft
        except Exception as e:
            logger.warning("LLM repair attempt %d failed: %s", repair_attempts, e)
            break

    return v_steps, p_alerts, list(p_skips), d_reports


def _apply_overrides(
    verified_steps: list[VerifiedStep],
    overrides_list: list[OverrideRecord],
    all_alerts: list[Alert],
    registry: ClinicalRegistry,
    abstain_code: AbstainCode,
) -> list[VerifiedStep]:
    """Apply clinician overrides, strictly enforcing Rule R11 (BLOCK cannot be overridden)."""
    steps = list(verified_steps)
    for override in overrides_list:
        for i, v_step in enumerate(steps):
            if v_step.draft.step_number != override.step_number:
                continue

            rule = registry.get_rule(override.rule_id)
            is_block = (
                v_step.status == StepStatus.BLOCKED_STRUCK_THROUGH
                or (rule is not None and rule.severity == Severity.BLOCK)
                or any(
                    a.severity == Severity.BLOCK
                    for a in all_alerts
                    if a.rule_id == override.rule_id or a.rule_id in v_step.triggered_rule_ids
                )
            )
            if is_block:
                raise PermissionError(
                    f"Rule R11 Violation: Step {override.step_number} is contraindicated "
                    f"by a BLOCK rule ({override.rule_id}) and cannot be overridden by "
                    f"{override.clinician_id}"
                )

            if v_step.status in (
                StepStatus.FLAGGED_HIGH,
                StepStatus.REQUIRES_CLINICIAN_CONFIRMATION,
            ):
                new_status = (
                    StepStatus.REQUIRES_CLINICIAN_CONFIRMATION
                    if abstain_code == AbstainCode.SYNDROME_INFERRED
                    else StepStatus.APPROVED
                )
                steps[i] = VerifiedStep(
                    draft=v_step.draft,
                    status=new_status,
                    triggered_rule_ids=v_step.triggered_rule_ids,
                    rejection_reasons=[f"OVERRIDDEN by {override.clinician_id}: {override.reason}"],
                    citation_verified=v_step.citation_verified,
                    citation_overlap_score=v_step.citation_overlap_score,
                    support_reason=v_step.support_reason,
                )
    return steps


def stage_verify(
    normalized_patient: Patient,
    plan_draft: PlanDraft | None,
    plan_context: PlanContext | None,
    llm_fallback_mode: bool,
    baseline_alerts: list[Alert],
    baseline_skips: list[SkippedCheck],
    unverified_rules: int,
    retrieval_report: RetrievalReport,
    registry: ClinicalRegistry,
    llm: LLMProvider | None,
    overrides_list: list[OverrideRecord],
    config: OrchestratorConfig,
    prov_meta: ProviderMetadata,
) -> VerifyStageResult:
    """Stage 5: Machine verification, plan repair, override application, and verdict lattice."""
    verified_steps: list[VerifiedStep] = []
    plan_alerts: list[Alert] = []
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

        if llm is not None and plan_context is not None:
            v_steps, p_alerts, p_skips, d_reports = _run_plan_repair_loop(
                verified_steps=verified_steps,
                plan_draft=plan_draft,
                plan_context=plan_context,
                normalized_patient=normalized_patient,
                baseline_alerts=baseline_alerts,
                retrieval_report=retrieval_report,
                registry=registry,
                llm=llm,
                max_repair_cycles=config.max_repair_cycles,
                prov_meta=prov_meta,
            )
            verified_steps = v_steps
            plan_alerts = p_alerts
            plan_skips = list(p_skips)
            dose_reports = d_reports

    all_alerts = baseline_alerts + plan_alerts
    all_skips = baseline_skips + plan_skips

    if overrides_list and verified_steps:
        verified_steps = _apply_overrides(
            verified_steps=verified_steps,
            overrides_list=overrides_list,
            all_alerts=all_alerts,
            registry=registry,
            abstain_code=retrieval_report.abstain_code,
        )

    has_block = any(a.severity == Severity.BLOCK for a in all_alerts) or any(
        s.status == StepStatus.BLOCKED_STRUCK_THROUGH for s in verified_steps
    )
    unresolved_entities = [m.raw_text for m in normalized_patient.medications if not m.resolved] + [
        a.raw_substance for a in normalized_patient.allergies if not a.resolved
    ]
    has_unverified_steps = any(
        s.status
        in (
            StepStatus.UNVERIFIED_MISSING_DATA,
            StepStatus.CITATION_UNVERIFIED,
            StepStatus.NOT_APPLICABLE,
            StepStatus.REQUIRES_CLINICIAN_CONFIRMATION,
        )
        for s in verified_steps
    )
    has_skip_or_unresolved = (
        len(all_skips) > 0 or len(unresolved_entities) > 0 or has_unverified_steps
    )
    has_alert = len(all_alerts) > 0
    has_approved_steps = any(s.status == StepStatus.APPROVED for s in verified_steps)

    overall_verdict, unverified_reason = resolve_verdict_with_reason(
        has_block=has_block,
        has_skip_or_unresolved=has_skip_or_unresolved,
        has_alert=has_alert,
        has_unverified_steps=has_unverified_steps,
        retrieval_report=retrieval_report,
        has_approved_steps=has_approved_steps,
    )

    if (
        config.trust_mode == TrustMode.STRICT
        and overall_verdict == Verdict.CHECKED_CLEAR
        and unverified_rules > 0
    ):
        overall_verdict = Verdict.UNVERIFIED
        unverified_reason = (
            f"UNVERIFIED_RULESET: {unverified_rules} rules evaluated without clinical "
            "verification in strict trust mode (HD-7)"
        )

    review_state: Literal["UNREVIEWED_DRAFT", "PARTIALLY_REVIEWED", "FULLY_REVIEWED"] = (
        "FULLY_REVIEWED" if unverified_rules == 0 else "UNREVIEWED_DRAFT"
    )

    return VerifyStageResult(
        verified_steps=verified_steps,
        plan_alerts=plan_alerts,
        plan_skips=plan_skips,
        dose_reports=dose_reports,
        overall_verdict=overall_verdict,
        unverified_reason=unverified_reason,
        ruleset_review_state=review_state,
    )


def stage_audit(
    normalized_patient: Patient,
    overall_verdict: Verdict,
    all_alerts: list[Alert],
    baseline_skips: list[SkippedCheck],
    overrides_list: list[OverrideRecord],
    retrieval_report: RetrievalReport,
    registry: ClinicalRegistry,
    llm: LLMProvider | None,
    clock: Clock,
    config: OrchestratorConfig,
) -> AuditStageResult:
    """Stage 6: Append triage decision metadata to tamper-evident audit log."""
    patient_hash = compute_patient_hash(normalized_patient)
    audit_hash = "UNAUDITED"

    if config.audit_log_path:
        from triagerag.audit.chain import append_audit_entry

        path_obj = Path(config.audit_log_path)
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
            timestamp_iso=clock.now().isoformat(),
            retrieval_query=retrieval_report.query,
            retrieval_filters=dict(retrieval_report.filters),
            retrieval_stage_scores=dict(retrieval_report.stage_scores),
            corpus_hash=retrieval_report.corpus_hash,
            index_version=retrieval_report.index_version,
            config_hash=retrieval_report.config_hash,
            abstain_code=retrieval_report.abstain_code.value,
        )

    return AuditStageResult(patient_hash=patient_hash, audit_hash=audit_hash)


def _build_headline(
    verdict_str: str,
    verdict_entry: dict[str, Any],
    retrieval: RetrievalReport | None,
) -> str:
    """Derive headline strictly upholding canonical wording and non-clear invariant."""
    if verdict_str == "UNVERIFIED" and retrieval and retrieval.abstained:
        ac_val = (
            retrieval.abstain_code.value
            if hasattr(retrieval.abstain_code, "value")
            else str(retrieval.abstain_code)
        )
        headline = f"UNVERIFIED: Protocol Retrieval Abstained ({ac_val})"
    else:
        headline = str(verdict_entry.get("headline", f"Triage Result: {verdict_str}"))

    if verdict_str != "CHECKED_CLEAR":
        assert "CLEAR" not in headline, (
            f"Safety invariant violated: Non-clear verdict has CLEAR in headline: {headline}"
        )
    return headline


def _build_outcome_reasons(
    engine: EngineReport,
    verified_steps: list[VerifiedStep],
    retrieval: RetrievalReport | None,
) -> list[str]:
    """Derive structured outcome reasons for alerts, steps, and abstentions."""
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
                "rejected: Supporting evidence could not be verified in retrieved protocol text."
            )
        elif v_step.status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION:
            outcome_reasons.append(
                f"[CONFIRMATION REQUIRED] Proposed step {v_step.draft.step_number} ('{step_desc}') "
                "requires explicit confirmation as protocol was inferred from vitals (ADR-0007)."
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

    return outcome_reasons


def _build_retrieval_explanation(retrieval: RetrievalReport | None) -> str:
    """Generate truthful explanation of retrieval status and constraints."""
    if retrieval is None:
        return "Protocol retrieval was not executed for this run."

    if retrieval.abstained:
        ac_val = (
            retrieval.abstain_code.value
            if hasattr(retrieval.abstain_code, "value")
            else str(retrieval.abstain_code)
        )
        return (
            f"Retrieval abstained under safety gate '{ac_val}': {retrieval.reason}. "
            f"Query: '{retrieval.query or '(empty)'}', Filters: {retrieval.filters}."
        )

    if str(getattr(retrieval.abstain_code, "value", retrieval.abstain_code)) == "SYNDROME_INFERRED":
        return (
            f"No syndrome was explicitly specified by the clinician. Retrieval inferred candidate "
            f"protocol from abnormal vitals flags using {retrieval.backend.upper()} backend. "
            f"In accordance with ADR-0007, all passing steps require clinician confirmation."
        )

    syn = retrieval.filters.get("syndrome", "unknown") if retrieval.filters else "unknown"
    pop = retrieval.filters.get("population", "unknown") if retrieval.filters else "unknown"
    return (
        f"Successfully retrieved {len(retrieval.chunks)} protocol chunks using "
        f"{retrieval.backend.upper()} partitioned by population '{pop}' and filtered by "
        f"syndrome '{syn}'. Lexical ranking scores reflect token matching against controlled "
        f"vocabulary, not clinical confidence probabilities."
    )


def _build_completed_checks(
    engine: EngineReport,
    patient: Any,
    verified_steps: list[VerifiedStep],
) -> list[str]:
    """Derive list of completed checks truthfully from actual execution (T1.2)."""
    completed_checks: list[str] = []
    if engine.checks_run > 0:
        completed_checks.append(
            f"Evaluated {engine.checks_run} registered safety rules across formulary and ontology"
        )

    has_allergy_skip = any(
        "allergy" in s.rule_type.lower()
        or "allergy" in s.rule_id.lower()
        or "allergies" in s.missing_fields
        for s in engine.checks_skipped
    ) or getattr(patient, "allergy_history_status", None) in (
        "incomplete",
        "unknown_unobtainable",
    )
    if not has_allergy_skip:
        completed_checks.append("Allergy and cross-reactivity interlock evaluation")

    has_med_skip = any(
        "medication" in s.rule_type.lower()
        or "medication" in s.rule_id.lower()
        or "medications" in s.missing_fields
        or s.rule_type == "entity_resolution"
        for s in engine.checks_skipped
    ) or getattr(patient, "medication_history_status", None) in (
        "incomplete",
        "unknown_unobtainable",
    )
    if not has_med_skip:
        completed_checks.append(
            "Deterministic contraindication and drug-drug interaction screening"
        )

    patient_weight = getattr(patient, "weight_kg", None)
    has_weight_skip = (
        any(
            "weight" in s.rule_type.lower()
            or "weight" in s.rule_id.lower()
            or "weight_kg" in s.missing_fields
            for s in engine.checks_skipped
        )
        or patient_weight is None
        or getattr(patient_weight, "value", None) is None
    )
    if not has_weight_skip:
        completed_checks.append("Weight-based dose ceiling and magnitude tripwire checks")

    has_score_skip = any(s.rule_type == "physiological_scoring" for s in engine.checks_skipped)
    if engine.score and engine.score.total_score is not None and not has_score_skip:
        band_val = (
            engine.score.band.value
            if hasattr(engine.score.band, "value")
            else str(engine.score.band)
        )
        completed_checks.append(
            f"Calculated physiological risk score: {engine.score.score_name} = "
            f"{engine.score.total_score} (Band: {band_val})"
        )

    approved_steps = [s for s in verified_steps if s.status == StepStatus.APPROVED]
    if approved_steps:
        completed_checks.append(
            f"Machine-verified {len(approved_steps)} proposed protocol steps against "
            "retrieved evidence and formulary limits"
        )

    completed_checks.append(
        f"Trust policy: {engine.trust_mode.upper()} mode ({engine.verified_rules_summary})"
    )

    return completed_checks


def _build_unresolved_checks(
    engine: EngineReport,
    verified_steps: list[VerifiedStep],
    retrieval: RetrievalReport | None,
) -> list[str]:
    """Derive list of unresolved checks and safety gaps (T1.2)."""
    unresolved_checks: list[str] = []
    if engine.trust_mode == TrustMode.STRICT and engine.unverified_rules_evaluated > 0:
        unresolved_checks.append(
            f"Trust policy STRICT: {engine.unverified_rules_evaluated} evaluated rules remain unverified by clinical reviewer (HD-7)"
        )

    for skip in engine.checks_skipped:
        missing_str = f" (Missing: {', '.join(skip.missing_fields)})" if skip.missing_fields else ""
        unresolved_checks.append(f"Rule '{skip.rule_id}': {skip.reason}{missing_str}")

    for ent in engine.unresolved_entities:
        unresolved_checks.append(
            f"Unresolved entity: '{ent}' could not be mapped to formulary or ontology"
        )

    for gap in engine.coverage_gaps:
        unresolved_checks.append(f"Known ruleset coverage gap: {gap}")

    for v_step in verified_steps:
        if v_step.status == StepStatus.CITATION_UNVERIFIED:
            unresolved_checks.append(
                f"Proposed step {v_step.draft.step_number} citation unverified: "
                "Supporting evidence could not be verified in retrieved protocol text"
            )
        elif v_step.status == StepStatus.UNVERIFIED_MISSING_DATA:
            unresolved_checks.append(
                f"Proposed step {v_step.draft.step_number} unverified: "
                "Missing required clinical parameters to verify proposed intervention"
            )
        elif v_step.status == StepStatus.BLOCKED_STRUCK_THROUGH:
            unresolved_checks.append(
                f"Proposed step {v_step.draft.step_number} struck through: "
                f"{'; '.join(v_step.rejection_reasons)}"
            )

    if retrieval and retrieval.abstained:
        ac_val = (
            retrieval.abstain_code.value
            if hasattr(retrieval.abstain_code, "value")
            else str(retrieval.abstain_code)
        )
        unresolved_checks.append(f"Protocol retrieval abstained ({ac_val}): {retrieval.reason}")

    return unresolved_checks


def _build_rejected_paths(
    engine: EngineReport,
    retrieval: RetrievalReport | None,
) -> list[str]:
    """Explain why alternative verdict paths were rejected (Rules R1, R2, R11)."""
    verdict = engine.verdict
    rejected: list[str] = []

    if verdict == Verdict.BLOCKED:
        rejected.append(
            "Rejected CHECKED_CLEAR: Rule R11 strictly prohibits clearing a plan when a BLOCK severity alert is active."
        )
        rejected.append(
            "Rejected CHECKED_ALERTS: Absolute contraindication interlocks cannot be overridden by clinical judgment."
        )
        rejected.append(
            "Rejected UNVERIFIED: Sufficient structured clinical parameters were verified to definitively prove contraindication."
        )
    elif verdict == Verdict.UNVERIFIED:
        rejected.append(
            "Rejected CHECKED_CLEAR: Rule R2 fail-closed interlock forbids assuming safety when required clinical data is missing or unresolved."
        )
        rejected.append(
            "Rejected BLOCKED: Incomplete data prevents confirming active contraindications; missing parameters trigger fail-closed UNVERIFIED."
        )
        rejected.append(
            "Rejected CHECKED_ALERTS: Safety scope cannot be partially accepted while unverified safety interlocks remain unperformed."
        )
    elif verdict == Verdict.CHECKED_ALERTS:
        rejected.append(
            "Rejected CHECKED_CLEAR: Non-blocking clinical safety alerts (HIGH) were flagged that require explicit clinician acknowledgment."
        )
        rejected.append(
            "Rejected BLOCKED: No absolute fatal contraindication or inviolable interlock rule fired."
        )
        rejected.append(
            "Rejected UNVERIFIED: All required clinical parameters and vitals were present and evaluated without unresolved data gaps."
        )
    else:  # CHECKED_CLEAR
        rejected.append(
            "Rejected BLOCKED: Zero fatal drug-drug, allergy, or physiologic contraindication rules fired."
        )
        rejected.append(
            "Rejected CHECKED_ALERTS: Zero clinical warnings or formulary ceiling violations detected."
        )
        rejected.append(
            "Rejected UNVERIFIED: All intake histories and vitals required for active rulesets were successfully resolved."
        )

    return rejected


def _build_generation_disclosure(
    patient: Any,
    provider_info: ProviderMetadata,
    include_complaint_in_llm: bool,
) -> str:
    """Build honest generation disclosure string."""
    disclosure = (
        f"Plan generation mode: '{provider_info.generation_mode}' (Deterministic mock profile: "
        f"'{provider_info.requested_profile or 'default'}', repair cycles: "
        f"{provider_info.repair_cycles}). No external generative AI models or cloud APIs are used."
    )
    complaint_text = getattr(patient, "chief_complaint_untrusted", "") or ""
    if complaint_text:
        if include_complaint_in_llm:
            disclosure += (
                " Patient narrative was passed inside a delimited clinical context block "
                "only per explicit opt-in."
            )
        else:
            disclosure += (
                " Patient narrative was excluded from drafting context under Rule R7 isolation."
            )
    return disclosure


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
    verdict_entry = get_verdict_entry(verdict_str)

    headline = _build_headline(verdict_str, verdict_entry, retrieval)
    plain_language_summary = str(
        verdict_entry.get("summary", "Clinical safety evaluation complete.")
    )
    outcome_reasons = _build_outcome_reasons(engine, verified_steps, retrieval)
    retrieval_explanation = _build_retrieval_explanation(retrieval)

    if retrieval and retrieval.chunks:
        top_c = retrieval.chunks[0]
        excerpt = top_c.text[:140]
        ellipsis = "..." if len(top_c.text) > 140 else ""
        evidence_summary = (
            f"Top retrieved evidence: Document '{top_c.doc_id}', Section '{top_c.section}' "
            f'(Rank 1). Excerpt: "{excerpt}{ellipsis}"'
        )
    else:
        evidence_summary = "No protocol evidence chunks were retrieved or verified for this case."

    completed_checks = _build_completed_checks(engine, patient, verified_steps)
    unresolved_checks = _build_unresolved_checks(engine, verified_steps, retrieval)
    rejected_paths = _build_rejected_paths(engine, retrieval)
    generation_disclosure = _build_generation_disclosure(
        patient, provider_info, include_complaint_in_llm
    )
    raw_actions = verdict_entry.get("actions", ["Review triage verification report."])
    permitted_ui_actions = [str(act) for act in raw_actions]

    return TriageExplanation(
        headline=headline,
        plain_language_summary=plain_language_summary,
        outcome_reasons=outcome_reasons,
        retrieval_explanation=retrieval_explanation,
        evidence_summary=evidence_summary,
        completed_checks=completed_checks,
        unresolved_checks=unresolved_checks,
        rejected_paths=rejected_paths,
        generation_disclosure=generation_disclosure,
        permitted_ui_actions=permitted_ui_actions,
    )


def stage_explain(
    normalized_patient: Patient,
    overall_verdict: Verdict,
    unverified_reason: str | None,
    score_result: ScoreResult,
    baseline_alerts: list[Alert],
    plan_alerts: list[Alert],
    baseline_skips: list[SkippedCheck],
    plan_skips: list[SkippedCheck],
    dose_reports: list[CalculatedDoseReport],
    checks_run: int,
    unverified_rules: int,
    ruleset_review_state: Literal["UNREVIEWED_DRAFT", "PARTIALLY_REVIEWED", "FULLY_REVIEWED"],
    retrieval_report: RetrievalReport,
    verified_steps: list[VerifiedStep],
    registry: ClinicalRegistry,
    provider_info: ProviderMetadata,
    llm_fallback_mode: bool,
    config: OrchestratorConfig,
) -> ExplainStageResult:
    """Stage 7: Build deterministic EngineReport and comprehensive clinical explanation."""
    unresolved_entities = [m.raw_text for m in normalized_patient.medications if not m.resolved] + [
        a.raw_substance for a in normalized_patient.allergies if not a.resolved
    ]

    total_rules_count = len(registry.rules)
    verified_rules_count = sum(
        1 for r in registry.rules if getattr(r.provenance, "verified", False)
    )
    verified_rules_summary = f"verified {verified_rules_count} of {total_rules_count}"

    engine_report = EngineReport(
        verdict=overall_verdict,
        unverified_reason=unverified_reason,
        score=score_result,
        baseline_alerts=baseline_alerts,
        plan_alerts=plan_alerts,
        dose_reports=dose_reports,
        checks_run=checks_run,
        checks_skipped=baseline_skips + plan_skips,
        unresolved_entities=unresolved_entities,
        ruleset_coverage=[
            f"{checks_run} rules evaluated across {len(registry.rules)} registered rules"
        ],
        coverage_gaps=list(registry.coverage_gaps),
        unverified_rules_evaluated=unverified_rules,
        ruleset_review_state=ruleset_review_state,
        ruleset_version=registry.version,
        trust_mode=config.trust_mode,
        verified_rules_count=verified_rules_count,
        total_rules_count=total_rules_count,
        verified_rules_summary=verified_rules_summary,
    )

    explanation = build_triage_explanation(
        engine=engine_report,
        retrieval=retrieval_report,
        verified_steps=verified_steps,
        patient=normalized_patient,
        provider_info=provider_info,
        llm_fallback_mode=llm_fallback_mode,
        include_complaint_in_llm=config.include_complaint_in_llm,
    )

    return ExplainStageResult(engine_report=engine_report, explanation=explanation)


def _resolve_run_context(
    config: OrchestratorConfig | dict[str, Any] | None,
    clock: Clock | None,
    llm: LLMProvider | None,
    provider_info: ProviderMetadata | None,
) -> tuple[OrchestratorConfig, Clock, ProviderMetadata]:
    """Resolve and validate configuration, system clock, and provider metadata."""
    if config is None:
        cfg = OrchestratorConfig()
    elif isinstance(config, OrchestratorConfig):
        cfg = config
    elif isinstance(config, dict):
        cfg = OrchestratorConfig(**config)
    else:
        raise TypeError(f"Invalid config type: {type(config)}")

    active_clock: Clock = clock if clock is not None else SystemClock()
    prov_meta = (
        provider_info.model_copy()
        if provider_info is not None
        else ProviderMetadata(
            generation_mode="deterministic_mock",
            requested_profile=getattr(llm, "profile", None) if llm else None,
            retrieval_backend="bm25",
        )
    )
    return cfg, active_clock, prov_meta


def run_triage_linear(
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
    """Execute reference linear emergency triage decision support pipeline across 7 typed stages."""
    cfg, active_clock, prov_meta = _resolve_run_context(config, clock, llm, provider_info)
    overrides_list = overrides or []

    # 1. Normalise
    stg1 = stage_normalise(patient=patient, registry=registry)

    # 2. Intake checks
    stg2 = stage_intake_checks(
        normalized_patient=stg1.normalized_patient,
        registry=registry,
        score_result=stg1.score_result,
        pop_str=stg1.pop_str,
    )

    # 3. Retrieve
    stg3 = stage_retrieve(normalized_patient=stg1.normalized_patient, index=index)
    prov_meta.retrieval_backend = stg3.retrieval_report.backend

    # 4. Draft
    stg4 = stage_draft(
        normalized_patient=stg1.normalized_patient,
        allowed_drug_ids=stg2.allowed_drug_ids,
        baseline_alerts=stg2.baseline_alerts,
        retrieval_report=stg3.retrieval_report,
        llm=llm,
        config=cfg,
    )

    # 5. Verify
    stg5 = stage_verify(
        normalized_patient=stg1.normalized_patient,
        plan_draft=stg4.plan_draft,
        plan_context=stg4.plan_context,
        llm_fallback_mode=stg4.llm_fallback_mode,
        baseline_alerts=stg2.baseline_alerts,
        baseline_skips=stg2.baseline_skips,
        unverified_rules=stg2.unverified_rules,
        retrieval_report=stg3.retrieval_report,
        registry=registry,
        llm=llm,
        overrides_list=overrides_list,
        config=cfg,
        prov_meta=prov_meta,
    )

    # 6. Audit
    stg6 = stage_audit(
        normalized_patient=stg1.normalized_patient,
        overall_verdict=stg5.overall_verdict,
        all_alerts=stg2.baseline_alerts + stg5.plan_alerts,
        baseline_skips=stg2.baseline_skips,
        overrides_list=overrides_list,
        retrieval_report=stg3.retrieval_report,
        registry=registry,
        llm=llm,
        clock=active_clock,
        config=cfg,
    )

    # 7. Explain
    stg7 = stage_explain(
        normalized_patient=stg1.normalized_patient,
        overall_verdict=stg5.overall_verdict,
        unverified_reason=stg5.unverified_reason,
        score_result=stg1.score_result,
        baseline_alerts=stg2.baseline_alerts,
        plan_alerts=stg5.plan_alerts,
        baseline_skips=stg2.baseline_skips,
        plan_skips=stg5.plan_skips,
        dose_reports=stg5.dose_reports,
        checks_run=stg2.checks_run,
        unverified_rules=stg2.unverified_rules,
        ruleset_review_state=stg5.ruleset_review_state,
        retrieval_report=stg3.retrieval_report,
        verified_steps=stg5.verified_steps,
        registry=registry,
        provider_info=prov_meta,
        llm_fallback_mode=stg4.llm_fallback_mode,
        config=cfg,
    )

    linear_resp = TriageResponse(
        engine=stg7.engine_report,
        verified_steps=stg5.verified_steps,
        retrieval=stg3.retrieval_report,
        overrides=overrides_list,
        llm_fallback_mode=stg4.llm_fallback_mode,
        audit_hash=stg6.audit_hash,
        provider_info=prov_meta,
        explanation=stg7.explanation,
        patient=stg1.normalized_patient,
        input_patient=patient,
        execution_trace=[],
    )
    from triagerag.action_plan import generate_action_plan
    from triagerag.defaults import apply_demo_defaults

    _, tags = apply_demo_defaults(patient)
    plan = generate_action_plan(linear_resp, tags)
    return linear_resp.model_copy(
        update={
            "action_plan": plan,
            "confidence": plan.confidence,
            "data_quality": plan.confidence.data_quality if plan.confidence else None,
        }
    )


run_triage_legacy = run_triage_linear


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
    """Execute complete emergency triage decision support pipeline via the LangGraph StateGraph (ADR 0017).

    Integrates LangGraph as the core orchestration framework while preserving 100% mathematical
    and clinical decision equivalence with the reference pipeline.
    """
    from triagerag.orchestration.langgraph_workflow import run_triage_graph

    response, _trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=llm,
        index=index,
        overrides=overrides,
        config=config,
        clock=clock,
        provider_info=provider_info,
    )
    from triagerag.action_plan import generate_action_plan
    from triagerag.defaults import apply_demo_defaults

    _, assumption_tags = apply_demo_defaults(patient)
    action_plan = response.action_plan or generate_action_plan(
        response, assumption_tags=assumption_tags
    )
    return response.model_copy(
        update={
            "execution_trace": _trace,
            "input_patient": patient,
            "action_plan": action_plan,
            "confidence": action_plan.confidence,
            "data_quality": action_plan.confidence.data_quality if action_plan.confidence else None,
        }
    )
