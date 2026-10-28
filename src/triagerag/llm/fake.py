"""Deterministic Fake LLM provider for testing and validation.

Safety Property (Section 9):
Emulates all adversarial and compliant drafting profiles without network access:
COMPLIANT, INVENT_DRUG, PROSE_LEAK, INVALID_CITATION, IGNORE_BLOCK,
OBEY_COMPLAINT, and NAIVE_FREE_TEXT.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from triagerag.contracts.enums import ActionType, DoseUnit, Route
from triagerag.contracts.schemas import (
    ExplicitDose,
    PlanContext,
    PlanDraft,
    PlanStepDraft,
    RetrievedChunk,
    SpanCitation,
)
from triagerag.llm.provider import LLMProvider


class FakeLLMProfile(StrEnum):
    """Profiles for deterministic FakeLLM behavior."""

    COMPLIANT = "COMPLIANT"
    INVENT_DRUG = "INVENT_DRUG"
    PROSE_LEAK = "PROSE_LEAK"
    INVALID_CITATION = "INVALID_CITATION"
    IGNORE_BLOCK = "IGNORE_BLOCK"
    OBEY_COMPLAINT = "OBEY_COMPLAINT"
    NAIVE_FREE_TEXT = "NAIVE_FREE_TEXT"


def _select_supporting_chunk_and_span(
    chunks: list[RetrievedChunk],
    target_span: str,
    fallback_keywords: list[str] | None = None,
) -> tuple[RetrievedChunk, str]:
    """Select the specific child node containing target_span (or fallback keywords)."""
    child_chunks = [c for c in chunks if c.parent_id is not None or "_NODE_" in c.chunk_id]
    candidate_pool = child_chunks if child_chunks else chunks

    for chunk in candidate_pool:
        if target_span.lower() in chunk.text.lower():
            return chunk, target_span

    for chunk in chunks:
        if target_span.lower() in chunk.text.lower():
            return chunk, target_span

    if fallback_keywords:
        for kw in fallback_keywords:
            kw_low = kw.lower()
            for chunk in candidate_pool:
                if kw_low in chunk.text.lower():
                    for line in chunk.text.splitlines():
                        stripped = line.strip()
                        if kw_low in stripped.lower() and len(stripped) >= 10:
                            return chunk, stripped[:80]
                    return chunk, chunk.text.strip()[:60]

    chosen = candidate_pool[0]
    for line in chosen.text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("THEN ") and len(stripped) >= 10:
            return chosen, stripped[:80]
    return chosen, chosen.text.strip()[:60]


class FakeLLM(LLMProvider):
    """Deterministic, pure LLM implementation for testing and evaluation."""

    def __init__(self, profile: FakeLLMProfile = FakeLLMProfile.COMPLIANT) -> None:
        self.profile = profile

    def draft_plan(self, context: PlanContext) -> PlanDraft:
        """Draft plan based on the configured profile."""
        if not context.retrieved_chunks:
            return PlanDraft(matched_protocol_title="No Protocol Matched", steps=[])

        first_chunk = context.retrieved_chunks[0]

        if self.profile == FakeLLMProfile.INVENT_DRUG:
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction="Administer novel unapproved compound",
                        drug_id="fictional_wonder_drug_xyz",
                        requested_dose=ExplicitDose(amount=Decimal("100"), unit=DoseUnit.mg),
                        route=Route.iv,
                        citations=[
                            SpanCitation(
                                doc_id=first_chunk.doc_id,
                                section=first_chunk.section,
                                chunk_id=first_chunk.chunk_id,
                                quoted_span=first_chunk.text[:30],
                            )
                        ],
                    )
                ],
            )

        if self.profile == FakeLLMProfile.PROSE_LEAK:
            # Leaks unbound drug name (amoxicillin) in narrative instruction (Section 10 violation)
            sup_chunk, sup_span = _select_supporting_chunk_and_span(
                context.retrieved_chunks,
                "administer intramuscular epinephrine into the anterolateral mid-thigh",
                ["epinephrine", "administer"],
            )
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction=(
                            "Administer amoxicillin alongside epinephrine intramuscularly "
                            "into the anterolateral mid-thigh"
                        ),
                        drug_id="epinephrine",
                        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                        route=Route.im,
                        citations=[
                            SpanCitation(
                                doc_id=sup_chunk.doc_id,
                                section=sup_chunk.section,
                                chunk_id=sup_chunk.chunk_id,
                                quoted_span=sup_span,
                            )
                        ],
                    )
                ],
            )

        if self.profile == FakeLLMProfile.INVALID_CITATION:
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.diagnostic,
                        narrative_instruction=(
                            "Obtain immediate bedside diagnostic electrocardiogram"
                        ),
                        citations=[
                            SpanCitation(
                                doc_id="NONEXISTENT_DOC",
                                section="Fake Section",
                                chunk_id="NONEXISTENT_CHUNK_999",
                                quoted_span="Completely fabricated citation span not in chunk",
                            )
                        ],
                    )
                ],
            )

        if self.profile == FakeLLMProfile.IGNORE_BLOCK:
            # Proposes a blocked drug that was excluded from allowed_drug_ids
            blocked_drug = "nitroglycerin"
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction="Administer coronary vasodilator sublingually",
                        drug_id=blocked_drug,
                        requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
                        route=Route.sublingual,
                        citations=[
                            SpanCitation(
                                doc_id=first_chunk.doc_id,
                                section=first_chunk.section,
                                chunk_id=first_chunk.chunk_id,
                                quoted_span=first_chunk.text[:30],
                            )
                        ],
                    )
                ],
            )

        if self.profile == FakeLLMProfile.OBEY_COMPLAINT:
            complaint = context.chief_complaint_delimited or ""
            if "morphine" in complaint.lower():
                return PlanDraft(
                    matched_protocol_title=first_chunk.section,
                    steps=[
                        PlanStepDraft(
                            step_number=1,
                            action_type=ActionType.administer,
                            narrative_instruction="Administer high-dose opioid as in complaint",
                            drug_id="morphine",
                            requested_dose=ExplicitDose(amount=Decimal("100"), unit=DoseUnit.mg),
                            route=Route.iv,
                            citations=[
                                SpanCitation(
                                    doc_id=first_chunk.doc_id,
                                    section=first_chunk.section,
                                    chunk_id=first_chunk.chunk_id,
                                    quoted_span=first_chunk.text[:30],
                                )
                            ],
                        )
                    ],
                )

        if self.profile == FakeLLMProfile.NAIVE_FREE_TEXT:
            sup_chunk, sup_span = _select_supporting_chunk_and_span(
                context.retrieved_chunks,
                "obtain immediate",
                ["obtain", "assess", "monitor"],
            )
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.maneuver,
                        narrative_instruction="Provide general supportive reassurance and monitor",
                        citations=[
                            SpanCitation(
                                doc_id=sup_chunk.doc_id,
                                section=sup_chunk.section,
                                chunk_id=sup_chunk.chunk_id,
                                quoted_span=sup_span,
                            )
                        ],
                    )
                ],
            )

        # Default: COMPLIANT profile
        steps: list[PlanStepDraft] = []
        syndrome = first_chunk.syndrome.lower()

        if "anaphylaxis" in syndrome and "epinephrine" in context.allowed_drug_ids:
            sup_chunk, span = _select_supporting_chunk_and_span(
                context.retrieved_chunks,
                "administer intramuscular epinephrine into the anterolateral mid-thigh",
                ["epinephrine", "administer"],
            )
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=(
                        "Administer first-line emergency medication intramuscularly "
                        "into the anterolateral mid-thigh"
                    ),
                    drug_id="epinephrine",
                    requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                    route=Route.im,
                    citations=[
                        SpanCitation(
                            doc_id=sup_chunk.doc_id,
                            section=sup_chunk.section,
                            chunk_id=sup_chunk.chunk_id,
                            quoted_span=span,
                        )
                    ],
                )
            )
        elif "chest_pain" in syndrome:
            if "nitroglycerin" in context.allowed_drug_ids:
                sup_chunk, span = _select_supporting_chunk_and_span(
                    context.retrieved_chunks,
                    "administer sublingual nitroglycerin as formulary-directed",
                    ["nitroglycerin", "sublingual"],
                )
                steps.append(
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction=(
                            "Administer sublingual emergency medication as formulary-directed "
                            "for acute ischemic chest discomfort"
                        ),
                        drug_id="nitroglycerin",
                        requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
                        route=Route.sublingual,
                        citations=[
                            SpanCitation(
                                doc_id=sup_chunk.doc_id,
                                section=sup_chunk.section,
                                chunk_id=sup_chunk.chunk_id,
                                quoted_span=span,
                            )
                        ],
                    )
                )
            else:
                sup_chunk, span = _select_supporting_chunk_and_span(
                    context.retrieved_chunks,
                    "withhold nitroglycerin completely to prevent refractory vasodilation",
                    ["withhold", "nitroglycerin"],
                )
                steps.append(
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.withhold,
                        narrative_instruction=(
                            "Withhold indicated medication completely to prevent "
                            "refractory vasodilation"
                        ),
                        drug_id="nitroglycerin",
                        citations=[
                            SpanCitation(
                                doc_id=sup_chunk.doc_id,
                                section=sup_chunk.section,
                                chunk_id=sup_chunk.chunk_id,
                                quoted_span=span,
                            )
                        ],
                    )
                )
        elif "sepsis" in syndrome and "ceftriaxone" in context.allowed_drug_ids:
            sup_chunk, span = _select_supporting_chunk_and_span(
                context.retrieved_chunks,
                "administer broad-spectrum intravenous ceftriaxone",
                ["ceftriaxone", "broad-spectrum"],
            )
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=(
                        "Administer broad-spectrum intravenous antimicrobial "
                        "for urgent sepsis screening"
                    ),
                    drug_id="ceftriaxone",
                    requested_dose=ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg_per_kg),
                    route=Route.iv,
                    citations=[
                        SpanCitation(
                            doc_id=sup_chunk.doc_id,
                            section=sup_chunk.section,
                            chunk_id=sup_chunk.chunk_id,
                            quoted_span=span,
                        )
                    ],
                )
            )
        elif "hypoglycemia" in syndrome and "dextrose" in context.allowed_drug_ids:
            sup_chunk, span = _select_supporting_chunk_and_span(
                context.retrieved_chunks,
                "administer intravenous dextrose immediately via secure vascular access",
                ["dextrose", "intravenous"],
            )
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=(
                        "Administer intravenous hypertonic solution immediately "
                        "via secure vascular access"
                    ),
                    drug_id="dextrose",
                    requested_dose=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.g),
                    route=Route.iv,
                    citations=[
                        SpanCitation(
                            doc_id=sup_chunk.doc_id,
                            section=sup_chunk.section,
                            chunk_id=sup_chunk.chunk_id,
                            quoted_span=span,
                        )
                    ],
                )
            )
        else:
            sup_chunk, span = _select_supporting_chunk_and_span(
                context.retrieved_chunks,
                "obtain immediate",
                ["obtain", "assess", "monitor", "administer"],
            )
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.diagnostic,
                    narrative_instruction=(
                        f"Obtain continuous physiological monitoring and follow "
                        f"protocol: {span[:30]}"
                    ),
                    citations=[
                        SpanCitation(
                            doc_id=sup_chunk.doc_id,
                            section=sup_chunk.section,
                            chunk_id=sup_chunk.chunk_id,
                            quoted_span=span,
                        )
                    ],
                )
            )

        return PlanDraft(
            matched_protocol_title=first_chunk.section,
            steps=steps,
        )

    def repair_plan(
        self,
        context: PlanContext,
        draft: PlanDraft,
        violations: list[str],
    ) -> PlanDraft:
        """Repair loop implementation for FakeLLM."""
        repaired_steps: list[PlanStepDraft] = []
        for step in draft.steps:
            fixed_instruction = step.narrative_instruction
            for drug in ("epinephrine", "amoxicillin", "nitroglycerin", "morphine"):
                fixed_instruction = fixed_instruction.replace(drug, "indicated agent")

            fixed_citations = list(step.citations)
            if context.retrieved_chunks and any("CITATION" in v for v in violations):
                keywords: list[str] = []
                if step.drug_id:
                    keywords.append(step.drug_id)
                keywords.extend(
                    ["electrocardiogram", "monitor", "obtain", "administer", "withhold"]
                )
                sup_chunk, sup_span = _select_supporting_chunk_and_span(
                    context.retrieved_chunks,
                    "obtain immediate 12-lead electrocardiogram",
                    keywords,
                )
                fixed_citations = [
                    SpanCitation(
                        doc_id=sup_chunk.doc_id,
                        section=sup_chunk.section,
                        chunk_id=sup_chunk.chunk_id,
                        quoted_span=sup_span,
                    )
                ]

            repaired_steps.append(
                PlanStepDraft(
                    step_number=step.step_number,
                    action_type=step.action_type,
                    narrative_instruction=fixed_instruction,
                    drug_id=step.drug_id,
                    requested_dose=step.requested_dose,
                    route=step.route,
                    citations=fixed_citations,
                )
            )

        return PlanDraft(
            matched_protocol_title=draft.matched_protocol_title,
            steps=repaired_steps,
        )
