"""Deterministic and structured plan repair facilities for LLM drafting.

Safety Property (Rules R1, R7, Section 9):
1. Maximum 2 repair cycles.
2. Feeds back strictly structured violation codes (never echoes untrusted patient complaint text).
3. Unresolved steps are permanently struck with rejection_reasons.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triagerag.contracts.schemas import PlanContext, PlanDraft
    from triagerag.llm.provider import LLMProvider

MAX_REPAIR_CYCLES: int = 2


class ViolationCategory(StrEnum):
    """Controlled vocabulary of structured violation codes for LLM repair feedback."""

    PROSE_LEAK = "PROSE_LEAK"
    INVALID_CITATION = "INVALID_CITATION"
    UNAPPROVED_DRUG = "UNAPPROVED_DRUG"
    CONTRAINDICATED_BLOCK = "CONTRAINDICATED_BLOCK"
    DOSE_MAGNITUDE_ERROR = "DOSE_MAGNITUDE_ERROR"
    HIGH_SEVERITY_INTERACTION = "HIGH_SEVERITY_INTERACTION"
    GENERAL_VIOLATION = "GENERAL_VIOLATION"


def classify_violation(reason: str) -> str:
    """Classify a raw rejection reason into a standardized structured violation code.

    Rule R7: Strips any dynamic narrative content to prevent untrusted prompt injection leakage.
    """
    reason_lower = reason.lower()

    if (
        "lexicon prose leak" in reason_lower
        or "prose drug leak" in reason_lower
        or "drug name in narrative" in reason_lower
    ):
        return (
            f"{ViolationCategory.PROSE_LEAK}: Narrative instruction must not contain drug names; "
            "use generic clinical role"
        )
    if (
        "citation" in reason_lower
        or "verbatim" in reason_lower
        or "chunk_id" in reason_lower
        or "doc_id" in reason_lower
    ):
        return (
            f"{ViolationCategory.INVALID_CITATION}: Quoted span must be a verbatim substring "
            "of a retrieved chunk"
        )
    if (
        "formulary" in reason_lower
        or "unapproved" in reason_lower
        or "unknown drug" in reason_lower
    ):
        return (
            f"{ViolationCategory.UNAPPROVED_DRUG}: Drug ID must exist in the provided "
            "allowed formulary list"
        )
    if "contraindicated" in reason_lower or "block" in reason_lower:
        return (
            f"{ViolationCategory.CONTRAINDICATED_BLOCK}: Drug has a BLOCK-level contraindication "
            "and cannot be administered"
        )
    if "magnitude" in reason_lower or "dose" in reason_lower or "ceiling" in reason_lower:
        return (
            f"{ViolationCategory.DOSE_MAGNITUDE_ERROR}: Requested dose exceeds allowable "
            "mathematical magnitude bounds"
        )
    if "high" in reason_lower:
        return (
            f"{ViolationCategory.HIGH_SEVERITY_INTERACTION}: Drug has a HIGH-severity alert "
            "requiring explicit justification"
        )

    return f"{ViolationCategory.GENERAL_VIOLATION}: Plan step failed machine validation constraints"


def sanitize_repair_violations(reasons: list[str]) -> list[str]:
    """Sanitize and deduplicate rejection reasons into structured codes for LLM feedback.

    Guarantees no untrusted chief complaint or unverified narrative is echoed back to the LLM.
    """
    structured: set[str] = set()
    for r in reasons:
        if r.strip():
            structured.add(classify_violation(r))
    return sorted(structured)


def attempt_plan_repair(
    llm: LLMProvider,
    context: PlanContext,
    draft: PlanDraft,
    violations: list[str],
) -> PlanDraft:
    """Execute a plan repair attempt using the configured LLM provider and structured codes."""
    return llm.repair_plan(context, draft, violations)
