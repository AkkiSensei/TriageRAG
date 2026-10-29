"""Streamlit UI components for TriageRAG.

Safety Properties (Rules R1, R2, R3, R7, R11, R12):
1. Code decides; LLM explains (banner & reports derived strictly from EngineReport).
2. Never display the bare word 'CLEAR'.
3. 'UNSOURCED DRAFT' badges on unreviewed rules.
4. 'SYNTHETIC' badges on protocol text.
5. Untrusted chief complaint is NEVER rendered via unsafe_allow_html.
"""

from __future__ import annotations

import streamlit as st

from triagerag.contracts.enums import StepStatus, Verdict
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import EngineReport, TriageResponse, VerifiedStep

DISCLAIMER: str = (
    "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
)

__all__ = [
    "DISCLAIMER",
    "format_step_status_display",
    "format_verdict_display",
    "get_preloaded_scenario",
    "render_alerts_and_blocks",
    "render_coverage_gaps",
    "render_disclaimer_header",
    "render_llm_narrative",
    "render_top_banner",
    "render_unverified_section",
    "render_verified_plan",
]


def format_verdict_display(verdict: Verdict) -> str:
    """Format verdict string strictly upholding Section 12 wording rule.

    Never display the bare word 'CLEAR'.
    """
    if verdict == Verdict.CHECKED_CLEAR:
        return "No rules fired (within covered scope) — ruleset unreviewed"
    return verdict.value


def format_step_status_display(status: StepStatus) -> str:
    """Format step status for display."""
    if status == StepStatus.BLOCKED_STRUCK_THROUGH:
        return "[BLOCKED - STRUCK THROUGH]"
    if status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION:
        return "[REQUIRES CLINICIAN CONFIRMATION]"
    return status.value


def render_disclaimer_header() -> None:
    """Render mandatory research prototype disclaimer."""
    st.error(f"**SAFETY NOTICE**: {DISCLAIMER}")


def render_top_banner(engine: EngineReport) -> None:
    """Render fixed top banner strictly from deterministic EngineReport."""
    verdict_text = format_verdict_display(engine.verdict)

    if engine.verdict == Verdict.BLOCKED:
        st.markdown(f"## :red[Verdict: {verdict_text}]")
    elif engine.verdict in (Verdict.UNVERIFIED, Verdict.CHECKED_ALERTS):
        st.markdown(f"## :orange[Verdict: {verdict_text}]")
    else:
        st.markdown(f"## :blue[Verdict: {verdict_text}]")

    ews_score = engine.score.total_score if engine.score else "UNSCORED"
    ews_band = engine.score.band.value if engine.score else "UNSCORED"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**EWS Score:** {ews_score} ({ews_band})")
    with col2:
        st.markdown(f"**Checks Run:** {engine.checks_run}")
    with col3:
        st.markdown(f"**Checks Skipped:** {len(engine.checks_skipped)}")
    with col4:
        st.markdown(f"**Ruleset State:** *{engine.ruleset_review_state}*")


def render_alerts_and_blocks(engine: EngineReport) -> None:
    """Render clinical safety alerts and struck-through blocked drugs."""
    all_alerts = engine.baseline_alerts + engine.plan_alerts
    if not all_alerts:
        return

    st.subheader("Clinical Safety Alerts & Contraindications")
    for alert in all_alerts:
        badge = " [UNSOURCED DRAFT]" if (alert.unverified or not alert.provenance.verified) else ""
        alert_hdr = (
            f"**{alert.severity.value}**: {alert.consequence} | Rule: `{alert.rule_id}`{badge}"
        )
        if alert.severity.value == "BLOCK":
            st.error(f"{alert_hdr}\n\nAction Required: **{alert.action}**")
        elif alert.severity.value == "HIGH":
            st.warning(f"{alert_hdr}\n\nAction Required: {alert.action}")
        else:
            st.info(f"{alert_hdr}\n\nAction: {alert.action}")


