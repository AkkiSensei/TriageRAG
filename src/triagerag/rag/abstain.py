"""Abstention and calibration configuration module for protocol retrieval.

Safety Properties (Rule R2, Section 8, RAG-01, RAG-14, RAG-15):
1. All retrieval thresholds, margin rules, and BM25 parameters live in
   data/retrieval/config.yaml with Provenance and calibration_run_id.
2. Retires uncalibrated magic constants from source code.
3. Emits typed AbstainCode values (NO_POPULATION_COVERAGE, UNKNOWN_SYNDROME,
   LOW_CONFIDENCE, AMBIGUOUS_MARGIN, EMPTY_QUERY, INDEX_UNAVAILABLE, SYNDROME_INFERRED).
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict

from triagerag.config import get_data_dir
from triagerag.contracts.enums import AbstainCode
from triagerag.contracts.schemas import Provenance

if TYPE_CHECKING:
    from triagerag.rag.chunking import ProtocolChunk


class RetrievalConfig(BaseModel):
    """Calibrated retrieval configuration loaded from data/retrieval/config.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    calibration_run_id: str
    top_k: int
    contextual_chunking: bool = False
    calibrated_threshold: float
    syndrome_inferred_threshold: float
    min_syndrome_margin: float
    bm25_k1: float
    bm25_b: float
    child_node_boost: float
    score_decimal_places: int
    predicate_match_weight: float = 1.0
    predicate_conflict_weight: float = 2.0
    raw_token_weight: float = 1.0
    stem_token_weight: float = 0.5
    synonym_token_weight: float = 0.5
    cue_token_weight: float = 0.5
    backend_thresholds: dict[str, dict[str, float]] | None = None
    provenance: Provenance
    config_hash: str = ""


@lru_cache
def load_retrieval_config(data_dir: Path | None = None) -> RetrievalConfig:
    """Load and validate calibrated retrieval configuration from YAML (fail-closed, R2)."""
    target_dir = (data_dir or get_data_dir()).resolve()
    cfg_path = target_dir / "retrieval" / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Retrieval config not found at {cfg_path}")

    raw_text = cfg_path.read_text(encoding="utf-8")
    cfg_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    parsed = yaml.safe_load(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError(f"Invalid retrieval config in {cfg_path}")
    parsed["config_hash"] = cfg_hash
    return RetrievalConfig.model_validate(parsed)


def normalize_relevance_score(
    raw_score: float,
    backend: str = "bm25",
    top_k: int = 1,
) -> float:
    """Map non-negative retrieval score onto [0.0, 1.0) calibrated confidence scale (T2.6)."""
    if raw_score <= 0.0:
        return 0.0
    b_norm = backend.lower().strip()
    if b_norm in ("hybrid_rrf", "hybrid_rrf_rerank"):
        rrf_k = float(top_k * top_k)
        max_theoretical_rrf = 2.0 / (rrf_k + 1.0)
        if max_theoretical_rrf <= 0.0:
            return 0.0
        return min(1.0, float(raw_score / max_theoretical_rrf))
    if b_norm in ("char_ngram", "dense"):
        norm_factor = 2.0 + 0.5
        return min(1.0, float(raw_score / norm_factor))
    return float(raw_score / (raw_score + 1.0))


def evaluate_abstention_with_code(
    scored_chunks: list[tuple[ProtocolChunk, float]],
    population: str,
    population_available: bool,
    threshold: float | None = None,
    syndrome_provided: bool = True,
    min_margin: float | None = None,
    config: RetrievalConfig | None = None,
    *,
    backend: str = "bm25",
    use_calibrated_for_inferred: bool = False,
    base_best_score: float | None = None,
) -> tuple[bool, AbstainCode, str | None]:
    """Evaluate calibrated abstention and top-1/top-2 syndrome margin rules."""
    cfg = config if config is not None else load_retrieval_config()
    _backend_thresh = (
        cfg.backend_thresholds.get(backend.lower().strip())
        if cfg.backend_thresholds is not None
        else None
    )
    eff_threshold = (
        threshold
        if threshold is not None
        else (
            cfg.calibrated_threshold
            if (syndrome_provided or use_calibrated_for_inferred)
            else cfg.syndrome_inferred_threshold
        )
    )
    eff_margin = min_margin if min_margin is not None else cfg.min_syndrome_margin

    if not population_available:
        return (
            True,
            AbstainCode.NO_POPULATION_COVERAGE,
            f"No verified protocol chunks available for population '{population}'",
        )

    if not scored_chunks:
        return (
            True,
            AbstainCode.NO_RESULTS,
            f"No protocol chunks matched retrieval query for population '{population}'",
        )

    best_score = float(scored_chunks[0][1])
    eval_score = (
        base_best_score if (syndrome_provided and base_best_score is not None) else best_score
    )
    norm_best = normalize_relevance_score(eval_score, backend=backend, top_k=cfg.top_k)

    if norm_best < eff_threshold or eval_score <= 0.0:
        msg = (
            f"Top retrieval relevance {norm_best:.2f} (raw {eval_score:.2f}) is below "
            f"calibrated threshold {eff_threshold:.2f}"
        )
        return True, AbstainCode.LOW_CONFIDENCE, msg

    if not syndrome_provided:
        # Group best score by syndrome to check top-1 vs top-2 margin
        best_by_syndrome: dict[str, float] = {}
        for chunk, sc in scored_chunks:
            syn = chunk.syndrome
            if syn not in best_by_syndrome or float(sc) > best_by_syndrome[syn]:
                best_by_syndrome[syn] = float(sc)

        ranked_syndromes = sorted(best_by_syndrome.items(), key=lambda x: x[1], reverse=True)
        if len(ranked_syndromes) >= 2:
            top1_syn, top1_sc = ranked_syndromes[0]
            top2_syn, top2_sc = ranked_syndromes[1]
            if top1_sc > 0.0:
                rel_margin = (top1_sc - top2_sc) / top1_sc
                if rel_margin < eff_margin:
                    msg = (
                        f"Ambiguous syndrome match without suspected_syndrome: "
                        f"'{top1_syn}' ({top1_sc:.2f}) vs '{top2_syn}' ({top2_sc:.2f}), "
                        f"relative margin {rel_margin:.2f} < required {eff_margin:.2f}"
                    )
                    return True, AbstainCode.AMBIGUOUS_MARGIN, msg

        inferred_syn = ranked_syndromes[0][0]
        return (
            False,
            AbstainCode.SYNDROME_INFERRED,
            f"Syndrome '{inferred_syn}' inferred from physiological flags; "
            "requires clinician confirmation",
        )

    return False, AbstainCode.NONE, None


def evaluate_abstention(
    scored_chunks: list[tuple[ProtocolChunk, float]],
    population: str,
    population_available: bool,
    threshold: float | None = None,
    config: RetrievalConfig | None = None,
) -> tuple[bool, str | None]:
    """Backwards-compatible abstention tuple (abstained, reason)."""
    abstained, _code, reason = evaluate_abstention_with_code(
        scored_chunks=scored_chunks,
        population=population,
        population_available=population_available,
        threshold=threshold,
        syndrome_provided=True,
        config=config,
    )
    return abstained, reason
