"""Verdict lattice resolution for clinical decision safety.

Safety Property (Rule R2, Rule R11, T1.1 / AUB-VRD-01):
Lattice order: BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.
Any presence of a BLOCK severity alert forces the overall verdict to BLOCKED.
Any missing data, unresolved entity, skipped check, retrieval abstention, or
absence of approved steps forces UNVERIFIED (fail closed), preventing any false
'CLEAR' assurance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from triagerag.contracts.enums import AbstainCode, Verdict

if TYPE_CHECKING:
    from triagerag.contracts.schemas import RetrievalReport


def resolve_verdict_with_reason(
    has_block: bool,
    has_skip_or_unresolved: bool,
    has_alert: bool,
    *,
    has_unverified_steps: bool = False,
    has_coverage_gaps: bool = False,
    retrieval_report: RetrievalReport | None = None,
    has_approved_steps: bool | None = None,
) -> tuple[Verdict, str | None]:
    """Resolve the overall safety verdict and structured reason from the 4-level lattice.

    Priority:
    1. BLOCKED: Hard contraindication or BLOCK alert triggered.
    2. UNVERIFIED: Missing vitals, unknown history, unresolved entity, skipped check,
       coverage gap, unverified step, retrieval abstention, or no approved steps.
    3. CHECKED_ALERTS: Checks completed without block or skip, but non-blocking alerts fired.
    4. CHECKED_CLEAR: Complete ruleset coverage without block, skip, or alert, and with
       approved steps.
    """
    if has_block:
        return (
            Verdict.BLOCKED,
            "Absolute clinical contraindication or BLOCK safety alert triggered.",
        )

    if has_skip_or_unresolved:
        return (
            Verdict.UNVERIFIED,
            "Missing vitals, unknown clinical history, unresolved entity, or skipped check.",
        )
    if has_unverified_steps:
        return (
            Verdict.UNVERIFIED,
            "Proposed plan steps contain ungrounded or unverified actions.",
        )
    if has_coverage_gaps:
        return (
            Verdict.UNVERIFIED,
            "Known ruleset coverage gaps in active ruleset.",
        )
    if retrieval_report is not None and (
        retrieval_report.abstained or retrieval_report.abstain_code != AbstainCode.NONE
    ):
        code_val = (
            retrieval_report.abstain_code.value
            if hasattr(retrieval_report.abstain_code, "value")
            else str(retrieval_report.abstain_code)
        )
        return (
            Verdict.UNVERIFIED,
            f"Protocol retrieval abstained under safety gate '{code_val}': "
            f"{retrieval_report.reason}",
        )
    if has_approved_steps is False:
        return (
            Verdict.UNVERIFIED,
            "No proposed plan steps have an APPROVED verification status.",
        )

    if has_alert:
        return (
            Verdict.CHECKED_ALERTS,
            "Safety checks completed with non-blocking clinical warnings "
            "(HIGH/MODERATE/INFO alerts).",
        )

    return Verdict.CHECKED_CLEAR, None


def resolve_verdict(
    has_block: bool,
    has_skip_or_unresolved: bool,
    has_alert: bool,
    *,
    has_unverified_steps: bool = False,
    has_coverage_gaps: bool = False,
    retrieval_report: RetrievalReport | None = None,
    has_approved_steps: bool | None = None,
) -> Verdict:
    """Resolve the overall safety verdict from the strict 4-level lattice."""
    verdict, _ = resolve_verdict_with_reason(
        has_block=has_block,
        has_skip_or_unresolved=has_skip_or_unresolved,
        has_alert=has_alert,
        has_unverified_steps=has_unverified_steps,
        has_coverage_gaps=has_coverage_gaps,
        retrieval_report=retrieval_report,
        has_approved_steps=has_approved_steps,
    )
    return verdict
