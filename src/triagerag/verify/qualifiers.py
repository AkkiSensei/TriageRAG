"""Protocol THEN-clause qualifier verification module.

Safety Properties (Rule R1, Rule R2, AUB Phase 5 Task T5.2 / AUB-GRD-01):
1. Detects conditional, temporal, and discretionary qualifiers in cited THEN clauses
   (e.g., "repeat", "consider", "after", "following", "continue", "withhold", "until").
2. Rejects drafted instructions that drop these qualifiers while citing the qualified node,
   preventing conversion of repeat/escalated/conditional steps into immediate first-line directives.
3. Fail-closed: if an essential qualifier is dropped in the drafted action, the verifier
   refuses the citation with a structured failure reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from triagerag.normalize.clause_parser import extract_then_else_text, has_if_then_structure


@dataclass(frozen=True)
class QualifierSpec:
    name: str
    then_pattern: re.Pattern[str]
    instruction_patterns: list[re.Pattern[str]]
    description: str


# Controlled qualifiers and allowed drafted equivalents
_QUALIFIER_SPECS: list[QualifierSpec] = [
    QualifierSpec(
        name="repeat",
        then_pattern=re.compile(r"\b(repeat|repeated|repeating|re-administer)\b", re.IGNORECASE),
        instruction_patterns=[
            re.compile(
                r"\b(repeat|repeated|repeating|re-administer|second|subsequent|further|escalated)\b",
                re.IGNORECASE,
            ),
        ],
        description="repeat administration or re-dosing directive",
    ),
    QualifierSpec(
        name="consider",
        then_pattern=re.compile(r"\b(consider|considering|trial of)\b", re.IGNORECASE),
        instruction_patterns=[
            re.compile(
                r"\b(consider|considering|trial|discretion|evaluate for|optional)\b",
                re.IGNORECASE,
            ),
        ],
        description="discretionary or conditional consideration",
    ),
    QualifierSpec(
        name="after",
        then_pattern=re.compile(r"\b(after|following|subsequent to)\b", re.IGNORECASE),
        instruction_patterns=[
            re.compile(
                r"\b(after|following|subsequent to|post|once|following initial)\b",
                re.IGNORECASE,
            ),
        ],
        description="temporal prerequisite or post-therapy condition",
    ),
    QualifierSpec(
        name="continue",
        then_pattern=re.compile(r"\b(continue|continuing|maintain|prolong)\b", re.IGNORECASE),
        instruction_patterns=[
            re.compile(
                r"\b(continue|continuing|maintain|maintenance|prolong|ongoing)\b",
                re.IGNORECASE,
            ),
        ],
        description="maintenance or ongoing therapy directive",
    ),
    QualifierSpec(
        name="withhold",
        then_pattern=re.compile(r"\b(withhold|withholding|avoid|hold|do not)\b", re.IGNORECASE),
        instruction_patterns=[
            re.compile(
                r"\b(withhold|withholding|avoid|hold|do not|stop|discontinue|cease)\b",
                re.IGNORECASE,
            ),
        ],
        description="withholding or avoidance directive",
    ),
    QualifierSpec(
        name="until",
        then_pattern=re.compile(r"\b(until|only when|only if)\b", re.IGNORECASE),
        instruction_patterns=[
            re.compile(r"\b(until|only when|only if|up to)\b", re.IGNORECASE),
        ],
        description="boundary termination or conditional limit",
    ),
    QualifierSpec(
        name="if",
        then_pattern=re.compile(r"\b(if|when|provided that|in the event)\b", re.IGNORECASE),
        instruction_patterns=[
            re.compile(
                r"\b(if|when|provided that|in the event|in case|conditional on|only if)\b",
                re.IGNORECASE,
            ),
        ],
        description="conditional prerequisite in action clause",
    ),
]


def verify_step_qualifiers(
    narrative_instruction: str,
    chunk_text: str,
) -> tuple[bool, str | None]:
    """Verify that essential qualifiers in a cited THEN clause are preserved in the instruction.

    Args:
        narrative_instruction: Drafted clinical instruction text.
        chunk_text: Verbatim protocol chunk text.

    Returns:
        (is_verified, failure_reason_if_any)
    """
    if not has_if_then_structure(chunk_text):
        return True, None

    then_text = extract_then_else_text(chunk_text)
    if not then_text.strip():
        return True, None

    for spec in _QUALIFIER_SPECS:
        if spec.then_pattern.search(then_text):
            # The cited THEN clause contains this qualifier
            matches_instruction = any(
                p.search(narrative_instruction) for p in spec.instruction_patterns
            )
            if not matches_instruction:
                return (
                    False,
                    (
                        f"QUALIFIER_DROPPED: cited node contains '{spec.name}' qualifier "
                        f"({spec.description}) not present in drafted instruction"
                    ),
                )

    return True, None
