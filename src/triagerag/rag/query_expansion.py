"""Controlled Query Expansion from Structured Patient Predicates (T7.1 / AUB-EXP-01).

Safety Properties (Rules R1, R2, R3, R7, R12):
1. Query expansion is purely deterministic and traceable to satisfied patient predicates.
2. chief_complaint_untrusted is NEVER included in expansion.
3. Unknown or indeterminate patient predicates are NEVER expanded.
4. Every expansion term carries explicit predicate origin provenance.
5. Baseline BM25, predicate-aware BM25, and controlled expansion remain separately selectable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from triagerag.config import get_data_dir
from triagerag.contracts.schemas import Provenance
from triagerag.normalize.yaml_loader import load_yaml_decimal
from triagerag.rag.predicates import PredicateEvalResult, evaluate_patient_predicates

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient
    from triagerag.rag.retrieve import RetrievalContext


class ExpansionTermEntry(BaseModel):
    terms: list[str]


class QueryExpansionConfig(BaseModel):
    version: str
    source_status: str
    provenance: Provenance
    expansions: dict[str, ExpansionTermEntry]


class QueryExpansionResult(BaseModel):
    """Traceable result of controlled query expansion."""

    original_query: str
    expanded_query: str
    mode: Literal["baseline_bm25", "predicate_aware_bm25", "controlled_expansion"]
    expansion_terms: list[str] = Field(default_factory=list)
    predicate_origins: dict[str, list[str]] = Field(default_factory=dict)
    unknown_predicates_skipped: list[str] = Field(default_factory=list)
    unconfirmed_predicates_skipped: list[str] = Field(default_factory=list)


@lru_cache(maxsize=16)
def _load_expansion_config_cached(config_path_str: str) -> QueryExpansionConfig:
    p = Path(config_path_str)
    if not p.exists():
        raise FileNotFoundError(f"Controlled query expansion config not found at: {p}")
    raw = load_yaml_decimal(p)
    return QueryExpansionConfig.model_validate(raw)


def load_query_expansion_config(data_dir: Path | None = None) -> QueryExpansionConfig:
    dd = data_dir if data_dir is not None else get_data_dir()
    path = dd / "retrieval" / "expansion_terms.yaml"
    return _load_expansion_config_cached(str(path.resolve()))


def clear_query_expansion_cache() -> None:
    _load_expansion_config_cached.cache_clear()


def build_expanded_query(
    patient: Patient,
    context: RetrievalContext,
    base_query: str,
    mode: Literal[
        "baseline_bm25", "predicate_aware_bm25", "controlled_expansion"
    ] = "predicate_aware_bm25",
    expansion_config: QueryExpansionConfig | None = None,
) -> QueryExpansionResult:
    """Build controlled query expansion while preserving deterministic ordering and provenance."""
    if mode == "baseline_bm25":
        return QueryExpansionResult(
            original_query=base_query,
            expanded_query=base_query,
            mode=mode,
            expansion_terms=[],
            predicate_origins={},
            unknown_predicates_skipped=[],
            unconfirmed_predicates_skipped=[],
        )

    # In predicate_aware_bm25, base_query already contains the standard T2.3 cues.
    if mode == "predicate_aware_bm25":
        return QueryExpansionResult(
            original_query=base_query,
            expanded_query=base_query,
            mode=mode,
            expansion_terms=[],
            predicate_origins={},
            unknown_predicates_skipped=[],
            unconfirmed_predicates_skipped=[],
        )

    # mode == "controlled_expansion"
    cfg = (
        expansion_config
        if expansion_config is not None
        else load_query_expansion_config(context.data_dir)
    )
    predicate_evals = evaluate_patient_predicates(patient, context.predicates.predicates)

    unknown_skipped: list[str] = []
    unconfirmed_skipped: list[str] = []
    predicate_origins: dict[str, list[str]] = {}
    new_terms: list[str] = []

    # Sort predicate keys for deterministic iteration
    for pred_id in sorted(predicate_evals.keys()):
        res = predicate_evals[pred_id]
        if res == PredicateEvalResult.UNKNOWN:
            unknown_skipped.append(pred_id)
            continue
        if res != PredicateEvalResult.SATISFIED:
            unconfirmed_skipped.append(pred_id)
            continue

        # If satisfied and has controlled expansion vocabulary
        if pred_id in cfg.expansions:
            entry = cfg.expansions[pred_id]
            pred_terms: list[str] = []
            for t in entry.terms:
                clean_term = t.strip().lower()
                if clean_term and clean_term not in pred_terms:
                    pred_terms.append(clean_term)
                    new_terms.append(clean_term)
            if pred_terms:
                predicate_origins[pred_id] = pred_terms

    # Merge base_query with expansion terms, deduplicating while preserving order
    base_tokens = [tok for tok in base_query.split() if tok]
    seen_tokens: set[str] = set(base_tokens)
    deduped_expansions: list[str] = []

    for t in new_terms:
        # If multi-word or single word
        for sub_tok in t.split():
            if sub_tok not in seen_tokens:
                seen_tokens.add(sub_tok)
                deduped_expansions.append(sub_tok)

    all_tokens = base_tokens + deduped_expansions
    expanded_query_str = " ".join(all_tokens).strip()

    return QueryExpansionResult(
        original_query=base_query,
        expanded_query=expanded_query_str,
        mode="controlled_expansion",
        expansion_terms=deduped_expansions,
        predicate_origins=predicate_origins,
        unknown_predicates_skipped=unknown_skipped,
        unconfirmed_predicates_skipped=unconfirmed_skipped,
    )
