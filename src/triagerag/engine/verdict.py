"""Verdict lattice resolution for clinical decision safety.

Safety Property (Rule R2):
Lattice order: BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.
Any presence of a BLOCK severity alert forces the overall verdict to BLOCKED.
Any missing data, unresolved entity, or skipped check forces UNVERIFIED (fail closed),
preventing any false 'CLEAR' assurance.
"""

from __future__ import annotations

from triagerag.contracts.enums import Verdict


def resolve_verdict(
    has_block: bool,
    has_skip_or_unresolved: bool,
    has_alert: bool,
) -> Verdict:
    """Resolve the overall safety verdict from the strict 4-level lattice.

    Lattice priority:
    1. BLOCKED (highest priority): Hard contraindication fired.
    2. UNVERIFIED: Missing vitals, unknown history, unresolved brand, or skipped check.
    3. CHECKED_ALERTS: Checks completed without block or skip, but HIGH/MODERATE/INFO alerts fired.
    4. CHECKED_CLEAR: Complete ruleset coverage without block, skip, or alert.
    """
    if has_block:
        return Verdict.BLOCKED
    if has_skip_or_unresolved:
        return Verdict.UNVERIFIED
    if has_alert:
        return Verdict.CHECKED_ALERTS
    return Verdict.CHECKED_CLEAR
