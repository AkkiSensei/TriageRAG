"""Deterministic Fake LLM provider for testing and validation.

Safety Property (Section 9):
Emulates all adversarial and compliant drafting profiles without network access:
COMPLIANT, INVENT_DRUG, PROSE_LEAK, INVALID_CITATION, IGNORE_BLOCK,
OBEY_COMPLAINT, and NAIVE_FREE_TEXT.
"""

from __future__ import annotations

import re
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
from triagerag.normalize.clause_parser import extract_then_else_text, has_if_then_structure


class FakeLLMProfile(StrEnum):
    """Profiles for deterministic FakeLLM behavior."""

    COMPLIANT = "COMPLIANT"
    INVENT_DRUG = "INVENT_DRUG"
    PROSE_LEAK = "PROSE_LEAK"
    INVALID_CITATION = "INVALID_CITATION"
    IGNORE_BLOCK = "IGNORE_BLOCK"
    OBEY_COMPLAINT = "OBEY_COMPLAINT"
    NAIVE_FREE_TEXT = "NAIVE_FREE_TEXT"
    RANKED_CHOICE = "RANKED_CHOICE"
    WRONG_BUT_MATCHING_CLAUSE = "WRONG_BUT_MATCHING_CLAUSE"
    QUALIFIER_DROP = "QUALIFIER_DROP"


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

        if self.profile == FakeLLMProfile.RANKED_CHOICE:
            # Dynamically select from the top ranked child chunk in retrieved ranking
            child_chunks = [
                c
                for c in context.retrieved_chunks
                if c.parent_id is not None or "_NODE_" in c.chunk_id
            ]
            top_chunk = child_chunks[0] if child_chunks else context.retrieved_chunks[0]

            text = top_chunk.text
            if has_if_then_structure(text):
                act_text = extract_then_else_text(text).strip()
            else:
                lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 15]
                act_text = lines[0] if lines else text.strip()

            quoted_span = act_text[: min(len(act_text), 80)]
            if quoted_span not in top_chunk.text:
                quoted_span = top_chunk.text[: min(len(top_chunk.text), 60)]

            bound_drug: str | None = None
            for allowed in context.allowed_drug_ids:
                if allowed.lower() in act_text.lower():
                    bound_drug = allowed
                    break

            if bound_drug:
                route = (
                    Route.im
                    if "intramuscular" in act_text.lower()
                    else Route.iv
                    if "intravenous" in act_text.lower()
                    else Route.oral
                )
                ranked_steps = [
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction=act_text,
                        drug_id=bound_drug,
                        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                        route=route,
                        citations=[
                            SpanCitation(
                                doc_id=top_chunk.doc_id,
                                section=top_chunk.section,
                                chunk_id=top_chunk.chunk_id,
                                quoted_span=quoted_span,
                            )
                        ],
                    )
                ]
            else:
                act_type = (
                    ActionType.diagnostic
                    if any(
                        w in act_text.lower()
                        for w in ("obtain", "ecg", "imaging", "x-ray", "blood", "test")
                    )
                    else ActionType.monitor
                    if "monitor" in act_text.lower()
                    else ActionType.maneuver
                )
                ranked_steps = [
                    PlanStepDraft(
                        step_number=1,
                        action_type=act_type,
                        narrative_instruction=act_text,
                        citations=[
                            SpanCitation(
                                doc_id=top_chunk.doc_id,
                                section=top_chunk.section,
                                chunk_id=top_chunk.chunk_id,
                                quoted_span=quoted_span,
                            )
                        ],
                    )
                ]

            return PlanDraft(
                matched_protocol_title=top_chunk.section,
                steps=ranked_steps,
            )

        if self.profile == FakeLLMProfile.WRONG_BUT_MATCHING_CLAUSE:
            # Selects a valid verbatim span from a node whose applicability
            # preconditions are NOT met by the patient
            target_chunk: RetrievedChunk | None = None
            for c in context.retrieved_chunks:
                if "_NODE_3" in c.chunk_id or "_NODE_4" in c.chunk_id or "_NODE_2" in c.chunk_id:
                    target_chunk = c
                    break
            if target_chunk is None:
                target_chunk = context.retrieved_chunks[0]

            if has_if_then_structure(target_chunk.text):
                act_text = extract_then_else_text(target_chunk.text).strip()
            else:
                act_text = target_chunk.text.strip()

            quoted_span = act_text[: min(len(act_text), 80)]
            if quoted_span not in target_chunk.text:
                quoted_span = target_chunk.text[: min(len(target_chunk.text), 60)]

            bound_drug = None
            for allowed in context.allowed_drug_ids:
                if allowed.lower() in act_text.lower():
                    bound_drug = allowed
                    break

            if bound_drug:
                route = (
                    Route.im
                    if "intramuscular" in act_text.lower()
                    else Route.iv
                    if "intravenous" in act_text.lower()
                    else Route.oral
                )
                wrong_steps = [
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction=act_text,
                        drug_id=bound_drug,
                        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                        route=route,
                        citations=[
                            SpanCitation(
                                doc_id=target_chunk.doc_id,
                                section=target_chunk.section,
                                chunk_id=target_chunk.chunk_id,
                                quoted_span=quoted_span,
                            )
                        ],
                    )
                ]
            else:
                wrong_steps = [
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.maneuver,
                        narrative_instruction=act_text,
                        citations=[
                            SpanCitation(
                                doc_id=target_chunk.doc_id,
                                section=target_chunk.section,
                                chunk_id=target_chunk.chunk_id,
                                quoted_span=quoted_span,
                            )
                        ],
                    )
                ]

            return PlanDraft(
                matched_protocol_title=target_chunk.section,
                steps=wrong_steps,
            )

        if self.profile == FakeLLMProfile.QUALIFIER_DROP:
            # Find a chunk that contains a qualifier in its THEN clause (repeat, consider, after)
            target_chunk = None
            for c in context.retrieved_chunks:
                lower = c.text.lower()
                if "repeat" in lower or "consider" in lower or "after" in lower:
                    target_chunk = c
                    break
            if target_chunk is None:
                target_chunk = context.retrieved_chunks[0]

            if has_if_then_structure(target_chunk.text):
                act_text = extract_then_else_text(target_chunk.text).strip()
            else:
                act_text = target_chunk.text.strip()

            quoted_span = act_text[: min(len(act_text), 80)]
            if quoted_span not in target_chunk.text:
                quoted_span = target_chunk.text[: min(len(target_chunk.text), 60)]

            # Deliberately strip out qualifier words from the drafted narrative instruction
            dropped_narrative = act_text
            for q_word in (
                "repeat",
                "Repeat",
                "repeated",
                "Repeated",
                "consider",
                "Consider",
                "after",
                "After",
            ):
                dropped_narrative = re.sub(rf"\b{q_word}\b", "", dropped_narrative)
            dropped_narrative = " ".join(dropped_narrative.split()).strip()
            if not dropped_narrative.lower().startswith("administer"):
                dropped_narrative = f"Administer {dropped_narrative} immediately"

            bound_drug = None
            for allowed in context.allowed_drug_ids:
                if allowed.lower() in target_chunk.text.lower():
                    bound_drug = allowed
                    break

            if bound_drug:
                route = (
                    Route.im
                    if "intramuscular" in target_chunk.text.lower()
                    else Route.iv
                    if "intravenous" in target_chunk.text.lower()
                    else Route.oral
                )
                drop_steps = [
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.administer,
                        narrative_instruction=dropped_narrative,
                        drug_id=bound_drug,
                        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                        route=route,
                        citations=[
                            SpanCitation(
                                doc_id=target_chunk.doc_id,
                                section=target_chunk.section,
                                chunk_id=target_chunk.chunk_id,
                                quoted_span=quoted_span,
                            )
                        ],
                    )
                ]
            else:
                drop_steps = [
                    PlanStepDraft(
                        step_number=1,
                        action_type=ActionType.maneuver,
                        narrative_instruction=dropped_narrative,
                        citations=[
                            SpanCitation(
                                doc_id=target_chunk.doc_id,
                                section=target_chunk.section,
                                chunk_id=target_chunk.chunk_id,
                                quoted_span=quoted_span,
                            )
                        ],
                    )
                ]

            return PlanDraft(
                matched_protocol_title=target_chunk.section,
                steps=drop_steps,
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
        elif "asthma" in syndrome and "salbutamol" in context.allowed_drug_ids:
            sup_chunk, span = _select_supporting_chunk_and_span(
                context.retrieved_chunks,
                (
                    "administer nebulized salbutamol continuous bronchodilator "
                    "therapy with high-flow oxygen"
                ),
                ["salbutamol", "administer"],
            )
            steps.append(
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.administer,
                    narrative_instruction=("Administer nebulized therapy with high-flow oxygen"),
                    drug_id="salbutamol",
                    requested_dose=ExplicitDose(amount=Decimal("5"), unit=DoseUnit.mg),
                    route=Route.nebulized,
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