def render_unverified_section(engine: EngineReport) -> None:
    """Render 'What I couldn't check' section for fail-closed transparency."""
    if not engine.checks_skipped and not engine.unresolved_entities:
        return

    st.subheader("What I Couldn't Check (Fail-Closed)")
    with st.container():
        st.write(
            f"**Checks Skipped ({len(engine.checks_skipped)}):** The following safety checks could "
            "not be completed due to missing clinical data, unknown history, or rule gaps:"
        )
        for s in engine.checks_skipped:
            missing = f" *(missing: {', '.join(s.missing_fields)})*" if s.missing_fields else ""
            st.markdown(f"- **`{s.rule_id}`** ({s.rule_type}): {s.reason}{missing}")

        if engine.unresolved_entities:
            st.write(f"**Unresolved Clinical Entities:** {', '.join(engine.unresolved_entities)}")
        st.caption(
            "Per Rule R2: Missing, unknown, or unreviewed values fail closed to UNVERIFIED. "
            "A skipped check never produces clearance."
        )


def render_coverage_gaps(engine: EngineReport) -> None:
    """Render known ruleset coverage gaps."""
    with st.expander("Known Ruleset Coverage Gaps", expanded=False):
        st.caption(
            "Rule R2: 'No rule fired' means no rule in this shipped ruleset fired, "
            "NOT that the combination is clinically safe. The following areas are out of scope:"
        )
        for gap in engine.coverage_gaps:
            st.markdown(f"- {gap}")


def render_verified_plan(verified_steps: list[VerifiedStep]) -> None:
    """Render verified protocol plan steps with citation chips."""
    st.subheader("Verified Protocol Plan Steps")
    if not verified_steps:
        st.write("No protocol steps drafted or verified.")
        return

    for step in verified_steps:
        draft = step.draft
        status = step.status

        # Format status badge
        if status == StepStatus.APPROVED:
            status_badge = "🟢 APPROVED"
        elif status == StepStatus.BLOCKED_STRUCK_THROUGH:
            status_badge = "🔴 BLOCKED (STRUCK THROUGH)"
        elif status == StepStatus.FLAGGED_HIGH:
            status_badge = "🟠 FLAGGED HIGH"
        elif status == StepStatus.FLAGGED_MODERATE:
            status_badge = "🟡 FLAGGED MODERATE"
        elif status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION:
            status_badge = "🟠 REQUIRES CLINICIAN CONFIRMATION"
        else:
            status_badge = f"⚪ {status.value}"

        step_title = (
            f"Step {draft.step_number}: {draft.action_type.value.upper()} "
            f"{draft.drug_id or ''} — {status_badge}"
        )

        with st.container():
            if status == StepStatus.BLOCKED_STRUCK_THROUGH:
                st.markdown(f"### ~~{step_title}~~")
                st.markdown(f"~~Instruction: {draft.narrative_instruction}~~")
                for reason in step.rejection_reasons:
                    st.error(f"Rejection: {reason}")
            else:
                st.markdown(f"### {step_title}")
                st.write(f"**Instruction:** {draft.narrative_instruction}")
                if draft.requested_dose:
                    route_str = draft.route.value if draft.route else "unknown route"
                    st.write(
                        f"**Dose:** {draft.requested_dose.amount} "
                        f"{draft.requested_dose.unit.value} via {route_str}"
                    )
                if step.rejection_reasons:
                    for reason in step.rejection_reasons:
                        st.warning(f"Note: {reason}")

            # Citations chip
            if draft.citations:
                for cit in draft.citations:
                    st.caption(
                        f"🔖 Citation: `{cit.chunk_id}` | Doc: `{cit.doc_id}` | "
                        f"Section: `{cit.section}` [SYNTHETIC PROTOCOL TEXT]\n\n"
                        f'> "{cit.quoted_span}"'
                    )
            st.divider()


def render_llm_narrative(response: TriageResponse) -> None:
    """Render LLM narrative explanation strictly last, below EngineReport."""
    st.subheader("Protocol Explanation & Audit Hash")

    if response.llm_fallback_mode:
        st.info(
            "ℹ️ **LLM Fallback Mode Active**: LLM generation was bypassed or failed. "
            "Deterministic extractive protocol text and engine reports are fully preserved."
        )
    else:
        st.caption(
            "Rule R1: Code decides; the LLM explains. The explanation below is drafted by "
            "an AI model and machine-verified against clinical rules. [SYNTHETIC]"
        )
        if response.verified_steps:
            for s in response.verified_steps:
                st.write(f"- **Step {s.draft.step_number}:** {s.draft.narrative_instruction}")

    st.code(f"Audit Record SHA-256: {response.audit_hash}", language="text")
