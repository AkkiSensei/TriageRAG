"""Patient-conditioned retrieval scoring module.

Safety Properties (Rules R2, R3, R12, AUB-RET-01, Task T2.4):
1. Scoring formula: Score = Lexical(query) + λ * predicate_match - μ * predicate_conflict.
2. Predicate scoring is deterministic and inspectable.
3. Unknown patient values yield neither match nor conflict.
4. Deterministic tie-breaking via (-round(score, decimals), chunk_id).
5. Predicate score is a retrieval ranking signal only, never a clinical approval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from triagerag.rag.predicates import PredicateEvalResult

if TYPE_CHECKING:
    from triagerag.rag.chunking import ProtocolChunk


def calculate_node_predicate_score(
    *,
    requires_predicates: tuple[str, ...],
    contraindicated_by: tuple[str, ...],
    always_applicable: bool,
    patient_evals: dict[str, PredicateEvalResult],
    lexical_score: float,
    match_weight: float = 1.0,
    conflict_weight: float = 2.0,
) -> tuple[float, int, int]:
    """Calculate patient-conditioned score for a candidate protocol node.

    Requirements:
    1. A predicate contributes at most once.
    2. Unknown patient values yield neither match nor conflict.
    3. Conflicting predicates apply when requires_predicates is NOT_SATISFIED
       or contraindicated_by is SATISFIED.
    4. Deterministic formula: Lexical + match_weight * match - conflict_weight * conflict.
    """
    match_count = 0
    conflict_count = 0

    # 1. Evaluate required predicates
    for pred_id in requires_predicates:
        status = patient_evals.get(pred_id, PredicateEvalResult.UNKNOWN)
        if status == PredicateEvalResult.SATISFIED:
            match_count += 1
        elif status == PredicateEvalResult.NOT_SATISFIED:
            conflict_count += 1
        # UNKNOWN status does not alter match or conflict counts

    # 2. Evaluate contraindicating predicates
    for pred_id in contraindicated_by:
        status = patient_evals.get(pred_id, PredicateEvalResult.UNKNOWN)
        if status == PredicateEvalResult.SATISFIED:
            conflict_count += 1
        # NOT_SATISFIED or UNKNOWN contraindication does not alter conflict count

    final_score = (
        float(lexical_score)
        + (match_weight * match_count)
        - (conflict_weight * conflict_count)
    )
    return final_score, match_count, conflict_count


def rescore_chunks_with_patient_predicates(
    scored_chunks: list[tuple[ProtocolChunk, float]],
    patient_evals: dict[str, PredicateEvalResult],
    *,
    match_weight: float = 1.0,
    conflict_weight: float = 2.0,
    score_decimal_places: int = 4,
) -> tuple[list[tuple[ProtocolChunk, float]], dict[str, dict[str, float]]]:
    """Rescore candidate chunks with patient applicability predicates.

    Returns deterministic ranking and inspectable diagnostic scores per stage.
    """
    rescored: list[tuple[ProtocolChunk, float, int, int]] = []
    lexical_stage: dict[str, float] = {}
    match_stage: dict[str, float] = {}
    conflict_stage: dict[str, float] = {}
    patient_conditioned_stage: dict[str, float] = {}

    for chunk, lex_score in scored_chunks:
        final_score, match_count, conflict_count = calculate_node_predicate_score(
            requires_predicates=chunk.requires_predicates,
            contraindicated_by=chunk.contraindicated_by,
            always_applicable=chunk.always_applicable,
            patient_evals=patient_evals,
            lexical_score=float(lex_score),
            match_weight=match_weight,
            conflict_weight=conflict_weight,
        )
        rounded_final = round(final_score, score_decimal_places)
        rounded_lex = round(float(lex_score), score_decimal_places)

        lexical_stage[chunk.chunk_id] = rounded_lex
        match_stage[chunk.chunk_id] = float(match_count)
        conflict_stage[chunk.chunk_id] = float(conflict_count)
        patient_conditioned_stage[chunk.chunk_id] = rounded_final

        rescored.append((chunk, final_score, match_count, conflict_count))

    # Deterministic tie-breaking: higher score first, tie-break by chunk_id ascending
    rescored.sort(
        key=lambda item: (
            -round(item[1], score_decimal_places),
            item[0].chunk_id,
        )
    )

    stage_scores = {
        "bm25": lexical_stage,
        "predicate_match": match_stage,
        "predicate_conflict": conflict_stage,
        "patient_conditioned": patient_conditioned_stage,
    }

    output_chunks = [(item[0], item[1]) for item in rescored]
    return output_chunks, stage_scores
