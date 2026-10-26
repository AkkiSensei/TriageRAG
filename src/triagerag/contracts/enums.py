"""Enumeration definitions for TriageRAG contracts.

Safety Property:
Closed enumeration sets prevent invalid clinical strings, ambiguous routes,
unmapped units, and arbitrary severity overrides across the entire pipeline.
"""

from __future__ import annotations

from enum import StrEnum


class SourceStatus(StrEnum):
    """Retrieval and clinical review status of an evidence source."""

    PLACEHOLDER_UNRETRIEVED = "PLACEHOLDER_UNRETRIEVED"
    RETRIEVED_UNREVIEWED = "RETRIEVED_UNREVIEWED"
    REVIEWED = "REVIEWED"


class ContentOrigin(StrEnum):
    """Origin tracking for rule and formulary facts."""

    AGENT_DRAFT_UNSOURCED = "AGENT_DRAFT_UNSOURCED"
    HUMAN_AUTHORED = "HUMAN_AUTHORED"
    SOURCE_EXTRACT = "SOURCE_EXTRACT"


class Verdict(StrEnum):
    """Top-level safety verdict resolved from the lattice BLOCKED > UNVERIFIED > ALERTS > CLEAR."""

    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    CHECKED_ALERTS = "CHECKED_ALERTS"
    CHECKED_CLEAR = "CHECKED_CLEAR"


class Severity(StrEnum):
    """Clinical severity levels for safety alerts."""

    BLOCK = "BLOCK"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    INFO = "INFO"


class ScoreBand(StrEnum):
    """Risk stratification score bands."""

    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    UNSCORED = "UNSCORED"


class AgeUnit(StrEnum):
    """Units of chronological age."""

    days = "days"
    months = "months"
    years = "years"


class DoseUnit(StrEnum):
    """Controlled clinical dosage units."""

    mcg = "mcg"
    mg = "mg"
    g = "g"
    mL = "mL"
    IU = "IU"
    mcg_per_kg = "mcg/kg"
    mg_per_kg = "mg/kg"
    mcg_per_kg_min = "mcg/kg/min"
    mg_per_kg_hr = "mg/kg/hr"


class Route(StrEnum):
    """Medication administration routes."""

    oral = "oral"
    iv = "iv"
    im = "im"
    sc = "sc"
    inhaled = "inhaled"
    sublingual = "sublingual"
    rectal = "rectal"
    topical = "topical"
    nebulized = "nebulized"


class Consciousness(StrEnum):
    """AVPU+C scale: A (Alert), C (New Confusion), V (Voice), P (Pain), U (Unresponsive).

    Early-warning scores (NEWS2) treat new onset confusion 'C' distinctly with maximum score.
    """

    A = "A"
    C = "C"
    V = "V"
    P = "P"
    U = "U"


class RuleStatus(StrEnum):
    """Operational status of a clinical rule or threshold."""

    ACTIVE = "ACTIVE"
    NEEDS_SOURCE = "NEEDS_SOURCE"


class StepStatus(StrEnum):
    """Verification verdict for a proposed plan step."""

    APPROVED = "APPROVED"
    FLAGGED_HIGH = "FLAGGED_HIGH"
    FLAGGED_MODERATE = "FLAGGED_MODERATE"
    UNVERIFIED_MISSING_DATA = "UNVERIFIED_MISSING_DATA"
    CITATION_UNVERIFIED = "CITATION_UNVERIFIED"
    BLOCKED_STRUCK_THROUGH = "BLOCKED_STRUCK_THROUGH"


class ActionType(StrEnum):
    """Action category of a clinical plan step."""

    administer = "administer"
    withhold = "withhold"
    monitor = "monitor"
    diagnostic = "diagnostic"
    maneuver = "maneuver"


class PopulationCategory(StrEnum):
    """Physiological population groups."""

    neonate = "neonate"
    paediatric = "paediatric"
    adult = "adult"
