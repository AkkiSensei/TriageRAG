"""Protocol retrieval orchestrator.

Safety Properties (Rules R2, R3, R7, R8, Section 8, RAG-01, RAG-03, RAG-12):
1. Query constructed strictly from structured patient fields:
   canonical suspected_syndrome + per-population vitals-derived flags.
2. chief_complaint_untrusted is never used in query construction.
3. Vitals flag thresholds are loaded per population from data/retrieval/vitals_flags.yaml
   with Provenance; NEEDS_SOURCE rules emit nothing and never fall back to adult values.
4. Known suspected_syndrome enforces a hard metadata filter; unknown syndrome abstains
   immediately with AbstainCode.UNKNOWN_SYNDROME.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from triagerag.config import get_data_dir
from triagerag.contracts.enums import AbstainCode, RuleStatus
from triagerag.contracts.schemas import Provenance, RetrievalReport, RetrievedChunk
from triagerag.normalize.yaml_loader import load_yaml_decimal
from triagerag.rag.abstain import (
    DEFAULT_MIN_RETRIEVAL_THRESHOLD,
    evaluate_abstention_with_code,
    load_retrieval_config,
)
from triagerag.rag.ingest import load_corpus_manifest

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient
    from triagerag.rag.index import BM25ClinicalIndex

_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")


class VitalsFlagRule(BaseModel):
    """Per-population physiological flag rule with Provenance (RAG-03)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    flag: str
    field: str
    operator: Literal["<", "<=", ">", ">=", "in"]
    threshold: Decimal | None = None
    allowed_values: list[str] = Field(default_factory=list)
    status: RuleStatus
    provenance: Provenance


