"""Citation verification module for clinical protocol groundedness.

Safety Property (RAG-02, FG-01, FG-16, Rules R1, R2, R3, Section 10):
1. chunk_id must match a verified chunk from the current retrieval report.
2. Parent-only chunk citations are rejected when child decision nodes exist for that document.
3. quoted_span must be an exact verbatim whitespace-normalized substring of the chunk.
4. For IF/THEN decision nodes, quoted_span must cover at least min_then_coverage of the THEN
   action clause content tokens (THEN_CLAUSE_COVERAGE).
5. Enforces stopword-filtered content-token overlap between narrative instruction and cited span.
6. Administer/withhold steps require clause-scoped (action, drug_id) binding (with negation
   polarity flip and fail-closed rejection of unparsed drug clauses).
7. Non-drug steps (diagnostic, monitor, maneuver) require clinical action-verb binding in the
   cited THEN clause.
8. Failures result in CITATION_UNVERIFIED status.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from triagerag.contracts.enums import ActionType
from triagerag.normalize.clause_parser import (
    ActionCuesConfig,
    content_tokens,
    extract_then_else_text,
    has_if_then_structure,
    load_action_cues,
    load_default_drug_term_map,
    parse_clause_drug_actions,
)

if TYPE_CHECKING:
    from triagerag.contracts.schemas import PlanStepDraft, RetrievedChunk, SpanCitation
    from triagerag.engine.registry import ClinicalRegistry

__all__ = [
    "ActionCuesConfig",
    "compute_lexical_overlap",
    "load_action_cues",
    "verify_citation",
    "verify_step_support",
]


def _normalize_whitespace(text: str) -> str:
    """Normalize repeated whitespace, tabs, and newlines to single spaces."""
    return " ".join(text.split()).strip()


def compute_lexical_overlap(
    instruction: str,
    quoted_span: str,
    *,
    stopwords: set[str] | None = None,
) -> float:
    """Compute stopword-filtered content-token Jaccard overlap between instruction and span."""
    if stopwords is None:
        cfg = load_action_cues()
        stop_set = {w.lower() for w in cfg.stopwords}
    else:
        stop_set = stopwords

    inst_tokens = content_tokens(instruction, stop_set)
    span_tokens = content_tokens(quoted_span, stop_set)

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
    min_then_coverage: float | None = None,
) -> tuple[bool, float, str | None]:
    """Verify that a step citation is grounded in retrieved chunks.

    Returns:
        (is_verified, lexical_overlap_score, failure_reason)
    """
    cfg = load_action_cues()
    stop_set = {w.lower() for w in cfg.stopwords}

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
        if not has_child_for_doc:
            try:
                from triagerag.config import get_data_dir
                from triagerag.rag.ingest import ingest_protocols

                all_corpus_chunks = ingest_protocols(get_data_dir())
                has_child_for_doc = any(
                    c.doc_id == matched_chunk.doc_id
                    and (c.parent_id is not None or "_NODE_" in c.chunk_id)
                    for c in all_corpus_chunks
                )
            except Exception:
                pass

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

    if norm_span not in norm_chunk_text:
        msg = (
            f"Quoted span '{citation.quoted_span[:30]}...' is not a verbatim "
            f"substring of chunk {citation.chunk_id}"
        )
        return False, 0.0, msg

    # 5. THEN-clause span coverage gate (FG-16) for IF/THEN decision nodes
    if has_if_then_structure(matched_chunk.text):
        then_text = extract_then_else_text(matched_chunk.text)
        then_toks = content_tokens(then_text, stop_set)
        span_toks = content_tokens(citation.quoted_span, stop_set)
        if then_toks:
            coverage = len(span_toks & then_toks) / len(then_toks)
            eff_cov = min_then_coverage if min_then_coverage is not None else cfg.min_then_coverage
            if coverage < eff_cov:
                return (
                    False,
                    0.0,
                    f"THEN_CLAUSE_COVERAGE: Quoted span covers {coverage:.2f} of THEN clause "
                    f"(< {eff_cov:.2f} minimum)",
                )

    # 6. Compute stopword-filtered content overlap and enforce minimum overlap gate (RAG-02, FG-16)
    overlap = compute_lexical_overlap(
        narrative_instruction, citation.quoted_span, stopwords=stop_set
    )
    eff_min_overlap = min_overlap if min_overlap is not None else cfg.min_overlap_threshold
    if overlap < eff_min_overlap:
        return (
            False,
            overlap,
            f"Citation lexical overlap {overlap:.4f} is below minimum threshold "
            f"{eff_min_overlap:.4f}",
        )

    return True, overlap, None


def _build_registry_drug_term_map(
    registry: ClinicalRegistry,
    data_dir: Path | None = None,
) -> dict[str, set[str]]:
    """Combine registry formulary + aliases with default drug term lexicon."""
    term_map = load_default_drug_term_map(data_dir)
    for drug_id in registry.formulary_drugs:
        did = drug_id.lower()
        term_map.setdefault(did, {did, did.replace("_", " ")})
    for alias_name, alias_entry in registry.aliases.items():
        for ing in alias_entry.ingredient_ids:
            did = ing.lower()
            term_map.setdefault(did, {did, did.replace("_", " ")}).add(alias_name.lower())
    return term_map


def verify_step_support(
    step: PlanStepDraft,
    cited_chunks: list[RetrievedChunk],
    registry: ClinicalRegistry,
    *,
    data_dir: Path | None = None,
) -> tuple[bool, str]:
    """Verify deterministic clause-scoped drug and action-cue support in cited chunks.

    Prevents 'citation laundering' where a step proposes administering/withholding a drug
    while citing an unrelated chunk, a mixed-polarity clause for a different drug, a negated
    cue, or an unparsed clause.
    """
    if not cited_chunks:
        return False, "No verified cited chunks available for step support verification"

    cfg = load_action_cues(data_dir)
    drug_term_map = _build_registry_drug_term_map(registry, data_dir)

    if step.action_type in (ActionType.administer, ActionType.withhold):
        if not step.drug_id:
            return (
                False,
                f"MISSING_DRUG_ID: {step.action_type.value} step missing mandatory drug_id "
                "(fail closed)",
            )
        drug_id_lower = step.drug_id.lower()
        saw_unparsed = False
        saw_opposite_polarity: str | None = None

        for chunk in cited_chunks:
            if chunk.drug_actions:
                bound_actions = chunk.drug_actions
            else:
                bound_actions = parse_clause_drug_actions(
                    chunk.text,
                    drug_term_map=drug_term_map,
                    cues_cfg=cfg,
                    data_dir=data_dir,
                )

            matching_for_drug = [da for da in bound_actions if da.drug_id.lower() == drug_id_lower]
            if not matching_for_drug:
                continue

            if any(da.action == "unparsed" for da in matching_for_drug):
                saw_unparsed = True
                continue

            desired = step.action_type.value
            if all(da.action == desired for da in matching_for_drug):
                return (
                    True,
                    f"Supported: clause-bound ({desired}, '{step.drug_id}') "
                    f"verified in chunk '{chunk.chunk_id}'",
                )

            for da in matching_for_drug:
                if da.action != desired:
                    saw_opposite_polarity = da.action

        if saw_unparsed:
            return (
                False,
                f"UNPARSED_DRUG_CLAUSE: cited clause mentions drug '{step.drug_id}' "
                f"without a bindable action cue (fail closed)",
            )

        if saw_opposite_polarity is not None:
            return (
                False,
                f"ACTION_POLARITY_MISMATCH: cited chunk binds drug '{step.drug_id}' to "
                f"'{saw_opposite_polarity}', not '{step.action_type.value}'",
            )

        return (
            False,
            f"DRUG_NOT_IN_CITED_CHUNK: cited chunk(s) do not mention drug "
            f"'{step.drug_id}' or its verified aliases",
        )

    # Non-drug steps (diagnostic, monitor, maneuver) require clinical action-verb
    # binding (FG-16, N2)
    inst_lower = _normalize_whitespace(step.narrative_instruction).lower()
    action_cues_lower = [c.lower() for c in cfg.non_drug_action_cues]
    saw_any_chunk_action_verbs = False

    for chunk in cited_chunks:
        then_lower = _normalize_whitespace(extract_then_else_text(chunk.text)).lower()
        chunk_action_verbs = [
            cue for cue in action_cues_lower if re.search(rf"\b{re.escape(cue)}\b", then_lower)
        ]
        if not chunk_action_verbs:
            # N2: Missing binding evidence in THEN clause cannot support the action
            continue

        saw_any_chunk_action_verbs = True
        inst_action_verbs = [
            cue for cue in action_cues_lower if re.search(rf"\b{re.escape(cue)}\b", inst_lower)
        ]
        # Match either identical action cue or shared 5-char verb root (e.g. monitor / monitoring)
        has_bound_verb = any(
            iv == cv or (len(iv) >= 5 and len(cv) >= 5 and iv[:5] == cv[:5])
            for iv in inst_action_verbs
            for cv in chunk_action_verbs
        )
        if has_bound_verb:
            return (
                True,
                f"Supported: non-drug action verb bound in chunk '{chunk.chunk_id}'",
            )

    if not saw_any_chunk_action_verbs:
        return (
            False,
            "NON_DRUG_NO_ACTION_VERBS: cited chunk(s) THEN clause contains no verifiable "
            "action verbs (fail closed)",
        )

    return (
        False,
        "NON_DRUG_ACTION_MISMATCH: narrative instruction lacks bound clinical action verb "
        "matching the cited THEN clause",
    )
