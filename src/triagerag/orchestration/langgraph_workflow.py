"""LangGraph Deterministic Workflow Orchestrator for TriageRAG (ADR 0017).

Safety Properties (Rule R1, Rule R2, Rule R7, Rule R11, Rule R12):
1. Pure deterministic workflow orchestration using LangGraph StateGraph.
2. Code decides; the LLM interface explains. No external or stochastic model calls.
3. Explicit conditional routing:
   - route_after_retrieve -> draft_plan vs abstain_fallback (Rule R2 fail-closed)
   - route_after_verify -> block_seal (Rule R11) vs unverified_seal vs verified_seal
4. Non-sensitive execution tracing (node order, status, duration, route chosen; zero PII).
5. State isolation: Each workflow invocation runs on an isolated instance state.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from triagerag.contracts.enums import Severity, Verdict
from triagerag.contracts.schemas import (
    Alert,
    CalculatedDoseReport,
    Clock,
    EngineReport,
    OrchestratorConfig,
    OverrideRecord,
    Patient,
    PlanContext,
    PlanDraft,
    ProviderMetadata,
    RetrievalReport,
    ScoreResult,
    SkippedCheck,
    SystemClock,
    TriageExplanation,
    TriageResponse,
    VerifiedStep,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.provider import LLMProvider
from triagerag.orchestration.events import get_current_event_sink
from triagerag.orchestration.telemetry import (
    TelemetryManager,
    sanitize_span_attributes,
    trace_node,
)
from triagerag.orchestrator import (
    _resolve_run_context,
    stage_audit,
    stage_draft,
    stage_explain,
    stage_intake_checks,
    stage_normalise,
    stage_retrieve,
    stage_verify,
)
from triagerag.rag.index import Retriever

logger = logging.getLogger(__name__)


class TriageGraphState(TypedDict, total=False):
    """Strongly-typed graph state for TriageRAG LangGraph workflow."""

    # 1. Inputs & Configuration
    patient: Patient
    registry: ClinicalRegistry
    llm: LLMProvider | None
    index: Retriever | None
    overrides: list[OverrideRecord]
    config: OrchestratorConfig
    clock: Clock
    provider_info: ProviderMetadata

    # 2. Stage 1 Outputs (Normalisation & Physiological Scoring)
    normalized_patient: Patient
    score_result: ScoreResult
    pop_str: str

    # 3. Stage 2 Outputs (Pass 1 Deterministic Intake & Safety Interlocks)
    baseline_alerts: list[Alert]
    baseline_skips: list[SkippedCheck]
    checks_run: int
    unverified_rules: int
    blocked_drug_ids: set[str]
    allowed_drug_ids: list[str]
    has_block_alert: bool
    is_unverified: bool

    # 4. Stage 3 Outputs (Protocol Retrieval)
    retrieval_report: RetrievalReport

    # 5. Stage 4 Outputs (Extractive Plan Drafting)
    plan_draft: PlanDraft | None
    plan_context: PlanContext | None
    llm_fallback_mode: bool

    # 6. Stage 5 Outputs (Pass 2 Machine Verification & Verdict Lattice)
    verified_steps: list[VerifiedStep]
    plan_alerts: list[Alert]
    plan_skips: list[SkippedCheck]
    dose_reports: list[CalculatedDoseReport]
    overall_verdict: Verdict
    unverified_reason: str | None
    ruleset_review_state: Literal["UNREVIEWED_DRAFT", "PARTIALLY_REVIEWED", "FULLY_REVIEWED"]

    # 7. Stage 6 Outputs (Cryptographic Audit Logging)
    patient_hash: str
    audit_hash: str

    # 8. Stage 7 Outputs (EngineReport & Explanation)
    engine_report: EngineReport
    explanation: TriageExplanation
    final_response: TriageResponse

    # 9. Non-sensitive Execution Observability
    execution_trace: list[dict[str, Any]]
    error: str | None


# -----------------------------------------------------------------------------
# GRAPH NODE DEFINITIONS
# -----------------------------------------------------------------------------


def normalise_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 1: Normalise patient data and calculate early warning score."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started(
            "normalise", "Normalising patient observations and calculating early warning score"
        )
    try:
        with trace_node("normalise"):
            start_time = time.perf_counter()
            stg1 = stage_normalise(patient=state["patient"], registry=state["registry"])
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            trace_entry = {
                "node": "normalise",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "population_category": stg1.pop_str,
                    "score_band": str(stg1.score_result.band),
                    "ews_score": stg1.score_result.total_score,
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "normalise",
                    f"Normalised patient data (population: {stg1.pop_str}); score band {stg1.score_result.band}",
                    {
                        "population_category": stg1.pop_str,
                        "score_band": str(stg1.score_result.band),
                        "ews_score": stg1.score_result.total_score,
                    },
                )

            return {
                "normalized_patient": stg1.normalized_patient,
                "score_result": stg1.score_result,
                "pop_str": stg1.pop_str,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("normalise", "Normalisation failed")
        raise


def intake_safety_checks_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 2: Pass 1 deterministic intake, allergy, DDI, and formulary filters."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started(
            "intake_safety_checks",
            "Evaluating baseline clinical safety interlocks (Allergy, DDI, Formulary)",
        )
    try:
        with trace_node("intake_safety_checks"):
            start_time = time.perf_counter()
            stg2 = stage_intake_checks(
                normalized_patient=state["normalized_patient"],
                registry=state["registry"],
                score_result=state["score_result"],
                pop_str=state["pop_str"],
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            has_block = any(a.severity == Severity.BLOCK for a in stg2.baseline_alerts)
            is_unverified = any(
                s.rule_type in ("history_verification", "vitals_verification")
                for s in stg2.baseline_skips
            )

            trace_entry = {
                "node": "intake_safety_checks",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "checks_run": stg2.checks_run,
                    "baseline_alerts_count": len(stg2.baseline_alerts),
                    "baseline_skips_count": len(stg2.baseline_skips),
                    "has_block_alert": has_block,
                    "blocked_drugs_count": len(stg2.blocked_drug_ids),
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "intake_safety_checks",
                    f"Evaluated {stg2.checks_run} safety checks: {len(stg2.baseline_alerts)} alerts, {len(stg2.baseline_skips)} skips",
                    {
                        "checks_run": stg2.checks_run,
                        "baseline_alerts_count": len(stg2.baseline_alerts),
                        "baseline_skips_count": len(stg2.baseline_skips),
                        "has_block_alert": has_block,
                        "blocked_drugs_count": len(stg2.blocked_drug_ids),
                    },
                )

            return {
                "baseline_alerts": stg2.baseline_alerts,
                "baseline_skips": stg2.baseline_skips,
                "checks_run": stg2.checks_run,
                "unverified_rules": stg2.unverified_rules,
                "blocked_drug_ids": stg2.blocked_drug_ids,
                "allowed_drug_ids": stg2.allowed_drug_ids,
                "has_block_alert": has_block,
                "is_unverified": is_unverified,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("intake_safety_checks", "Baseline safety checks failed")
        raise


def retrieve_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 3: Protocol chunk retrieval and calibrated abstention evaluation."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started("retrieve", "Retrieving clinical protocol evidence chunks")
    try:
        with trace_node("retrieve"):
            start_time = time.perf_counter()
            stg3 = stage_retrieve(
                normalized_patient=state["normalized_patient"],
                index=state.get("index"),
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            prov_meta = state.get(
                "provider_info",
                ProviderMetadata(
                    generation_mode="deterministic_mock",
                    retrieval_backend=stg3.retrieval_report.backend,
                ),
            )
            prov_meta.retrieval_backend = stg3.retrieval_report.backend

            trace_entry = {
                "node": "retrieve",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "retrieval_backend": stg3.retrieval_report.backend,
                    "chunks_retrieved": len(stg3.retrieval_report.chunks),
                    "abstained": stg3.retrieval_report.abstained,
                    "abstain_code": str(stg3.retrieval_report.abstain_code)
                    if stg3.retrieval_report.abstained
                    else None,
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "retrieve",
                    f"Retrieved {len(stg3.retrieval_report.chunks)} protocol chunks via backend '{stg3.retrieval_report.backend}'",
                    {
                        "retrieval_backend": stg3.retrieval_report.backend,
                        "chunks_retrieved": len(stg3.retrieval_report.chunks),
                        "abstained": stg3.retrieval_report.abstained,
                    },
                )

            return {
                "retrieval_report": stg3.retrieval_report,
                "provider_info": prov_meta,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("retrieve", "Protocol retrieval failed")
        raise


def route_after_retrieve(state: TriageGraphState) -> str:
    """Conditional Edge 1: Route to plan drafting or fail-closed abstention (Rule R2)."""
    sink = get_current_event_sink()
    tracer = TelemetryManager.get_instance().get_tracer()
    if tracer:
        with contextlib.suppress(Exception):
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.is_recording():
                span.add_event(
                    "routing.evaluated",
                    sanitize_span_attributes({"triagerag.routing.edge": "route_after_retrieve"}),
                )

    retrieval_report = state.get("retrieval_report")
    if retrieval_report is None or retrieval_report.abstained or not retrieval_report.chunks:
        if sink:
            sink.emit_skipped(
                "draft_plan",
                "Skipping plan drafting: retrieval abstained or empty (Rule R2 fail-closed)",
            )
        return "abstain_fallback"

    if sink:
        sink.emit_skipped(
            "abstain_fallback",
            "Protocol chunks retrieved; proceeding to plan drafting",
        )
    return "draft_plan"


def draft_plan_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 4a: Normal extractive plan drafting using configured LLMProvider."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started("draft_plan", "Drafting clinical protocol action plan")
    try:
        with trace_node("draft_plan"):
            start_time = time.perf_counter()
            stg4 = stage_draft(
                normalized_patient=state["normalized_patient"],
                allowed_drug_ids=state["allowed_drug_ids"],
                baseline_alerts=state["baseline_alerts"],
                retrieval_report=state["retrieval_report"],
                llm=state.get("llm"),
                config=state["config"],
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            draft_count = len(stg4.plan_draft.steps) if stg4.plan_draft else 0

            trace_entry = {
                "node": "draft_plan",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "llm_fallback_mode": stg4.llm_fallback_mode,
                    "drafted_steps_count": draft_count,
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "draft_plan",
                    f"Drafted {draft_count} protocol steps (fallback_mode={stg4.llm_fallback_mode})",
                    {
                        "llm_fallback_mode": stg4.llm_fallback_mode,
                        "drafted_steps_count": draft_count,
                    },
                )

            return {
                "plan_draft": stg4.plan_draft,
                "plan_context": stg4.plan_context,
                "llm_fallback_mode": stg4.llm_fallback_mode,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("draft_plan", "Plan drafting failed")
        raise


def abstain_fallback_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 4b: Fail-closed abstention path (skips plan generation safely under Rule R2)."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started("abstain_fallback", "Executing fail-closed safety fallback (Rule R2)")
    try:
        with trace_node("abstain_fallback"):
            start_time = time.perf_counter()
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            report = state.get("retrieval_report")
            reason = str(report.reason or report.abstain_code) if report else "unknown"

            trace_entry = {
                "node": "abstain_fallback",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "route_action": "skip_llm_drafting",
                    "abstain_reason": reason,
                    "llm_fallback_mode": True,
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "abstain_fallback",
                    "Plan drafting safely abstained (Rule R2 fail-closed fallback active)",
                    {"llm_fallback_mode": True},
                )

            return {
                "plan_draft": None,
                "plan_context": None,
                "llm_fallback_mode": True,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("abstain_fallback", "Abstain fallback failed")
        raise


def verify_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 5: Pass 2 machine verification, repair loop, overrides, and verdict lattice."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started(
            "verify",
            "Verifying plan steps against deterministic rules and dosage limits",
        )
    try:
        with trace_node("verify"):
            start_time = time.perf_counter()
            stg5 = stage_verify(
                normalized_patient=state["normalized_patient"],
                plan_draft=state.get("plan_draft"),
                plan_context=state.get("plan_context"),
                llm_fallback_mode=state.get("llm_fallback_mode", False),
                baseline_alerts=state["baseline_alerts"],
                baseline_skips=state["baseline_skips"],
                unverified_rules=state["unverified_rules"],
                retrieval_report=state["retrieval_report"],
                registry=state["registry"],
                llm=state.get("llm"),
                overrides_list=state.get("overrides", []),
                config=state["config"],
                prov_meta=state["provider_info"],
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            trace_entry = {
                "node": "verify",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "overall_verdict": str(stg5.overall_verdict),
                    "unverified_reason": stg5.unverified_reason,
                    "verified_steps_count": len(stg5.verified_steps),
                    "plan_alerts_count": len(stg5.plan_alerts),
                    "dose_reports_count": len(stg5.dose_reports),
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "verify",
                    f"Machine verification complete: verdict {stg5.overall_verdict} ({len(stg5.verified_steps)} steps verified, {len(stg5.plan_alerts)} plan alerts)",
                    {
                        "overall_verdict": str(stg5.overall_verdict),
                        "verified_steps_count": len(stg5.verified_steps),
                        "plan_alerts_count": len(stg5.plan_alerts),
                        "dose_reports_count": len(stg5.dose_reports),
                    },
                )

            return {
                "verified_steps": stg5.verified_steps,
                "plan_alerts": stg5.plan_alerts,
                "plan_skips": stg5.plan_skips,
                "dose_reports": stg5.dose_reports,
                "overall_verdict": stg5.overall_verdict,
                "unverified_reason": stg5.unverified_reason,
                "ruleset_review_state": stg5.ruleset_review_state,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("verify", "Verification failed")
        raise


def route_after_verify(state: TriageGraphState) -> str:
    """Conditional Edge 2: Deterministic routing based on verdict lattice resolution (Rule R2 fail-closed)."""
    sink = get_current_event_sink()
    tracer = TelemetryManager.get_instance().get_tracer()
    if tracer:
        with contextlib.suppress(Exception):
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.is_recording():
                span.add_event(
                    "routing.evaluated",
                    sanitize_span_attributes({"triagerag.routing.edge": "route_after_verify"}),
                )

    verdict = state.get("overall_verdict")
    if verdict == Verdict.BLOCKED:
        if sink:
            sink.emit_skipped(
                "unverified_seal", "Overall verdict is BLOCKED; skipping UNVERIFIED seal"
            )
            sink.emit_skipped("verified_seal", "Overall verdict is BLOCKED; skipping VERIFIED seal")
        return "block_seal"
    if verdict in (Verdict.CHECKED_CLEAR, Verdict.CHECKED_ALERTS):
        if sink:
            sink.emit_skipped("block_seal", "Overall verdict is clear/alerts; skipping BLOCK seal")
            sink.emit_skipped(
                "unverified_seal", "Overall verdict is clear/alerts; skipping UNVERIFIED seal"
            )
        return "verified_seal"
    # Rule R2 Fail-Closed: any unknown, None, or unverified disposition routes to unverified_seal
    if sink:
        sink.emit_skipped("block_seal", "Fail-closed; skipping BLOCK seal")
        sink.emit_skipped("verified_seal", "Fail-closed; skipping VERIFIED seal")
    return "unverified_seal"


def block_seal_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 6a: Dedicated non-overridable BLOCK path seal (Rule R11)."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started("block_seal", "Sealing plan under Rule R11 non-overridable BLOCK status")
    try:
        with trace_node("block_seal"):
            start_time = time.perf_counter()
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            trace_entry = {
                "node": "block_seal",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "rule": "Rule R11: Inviolable BLOCK Interlock",
                    "non_overridable": True,
                    "verdict": "BLOCKED",
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "block_seal",
                    "Disposition sealed: non-overridable BLOCK safety boundary applied (Rule R11)",
                    {"overall_verdict": "BLOCKED"},
                )

            return {
                "overall_verdict": Verdict.BLOCKED,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("block_seal", "Block seal failed")
        raise


def unverified_seal_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 6b: Dedicated fail-closed UNVERIFIED path seal (Rule R2)."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started(
            "unverified_seal", "Sealing plan under Rule R2 fail-closed UNVERIFIED status"
        )
    try:
        with trace_node("unverified_seal"):
            start_time = time.perf_counter()
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            reason = state.get("unverified_reason") or "Fail-closed safety boundary"

            trace_entry = {
                "node": "unverified_seal",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "rule": "Rule R2: Fail-Closed Boundary",
                    "verdict": "UNVERIFIED",
                    "reason": reason,
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "unverified_seal",
                    "Disposition sealed: fail-closed UNVERIFIED boundary applied (Rule R2)",
                    {"overall_verdict": "UNVERIFIED"},
                )

            return {
                "overall_verdict": Verdict.UNVERIFIED,
                "unverified_reason": reason,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("unverified_seal", "Unverified seal failed")
        raise


def verified_seal_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 6c: Dedicated verified authorization seal (CHECKED_CLEAR / CHECKED_ALERTS)."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started(
            "verified_seal", "Sealing plan under verified clinical authorization status"
        )
    try:
        with trace_node("verified_seal"):
            start_time = time.perf_counter()
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            current_verdict = state.get("overall_verdict")
            # Rule R2 Fail-Closed: only valid authorized dispositions are permitted to remain verified
            unverified_reason: str | None
            if current_verdict not in (Verdict.CHECKED_CLEAR, Verdict.CHECKED_ALERTS):
                effective_verdict = Verdict.UNVERIFIED
                unverified_reason = "Unauthorized entry into verified seal path (fail-closed)"
            else:
                effective_verdict = current_verdict
                unverified_reason = state.get("unverified_reason")

            trace_entry = {
                "node": "verified_seal",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "verdict": str(effective_verdict),
                    "approved_steps_count": sum(
                        1 for s in state.get("verified_steps", []) if str(s.status) == "APPROVED"
                    ),
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "verified_seal",
                    f"Disposition sealed: authorized with verdict {effective_verdict}",
                    {"overall_verdict": str(effective_verdict)},
                )

            return {
                "overall_verdict": effective_verdict,
                "unverified_reason": unverified_reason,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("verified_seal", "Verified seal failed")
        raise


def audit_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 7: Cryptographic tamper-evident SHA-256 hash-chain logging."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started("audit", "Appending cryptographic SHA-256 audit log entry")
    try:
        with trace_node("audit"):
            start_time = time.perf_counter()
            all_alerts = state["baseline_alerts"] + state.get("plan_alerts", [])
            stg6 = stage_audit(
                normalized_patient=state["normalized_patient"],
                overall_verdict=state["overall_verdict"],
                all_alerts=all_alerts,
                baseline_skips=state["baseline_skips"],
                overrides_list=state.get("overrides", []),
                retrieval_report=state["retrieval_report"],
                registry=state["registry"],
                llm=state.get("llm"),
                clock=state.get("clock", SystemClock()),
                config=state["config"],
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            trace_entry = {
                "node": "audit",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "patient_hash_prefix": stg6.patient_hash[:8] if stg6.patient_hash else "",
                    "audit_hash_prefix": stg6.audit_hash[:8] if stg6.audit_hash else "",
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "audit",
                    "Cryptographic audit log sealed with SHA-256 hash-chain",
                    {
                        "patient_hash_prefix": stg6.patient_hash[:8] if stg6.patient_hash else "",
                        "audit_hash_prefix": stg6.audit_hash[:8] if stg6.audit_hash else "",
                    },
                )

            return {
                "patient_hash": stg6.patient_hash,
                "audit_hash": stg6.audit_hash,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("audit", "Audit hashing failed")
        raise


def explain_node(state: TriageGraphState) -> dict[str, Any]:
    """Graph Node 8: Compile final EngineReport, explanation, and TriageResponse."""
    sink = get_current_event_sink()
    if sink:
        sink.emit_started("explain", "Compiling final EngineReport and clinician explanation")
    try:
        with trace_node("explain"):
            start_time = time.perf_counter()
            stg7 = stage_explain(
                normalized_patient=state["normalized_patient"],
                overall_verdict=state["overall_verdict"],
                unverified_reason=state.get("unverified_reason"),
                score_result=state["score_result"],
                baseline_alerts=state["baseline_alerts"],
                plan_alerts=state.get("plan_alerts", []),
                baseline_skips=state["baseline_skips"],
                plan_skips=state.get("plan_skips", []),
                dose_reports=state.get("dose_reports", []),
                checks_run=state["checks_run"],
                unverified_rules=state["unverified_rules"],
                ruleset_review_state=state["ruleset_review_state"],
                retrieval_report=state["retrieval_report"],
                verified_steps=state.get("verified_steps", []),
                registry=state["registry"],
                provider_info=state["provider_info"],
                llm_fallback_mode=state.get("llm_fallback_mode", False),
                config=state["config"],
            )

            final_response = TriageResponse(
                engine=stg7.engine_report,
                verified_steps=state.get("verified_steps", []),
                retrieval=state["retrieval_report"],
                overrides=state.get("overrides", []),
                llm_fallback_mode=state.get("llm_fallback_mode", False),
                audit_hash=state.get("audit_hash", ""),
                provider_info=state["provider_info"],
                explanation=stg7.explanation,
                patient=state.get("normalized_patient") or state.get("patient"),
                input_patient=state.get("patient"),
            )

            from triagerag.action_plan import generate_action_plan

            action_plan = generate_action_plan(final_response)
            final_response = final_response.model_copy(
                update={
                    "action_plan": action_plan,
                    "confidence": action_plan.confidence,
                    "data_quality": action_plan.confidence.data_quality
                    if action_plan.confidence
                    else None,
                }
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

            trace_entry = {
                "node": "explain",
                "status": "completed",
                "duration_ms": duration_ms,
                "details": {
                    "verdict": str(stg7.engine_report.verdict),
                    "checks_run": stg7.engine_report.checks_run,
                },
            }
            existing_trace = list(state.get("execution_trace", []))
            existing_trace.append(trace_entry)

            if sink:
                sink.emit_completed(
                    "explain",
                    f"Compiled final EngineReport with verdict {stg7.engine_report.verdict}",
                    {
                        "verdict": str(stg7.engine_report.verdict),
                        "checks_run": stg7.engine_report.checks_run,
                    },
                )

            return {
                "engine_report": stg7.engine_report,
                "explanation": stg7.explanation,
                "final_response": final_response,
                "execution_trace": existing_trace,
            }
    except Exception:
        if sink:
            sink.emit_failed("explain", "Explain compilation failed")
        raise


# -----------------------------------------------------------------------------
# GRAPH CONSTRUCTION & COMPILATION
# -----------------------------------------------------------------------------


def build_triage_graph() -> StateGraph:
    """Build the uncompiled StateGraph representing the TriageRAG workflow."""
    builder = StateGraph(TriageGraphState)

    # 1. Register Nodes
    builder.add_node("normalise", normalise_node)
    builder.add_node("intake_safety_checks", intake_safety_checks_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("draft_plan", draft_plan_node)
    builder.add_node("abstain_fallback", abstain_fallback_node)
    builder.add_node("verify", verify_node)
    builder.add_node("block_seal", block_seal_node)
    builder.add_node("unverified_seal", unverified_seal_node)
    builder.add_node("verified_seal", verified_seal_node)
    builder.add_node("audit", audit_node)
    builder.add_node("explain", explain_node)

    # 2. Sequential Edges
    builder.add_edge(START, "normalise")
    builder.add_edge("normalise", "intake_safety_checks")
    builder.add_edge("intake_safety_checks", "retrieve")

    # 3. Conditional Edge 1: Retrieval Abstention Check
    builder.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "draft_plan": "draft_plan",
            "abstain_fallback": "abstain_fallback",
        },
    )

    # 4. Join back to Verify
    builder.add_edge("draft_plan", "verify")
    builder.add_edge("abstain_fallback", "verify")

    # 5. Conditional Edge 2: Verdict Lattice Disposition Seal
    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "block_seal": "block_seal",
            "unverified_seal": "unverified_seal",
            "verified_seal": "verified_seal",
        },
    )

    # 6. Re-converge to Audit & Explain
    builder.add_edge("block_seal", "audit")
    builder.add_edge("unverified_seal", "audit")
    builder.add_edge("verified_seal", "audit")
    builder.add_edge("audit", "explain")
    builder.add_edge("explain", END)

    return builder


_COMPILED_GRAPH_LOCK = threading.RLock()
_COMPILED_GRAPH: CompiledStateGraph | None = None


def compile_triage_graph() -> CompiledStateGraph:
    """Compile and return an executable StateGraph instance."""
    builder = build_triage_graph()
    return builder.compile()


def get_compiled_triage_graph() -> CompiledStateGraph:
    """Thread-safe singleton accessor for compiled LangGraph workflow."""
    global _COMPILED_GRAPH
    with _COMPILED_GRAPH_LOCK:
        if _COMPILED_GRAPH is None:
            _COMPILED_GRAPH = compile_triage_graph()
        return _COMPILED_GRAPH


# -----------------------------------------------------------------------------
# GRAPH RUNNER CONVENIENCE FUNCTION
# -----------------------------------------------------------------------------


def run_triage_graph(
    patient: Patient,
    *,
    registry: ClinicalRegistry,
    llm: LLMProvider | None = None,
    index: Retriever | None = None,
    overrides: list[OverrideRecord] | None = None,
    config: OrchestratorConfig | dict[str, Any] | None = None,
    clock: Clock | None = None,
    provider_info: ProviderMetadata | None = None,
) -> tuple[TriageResponse, list[dict[str, Any]]]:
    """Execute complete triage decision support via the compiled LangGraph workflow.

    Returns:
        (TriageResponse, execution_trace)
    """
    cfg, active_clock, prov_meta = _resolve_run_context(config, clock, llm, provider_info)
    overrides_list = overrides or []

    initial_state: TriageGraphState = {
        "patient": patient,
        "registry": registry,
        "llm": llm,
        "index": index,
        "overrides": overrides_list,
        "config": cfg,
        "clock": active_clock,
        "provider_info": prov_meta,
        "execution_trace": [],
    }

    graph = get_compiled_triage_graph()

    tracer = TelemetryManager.get_instance().get_tracer()
    workflow_cm = None
    active_wf_span = None

    try:
        workflow_cm = tracer.start_as_current_span(
            "langgraph.workflow.execution",
            attributes={
                "triagerag.workflow.name": "triage_state_graph",
            },
            record_exception=False,
            set_status_on_exception=False,
        )
        active_wf_span = workflow_cm.__enter__()
    except Exception:
        logger.debug("Telemetry workflow span creation failed; proceeding without workflow span.")
        workflow_cm = None
        active_wf_span = None

    try:
        invoked = graph.invoke(initial_state)
        final_state: TriageGraphState = dict(invoked) if isinstance(invoked, dict) else {}  # type: ignore[assignment]

        if "final_response" not in final_state:
            raise RuntimeError("LangGraph workflow completed without producing final_response.")

        if active_wf_span is not None:
            try:
                if hasattr(active_wf_span, "is_recording") and active_wf_span.is_recording():
                    active_wf_span.set_attribute("triagerag.workflow.status", "completed")
            except Exception:
                pass

        full_trace = final_state.get("execution_trace", [])
        final_resp = final_state["final_response"].model_copy(
            update={"execution_trace": full_trace}
        )
        return final_resp, full_trace

    except Exception as graph_err:
        if active_wf_span is not None:
            try:
                if hasattr(active_wf_span, "is_recording") and active_wf_span.is_recording():
                    active_wf_span.set_attribute("triagerag.workflow.status", "failed")
                    active_wf_span.set_attribute("error.type", "application_error")
            except Exception:
                pass

        if workflow_cm is not None:
            try:
                workflow_cm.__exit__(type(graph_err), graph_err, graph_err.__traceback__)
                workflow_cm = None
            except Exception:
                pass
        raise
    finally:
        if workflow_cm is not None:
            with contextlib.suppress(Exception):
                workflow_cm.__exit__(None, None, None)
