"""Citation verification module for clinical protocol groundedness.

Safety Property (RAG-02, Rules R1, R2, R3, Section 10):
1. chunk_id must match a verified chunk from the current retrieval report.
2. Parent-only chunk citations are rejected when child decision nodes exist for that document.
3. quoted_span must be an exact verbatim whitespace-normalized substring of the chunk.
4. Enforces minimum lexical overlap threshold between narrative instruction and cited span.
5. Administer/withhold steps must cite a chunk containing the step's drug (or alias) AND
   a matching action cue (administer vs withhold).
6. Failures result in CITATION_UNVERIFIED status.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from triagerag.config import get_data_dir
from triagerag.contracts.enums import ActionType
from triagerag.contracts.schemas import Provenance
from triagerag.normalize.yaml_loader import load_yaml_decimal

if TYPE_CHECKING:
    from triagerag.contracts.schemas import PlanStepDraft, RetrievedChunk, SpanCitation
    from triagerag.engine.registry import ClinicalRegistry


class ActionCuesConfig(BaseModel):
    """Configuration for citation overlap thresholds and clinical action cue lexicons."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "1.0.0"
    min_overlap_threshold: float = 0.08
    min_span_chars: int = 10
    administer_cues: list[str]
    withhold_cues: list[str]
    provenance: Provenance


def load_action_cues(data_dir: Path | None = None) -> ActionCuesConfig:
    """Load action cue lexicon and citation verification thresholds from YAML."""
    resolved_dir = data_dir if data_dir is not None else get_data_dir()
    cues_path = resolved_dir / "retrieval" / "action_cues.yaml"
    raw = load_yaml_decimal(cues_path)
    return ActionCuesConfig.model_validate(raw)


def _normalize_whitespace(text: str) -> str:
    """Normalize repeated whitespace, tabs, and newlines to single spaces."""
    return " ".join(text.split()).strip()


def compute_lexical_overlap(instruction: str, quoted_span: str) -> float:
    """Compute token Jaccard overlap between narrative instruction and cited span."""
    inst_tokens = set(re.findall(r"\b[A-Za-z0-9]+\b", instruction.lower()))
    span_tokens = set(re.findall(r"\b[A-Za-z0-9]+\b", quoted_span.lower()))

    if not inst_tokens or not span_tokens:
        return 0.0

    intersection = inst_tokens & span_tokens
    union = inst_tokens | span_tokens
    return round(len(intersection) / len(union), 4)


