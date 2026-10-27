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
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction=(
                            "Administer amoxicillin alongside epinephrine immediately into thigh"
                        ),
                        drug_id="epinephrine",
                        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                        route=Route.im,
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

        if self.profile == FakeLLMProfile.INVALID_CITATION:
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.diagnostic,
                        narrative_instruction="Obtain urgent bedside diagnostic electrocardiogram",
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
            return PlanDraft(
                matched_protocol_title=first_chunk.section,
                steps=[
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.maneuver,
                        narrative_instruction="Provide general supportive reassurance",
                        citations=[
                            SpanCitation(
                                doc_id=first_chunk.doc_id,
                                section=first_chunk.section,
                                chunk_id=first_chunk.chunk_id,
                                quoted_span=first_chunk.text[:20],
                            )
                        ],
                    )
                ],
            )

        # Default: COMPLIANT profile
        steps: list[PlanStepDraft] = []
        syndrome = first_chunk.syndrome.lower()

        if "anaphylaxis" in syndrome and "epinephrine" in context.allowed_drug_ids:
            # Find span in chunk
            span = "administer intramuscular epinephrine into the anterolateral mid-thigh"
            if span not in first_chunk.text:
                span = first_chunk.text[:40]
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
                            doc_id=first_chunk.doc_id,
                            section=first_chunk.section,
                            chunk_id=first_chunk.chunk_id,
                            quoted_span=span,
                        )
                    ],
                )
            )
        elif "chest_pain" in syndrome:
            if "nitroglycerin" in context.allowed_drug_ids:
                span = "administer sublingual nitroglycerin as formulary-directed"
                if span not in first_chunk.text:
                    span = first_chunk.text[:40]
                steps.append(
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction=(
                            "Administer emergency medication sublingually for acute "
                            "ischemic chest discomfort"
                        ),
                        drug_id="nitroglycerin",
                        requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
                        route=Route.sublingual,
                        citations=[
                            SpanCitation(
                                doc_id=first_chunk.doc_id,
                                section=first_chunk.section,
                                chunk_id=first_chunk.chunk_id,
                                quoted_span=span,
                            )
                        ],
                    )
                )
            else:
                span = "withhold nitroglycerin completely to prevent refractory vasodilation"
                if span not in first_chunk.text:
                    span = first_chunk.text[:40]
                steps.append(
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.withhold,
                        narrative_instruction=(
                            "Withhold indicated medication due to safety contraindication"
                        ),
                        drug_id="nitroglycerin",
                        citations=[
                            SpanCitation(
                                doc_id=first_chunk.doc_id,
                                section=first_chunk.section,
                                chunk_id=first_chunk.chunk_id,
                                quoted_span=span,
                            )
                        ],
                    )
                )
        elif "sepsis" in syndrome and "ceftriaxone" in context.allowed_drug_ids:
            span = "administer broad-spectrum intravenous ceftriaxone"
            if span not in first_chunk.text:
                span = first_chunk.text[:40]
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=(
                        "Administer broad-spectrum antimicrobial intravenously "
                        "for urgent sepsis screening"
                    ),
                    drug_id="ceftriaxone",
                    requested_dose=ExplicitDose(amount=Decimal("50"), unit=DoseUnit.mg_per_kg),
                    route=Route.iv,
                    citations=[
                        SpanCitation(
                            doc_id=first_chunk.doc_id,
                            section=first_chunk.section,
                            chunk_id=first_chunk.chunk_id,
                            quoted_span=span,
                        )
                    ],
                )
            )
        elif "hypoglycemia" in syndrome and "dextrose" in context.allowed_drug_ids:
            span = "administer intravenous dextrose immediately via secure vascular access"
            if span not in first_chunk.text:
                span = first_chunk.text[:40]
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=(
                        "Administer hypertonic solution intravenously for acute hypoglycemia"
                    ),
                    drug_id="dextrose",
                    requested_dose=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.g),
                    route=Route.iv,
                    citations=[
                        SpanCitation(
                            doc_id=first_chunk.doc_id,
                            section=first_chunk.section,
                            chunk_id=first_chunk.chunk_id,
                            quoted_span=span,
                        )
                    ],
                )
            )
        else:
            # Diagnostic fallback step
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.diagnostic,
                    narrative_instruction=(
                        "Obtain continuous physiological monitoring and bedside screening"
                    ),
                    citations=[
                        SpanCitation(
                            doc_id=first_chunk.doc_id,
                            section=first_chunk.section,
                            chunk_id=first_chunk.chunk_id,
                            quoted_span=first_chunk.text[:30],
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
        # When repairing, switch to clean compliant drafting
        repaired_steps: list[PlanStepDraft] = []
        for step in draft.steps:
            fixed_instruction = step.narrative_instruction
            # Clean any drug names
            for drug in ("epinephrine", "amoxicillin", "nitroglycerin", "morphine"):
                fixed_instruction = fixed_instruction.replace(drug, "indicated agent")

            # Clean citations
            fixed_citations = list(step.citations)
            if context.retrieved_chunks and any("CITATION" in v for v in violations):
                c = context.retrieved_chunks[0]
                fixed_citations = [
                    SpanCitation(
                        doc_id=c.doc_id,
                        section=c.section,
                        chunk_id=c.chunk_id,
                        quoted_span=c.text[:35],
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
