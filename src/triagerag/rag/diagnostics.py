"""Retrieval diagnostics, nearest-miss analysis, and MMR diversity re-ranking.

Safety Properties (Rules R1, R2, R3, R12, AUB T7.6):
1. Nearest-miss diagnostics surface rejected chunks and score margins deterministically.
2. Predicate diagnostics expose matched, conflicting, and unknown predicates explicitly.
3. Inferred-mode MMR balances clinical relevance and inter-document diversity
   using deterministic lexical token Jaccard similarity and stable tie-breaking.
4. Purely offline, zero-network execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from triagerag.rag.predicates import PredicateEvalResult

if TYPE_CHECKING:
    from triagerag.rag.chunking import ProtocolChunk


class PredicateMatchDetail(BaseModel):
    """Diagnostic details of how patient state matched node predicates."""

    predicate_id: str
    status: str  # "SATISFIED", "NOT_SATISFIED", "UNKNOWN"
    role: str  # "REQUIRED", "CONTRAINDICATION"
    clinical_effect: str  # "BOOST", "PENALTY", "NEUTRAL"


class NearestMissDetail(BaseModel):
    """Diagnostic details of a candidate chunk that was not selected."""

    chunk_id: str
    doc_id: str
    section: str
    syndrome: str
    score: float
    rank: int
    delta_to_threshold: float
    rejection_reason: str


class RetrievalDiagnostics(BaseModel):
    """Structured diagnostics for retrieval explanation and audit."""

    inferred_mode: bool = False
    mmr_applied: bool = False
    lambda_param: float = float("0.7")
    nearest_misses: list[NearestMissDetail] = Field(default_factory=list)
    predicate_evaluations: dict[str, list[PredicateMatchDetail]] = Field(default_factory=dict)
    abstention_code: str | None = None
    abstention_reason: str | None = None


def compute_token_jaccard_similarity(text1: str, text2: str) -> float:
    """Deterministic token Jaccard similarity between two chunk texts."""
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return float(intersection) / float(union) if union > 0 else 0.0


def apply_mmr_rerank(
    candidates: list[tuple[ProtocolChunk, float]],
    top_k: int,
    lambda_param: float = float("0.7"),
) -> list[tuple[ProtocolChunk, float]]:
    """Maximum Marginal Relevance (MMR) selection for diversity.

    MMR Score(d) = λ * norm_rel(d) - (1 - λ) * max_{s in Selected} sim(d, s)
    Ties broken deterministically by (-score, chunk_id).
    """
    if not candidates or top_k <= 0:
        return []

    # If candidates fewer than top_k, return sorted candidates
    if len(candidates) <= top_k:
        return sorted(candidates, key=lambda x: (-x[1], x[0].chunk_id))

    # Normalize candidate relevance scores into [0, 1]
    scores = [s for _, s in candidates]
    min_s = min(scores)
    max_s = max(scores)
    score_range = max_s - min_s if max_s > min_s else 1.0

    def norm_rel(raw_score: float) -> float:
        if max_s == min_s:
            return 1.0
        return (raw_score - min_s) / score_range

    selected: list[tuple[ProtocolChunk, float]] = []
    unselected = list(candidates)

    # 1. First item is the top-scoring candidate (deterministic tie-break)
    unselected.sort(key=lambda x: (-x[1], x[0].chunk_id))
    first = unselected.pop(0)
    selected.append(first)

    # 2. Iteratively select next item maximizing MMR score
    while len(selected) < top_k and unselected:
        best_candidate: tuple[ProtocolChunk, float] | None = None
        best_mmr_score = -float("inf")
        best_idx = -1

        for idx, (cand_chunk, cand_raw_score) in enumerate(unselected):
            rel = norm_rel(cand_raw_score)
            max_sim = max(
                compute_token_jaccard_similarity(cand_chunk.text, sel_chunk.text)
                for sel_chunk, _ in selected
            )
            mmr_score = (lambda_param * rel) - ((1.0 - lambda_param) * max_sim)

            # Deterministic tie-breaking: higher MMR, then higher raw score, then chunk_id ascending
            if mmr_score > best_mmr_score or (
                abs(mmr_score - best_mmr_score) < float("1e-9")
                and best_candidate is not None
                and (
                    cand_raw_score > best_candidate[1]
                    or cand_chunk.chunk_id < best_candidate[0].chunk_id
                )
            ):
                best_mmr_score = mmr_score
                best_candidate = (cand_chunk, cand_raw_score)
                best_idx = idx

        if best_candidate is not None and best_idx >= 0:
            selected.append(best_candidate)
            unselected.pop(best_idx)
        else:
            break

    return selected


def calculate_nearest_misses(
    all_scored_candidates: list[tuple[ProtocolChunk, float]],
    selected_chunk_ids: set[str],
    threshold: float,
    max_misses: int = int("5"),
) -> list[NearestMissDetail]:
    """Identify top non-selected candidate chunks and compute distance metrics."""
    nearest_misses: list[NearestMissDetail] = []
    rank = 1

    for chunk, score in all_scored_candidates:
        if chunk.chunk_id not in selected_chunk_ids:
            delta = round(float(score) - float(threshold), int("3"))
            reason = "BELOW_SCORE_THRESHOLD" if delta < 0 else "TOP_K_RANK_CUTOFF"

            nearest_misses.append(
                NearestMissDetail(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    section=chunk.section,
                    syndrome=chunk.syndrome,
                    score=round(float(score), int("3")),
                    rank=rank,
                    delta_to_threshold=delta,
                    rejection_reason=reason,
                )
            )
            if len(nearest_misses) >= max_misses:
                break
        rank += 1

    return nearest_misses


def explain_chunk_predicates(
    chunk: ProtocolChunk,
    patient_evals: dict[str, PredicateEvalResult],
) -> list[PredicateMatchDetail]:
    """Produce inspectable predicate matching breakdown for a candidate chunk."""
    details: list[PredicateMatchDetail] = []

    # Requires predicates
    for pred_id in chunk.requires_predicates:
        status = patient_evals.get(pred_id, PredicateEvalResult.UNKNOWN)
        effect = (
            "BOOST"
            if status == PredicateEvalResult.SATISFIED
            else ("PENALTY" if status == PredicateEvalResult.NOT_SATISFIED else "NEUTRAL")
        )
        details.append(
            PredicateMatchDetail(
                predicate_id=pred_id,
                status=status.value if hasattr(status, "value") else str(status),
                role="REQUIRED",
                clinical_effect=effect,
            )
        )

    # Contraindicated by predicates
    for pred_id in chunk.contraindicated_by:
        status = patient_evals.get(pred_id, PredicateEvalResult.UNKNOWN)
        effect = "PENALTY" if status == PredicateEvalResult.SATISFIED else "NEUTRAL"
        details.append(
            PredicateMatchDetail(
                predicate_id=pred_id,
                status=status.value if hasattr(status, "value") else str(status),
                role="CONTRAINDICATION",
                clinical_effect=effect,
            )
        )

    return details