def verify_citation(
    citation: SpanCitation,
    retrieved_chunks: list[RetrievedChunk],
    narrative_instruction: str,
    *,
    min_overlap: float | None = None,
) -> tuple[bool, float, str | None]:
    """Verify that a step citation is grounded in retrieved chunks.

    Returns:
        (is_verified, lexical_overlap_score, failure_reason)
    """
    cfg = load_action_cues()

    # 1. Minimum quoted span length (Section 4)
    if len(citation.quoted_span.strip()) < cfg.min_span_chars:
        return (
            False,
            0.0,
            f"Quoted span too short ({len(citation.quoted_span.strip())} < "
            f"{cfg.min_span_chars} characters)",
        )

    # 2. Check chunk existence
    chunk_map = {c.chunk_id: c for c in retrieved_chunks}
    if citation.chunk_id not in chunk_map:
        return (
            False,
            0.0,
            f"Citation chunk_id '{citation.chunk_id}' not found in retrieved chunks",
        )

    matched_chunk = chunk_map[citation.chunk_id]
    if citation.doc_id != matched_chunk.doc_id:
        return (
            False,
            0.0,
            f"Citation doc_id '{citation.doc_id}' does not match "
            f"chunk doc_id '{matched_chunk.doc_id}'",
        )

    # 3. Child-node citation rule (RAG-02): reject parent-only chunk when child nodes exist
    is_parent_chunk = matched_chunk.parent_id is None and "_NODE_" not in matched_chunk.chunk_id
    if is_parent_chunk:
        has_child_for_doc = any(
            c.doc_id == matched_chunk.doc_id and (c.parent_id is not None or "_NODE_" in c.chunk_id)
            for c in retrieved_chunks
        )
        if has_child_for_doc:
            return (
                False,
                0.0,
                f"Parent-only citation '{citation.chunk_id}' rejected when child decision nodes "
                f"exist for document '{matched_chunk.doc_id}'",
            )

    # 4. Exact verbatim substring check (whitespace normalized)
    norm_span = _normalize_whitespace(citation.quoted_span)
    norm_chunk_text = _normalize_whitespace(matched_chunk.text)

    if norm_span.lower() not in norm_chunk_text.lower():
        msg = (
            f"Quoted span '{citation.quoted_span[:30]}...' is not a verbatim "
            f"substring of chunk {citation.chunk_id}"
        )
        return False, 0.0, msg

    # 5. Compute lexical overlap score and enforce minimum overlap gate (RAG-02)
    overlap = compute_lexical_overlap(narrative_instruction, citation.quoted_span)
    eff_min_overlap = min_overlap if min_overlap is not None else cfg.min_overlap_threshold
    if overlap < eff_min_overlap:
        return (
            False,
            overlap,
            f"Citation lexical overlap {overlap:.4f} is below minimum threshold "
            f"{eff_min_overlap:.4f}",
        )

    return True, overlap, None


def verify_step_support(
    step: PlanStepDraft,
    cited_chunks: list[RetrievedChunk],
    registry: ClinicalRegistry,
    *,
    data_dir: Path | None = None,
) -> tuple[bool, str]:
    """Verify deterministic drug and action-cue support in cited chunks (RAG-02).

    Prevents 'citation laundering' where a step proposes administering/withholding a drug
    while citing an unrelated chunk or a chunk with the opposite action polarity.
    """
    if not cited_chunks:
        return False, "No verified cited chunks available for step support verification"

    cfg = load_action_cues(data_dir)

    if step.action_type in (ActionType.administer, ActionType.withhold) and step.drug_id:
        drug_id_lower = step.drug_id.lower()
        drug_terms: set[str] = {drug_id_lower, drug_id_lower.replace("_", " ")}
        for alias_name, alias_entry in registry.aliases.items():
            if any(ing.lower() == drug_id_lower for ing in alias_entry.ingredient_ids):
                drug_terms.add(alias_name.lower())

        required_cues = (
            cfg.administer_cues if step.action_type == ActionType.administer else cfg.withhold_cues
        )

        for chunk in cited_chunks:
            chunk_lower = _normalize_whitespace(chunk.text).lower()
            has_drug = any(re.search(rf"\b{re.escape(term)}\b", chunk_lower) for term in drug_terms)
            has_cue = any(
                re.search(rf"\b{re.escape(cue.lower())}\b", chunk_lower) for cue in required_cues
            )
            if has_drug and has_cue:
                return (
                    True,
                    f"Supported: drug '{step.drug_id}' and '{step.action_type.value}' cue "
                    f"verified in chunk '{chunk.chunk_id}'",
                )

        has_drug_any = any(
            any(
                re.search(rf"\b{re.escape(term)}\b", _normalize_whitespace(c.text).lower())
                for term in drug_terms
            )
            for c in cited_chunks
        )
        if not has_drug_any:
            return (
                False,
                f"Citation support check failed: cited chunk(s) do not mention drug "
                f"'{step.drug_id}' or its verified aliases",
            )
        return (
            False,
            f"Citation support check failed: cited chunk(s) lack required "
            f"'{step.action_type.value}' action cue for drug '{step.drug_id}'",
        )

    return (
        True,
        f"Supported: verbatim span and lexical overlap verified in chunk "
        f"'{cited_chunks[0].chunk_id}'",
    )