class VitalsFlagsConfig(BaseModel):
    """Per-population vitals flag configuration loaded from data/retrieval/vitals_flags.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    populations: dict[str, list[VitalsFlagRule]]


@lru_cache
def load_vitals_flags_config(data_dir: Path | None = None) -> VitalsFlagsConfig:
    """Load and validate per-population vitals flag rules using Decimal YAML loader."""
    target_dir = data_dir or get_data_dir()
    flags_path = target_dir / "retrieval" / "vitals_flags.yaml"
    if not flags_path.exists():
        flags_path = get_data_dir() / "retrieval" / "vitals_flags.yaml"
    raw_data: Any = load_yaml_decimal(flags_path)
    return VitalsFlagsConfig.model_validate(raw_data)


def normalize_syndrome(
    raw_syndrome: str | None,
    data_dir: Path | None = None,
) -> str | None:
    """Normalize a syndrome string and resolve aliases against the corpus manifest."""
    if raw_syndrome is None:
        return None
    cleaned = _NON_ALNUM_RE.sub("_", raw_syndrome.strip().lower()).strip("_")
    if not cleaned:
        return None
    manifest = load_corpus_manifest(data_dir or get_data_dir())
    return manifest.syndrome_aliases.get(cleaned, cleaned)


def derive_vitals_flags(
    patient: Patient,
    data_dir: Path | None = None,
) -> list[str]:
    """Derive standardized categorical physiological flags from measured vitals.

    Safety (RAG-03, Rules R2, R3):
    - Uses only rules for the patient's own population category (never falls back to adult).
    - Rules with status == NEEDS_SOURCE or threshold is None fail closed and emit nothing.
    - Vitals that are unknown or missing never trigger spurious flags.
    """
    cfg = load_vitals_flags_config(data_dir)
    pop = str(patient.age.population_category).lower().strip()
    pop_rules = cfg.populations.get(pop, [])

    flags: list[str] = []
    v = patient.vitals

    for rule in pop_rules:
        if rule.status != RuleStatus.ACTIVE:
            continue

        measured_field = getattr(v, rule.field, None)
        if measured_field is None or measured_field.value is None:
            continue

        raw_val = measured_field.value
        triggered = False

        if rule.operator == "in":
            val_str = str(raw_val.value if hasattr(raw_val, "value") else raw_val)
            if val_str in rule.allowed_values:
                triggered = True
        else:
            if rule.threshold is None:
                continue
            dec_val = Decimal(str(raw_val))
            triggered = (
                (rule.operator == "<" and dec_val < rule.threshold)
                or (rule.operator == "<=" and dec_val <= rule.threshold)
                or (rule.operator == ">" and dec_val > rule.threshold)
                or (rule.operator == ">=" and dec_val >= rule.threshold)
            )

        if triggered and rule.flag not in flags:
            flags.append(rule.flag)

    return flags


def build_retrieval_query(patient: Patient) -> tuple[str, list[str]]:
    """Build a search query from structured clinical attributes.

    Rule R7: chief_complaint_untrusted is explicitly forbidden from query construction.
    RAG-07: No arbitrary ×3 token repetition; syndrome is enforced as a hard metadata filter.
    """
    flags = derive_vitals_flags(patient)
    query_parts: list[str] = []

    norm_syndrome = normalize_syndrome(patient.suspected_syndrome)
    if norm_syndrome:
        query_parts.append(norm_syndrome)

    query_parts.extend(flags)
    query_string = " ".join(query_parts).strip()
    return query_string, flags


def retrieve_protocol_chunks(
    patient: Patient,
    index: BM25ClinicalIndex,
    threshold: float = DEFAULT_MIN_RETRIEVAL_THRESHOLD,
    top_k: int | None = None,
) -> RetrievalReport:
    """Retrieve verified protocol chunks matching patient population and controlled syndrome."""
    cfg = load_retrieval_config()
    eff_top_k = top_k if top_k is not None else cfg.top_k

    pop = str(patient.age.population_category).lower().strip()
    query_str, _flags = build_retrieval_query(patient)
    norm_syndrome = normalize_syndrome(patient.suspected_syndrome)

    filters: dict[str, str] = {"population": pop}
    if norm_syndrome:
        filters["syndrome"] = norm_syndrome

    corpus_hash = getattr(index, "corpus_hash", "")
    index_version = getattr(index, "index_version", "1.0.0")

    if not index.index_by_population:
        return RetrievalReport(
            chunks=[],
            backend=index.backend,
            abstained=True,
            abstain_code=AbstainCode.INDEX_UNAVAILABLE,
            reason="No verified protocol chunks available in empty index",
            query=query_str,
            filters=filters,
            corpus_hash=corpus_hash,
            index_version=index_version,
            config_hash=cfg.config_hash,
        )

    pop_available = pop in index.index_by_population
    if not pop_available:
        return RetrievalReport(
            chunks=[],
            backend=index.backend,
            abstained=True,
            abstain_code=AbstainCode.NO_POPULATION_COVERAGE,
            reason=f"No verified protocol chunks available for population '{pop}'",
            query=query_str,
            filters=filters,
            corpus_hash=corpus_hash,
            index_version=index_version,
            config_hash=cfg.config_hash,
        )

    # RAG-01: When suspected_syndrome is provided, validate against controlled vocabulary
    if norm_syndrome is not None:
        manifest = load_corpus_manifest(get_data_dir())
        known_global = set(manifest.controlled_syndromes) | index.known_syndromes()
        if norm_syndrome not in known_global:
            return RetrievalReport(
                chunks=[],
                backend=index.backend,
                abstained=True,
                abstain_code=AbstainCode.UNKNOWN_SYNDROME,
                reason=(
                    f"Suspected syndrome '{patient.suspected_syndrome}' is not in controlled "
                    f"protocol vocabulary (abstained)"
                ),
                query=query_str,
                filters=filters,
                corpus_hash=corpus_hash,
                index_version=index_version,
                config_hash=cfg.config_hash,
            )

        known_in_pop = index.known_syndromes(population=pop)
        if norm_syndrome not in known_in_pop:
            return RetrievalReport(
                chunks=[],
                backend=index.backend,
                abstained=True,
                abstain_code=AbstainCode.NO_POPULATION_COVERAGE,
                reason=(f"No protocol chunks for syndrome '{norm_syndrome}' in population '{pop}'"),
                query=query_str,
                filters=filters,
                corpus_hash=corpus_hash,
                index_version=index_version,
                config_hash=cfg.config_hash,
            )

    if not query_str:
        return RetrievalReport(
            chunks=[],
            backend=index.backend,
            abstained=True,
            abstain_code=AbstainCode.EMPTY_QUERY,
            reason="Empty clinical query: no suspected syndrome or abnormal vitals flags",
            query=query_str,
            filters=filters,
            corpus_hash=corpus_hash,
            index_version=index_version,
            config_hash=cfg.config_hash,
        )

    scored_chunks = index.search(
        query=query_str,
        population=pop,
        top_k=eff_top_k,
        syndrome=norm_syndrome,
    )

    stage_scores: dict[str, dict[str, float]] = {
        "bm25": {
            chunk.chunk_id: round(float(sc), cfg.score_decimal_places)
            for chunk, sc in scored_chunks
        }
    }

    abstained, abstain_code, reason = evaluate_abstention_with_code(
        scored_chunks=scored_chunks,
        population=pop,
        population_available=pop_available,
        threshold=threshold,
        syndrome_provided=(norm_syndrome is not None),
    )

    if abstained:
        return RetrievalReport(
            chunks=[],
            backend=index.backend,
            abstained=True,
            abstain_code=abstain_code,
            reason=reason,
            query=query_str,
            filters=filters,
            stage_scores=stage_scores,
            corpus_hash=corpus_hash,
            index_version=index_version,
            config_hash=cfg.config_hash,
        )

    # When syndrome was inferred from vitals, restrict returned chunks to the winning syndrome
    if norm_syndrome is None and scored_chunks:
        winning_syndrome = scored_chunks[0][0].syndrome
        scored_chunks = [
            (chunk, sc) for chunk, sc in scored_chunks if chunk.syndrome == winning_syndrome
        ]

    retrieved: list[RetrievedChunk] = []
    for chunk, score in scored_chunks:
        norm_score = max(
            Decimal("0.0"),
            Decimal(str(round(float(score), cfg.score_decimal_places))),
        )
        retrieved.append(
            RetrievedChunk(
                doc_id=chunk.doc_id,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
                parent_id=chunk.parent_id,
                text=chunk.text,
                population=chunk.population,
                syndrome=chunk.syndrome,
                score=norm_score,
            )
        )

    return RetrievalReport(
        chunks=retrieved,
        backend=index.backend,
        abstained=False,
        abstain_code=abstain_code,
        reason=reason,
        query=query_str,
        filters=filters,
        stage_scores=stage_scores,
        corpus_hash=corpus_hash,
        index_version=index_version,
        config_hash=cfg.config_hash,
    )
