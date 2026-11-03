"""Synthetic retrieval cue mapping connecting patient predicates to protocol vocabulary.

Safety Properties (Rule R3, D2, HD-16, AUB Task T2.3):
1. Every cue maps a structured predicate from predicates.yaml to protocol terms.
2. Cues are retrieval search vocabulary ONLY and are NOT clinical rules or facts.
3. Every cue mapping carries source_status: SYNTHETIC_AUTHORED.
4. Cue expansion is deterministic and deduplicated.
5. Clinical rule engines (triagerag.engine) must never consume or import this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from triagerag.config import get_data_dir
from triagerag.contracts.enums import SourceStatus
from triagerag.contracts.schemas import Provenance
from triagerag.normalize.yaml_loader import load_yaml_decimal


class PredicateCueMapping(BaseModel):
    """Vocabulary mapping for a single predicate ID to protocol language terms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predicate_id: str
    terms: tuple[str, ...] = Field(default_factory=tuple)
    syndrome_cue: bool = False

    @model_validator(mode="before")
    @classmethod
    def deduplicate_terms(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_terms = data.get("terms", ())
            if isinstance(raw_terms, (list, tuple)):
                seen: set[str] = set()
                deduped: list[str] = []
                for term in raw_terms:
                    cleaned = str(term).strip()
                    if cleaned and cleaned not in seen:
                        seen.add(cleaned)
                        deduped.append(cleaned)
                data["terms"] = tuple(deduped)
        return data


class RetrievalCuesConfig(BaseModel):
    """Synthetic retrieval cue bundle loaded from data/retrieval/cues.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "1.0.0"
    source_status: SourceStatus = SourceStatus.SYNTHETIC_AUTHORED
    provenance: Provenance
    cues: dict[str, PredicateCueMapping] = Field(default_factory=dict)


@lru_cache
def load_retrieval_cues(data_dir: Path | None = None) -> RetrievalCuesConfig:
    """Load and validate synthetic retrieval cues from data/retrieval/cues.yaml."""
    target_dir = data_dir if data_dir is not None else get_data_dir()
    path = target_dir / "retrieval" / "cues.yaml"
    if not path.exists():
        path = get_data_dir() / "retrieval" / "cues.yaml"
    raw_data: Any = load_yaml_decimal(path)

    cues_dict: dict[str, Any] = raw_data.get("cues", {})
    parsed_cues: dict[str, PredicateCueMapping] = {}
    for pred_id, entry in cues_dict.items():
        if isinstance(entry, dict):
            entry_copy = dict(entry)
            entry_copy["predicate_id"] = pred_id
            parsed_cues[pred_id] = PredicateCueMapping.model_validate(entry_copy)

    raw_data_copy = dict(raw_data)
    raw_data_copy["cues"] = parsed_cues
    return RetrievalCuesConfig.model_validate(raw_data_copy)


def expand_predicates_to_cues(
    satisfied_predicate_ids: Iterable[str],
    cues_config: RetrievalCuesConfig,
    *,
    syndrome_cues_only: bool = False,
) -> list[str]:
    """Deterministically expand satisfied predicates into deduplicated protocol vocabulary.

    If syndrome_cues_only is True, filters to cues that indicate acute clinical
    presentation findings for vitals-only syndrome inference (T2.7).
    """
    seen: set[str] = set()
    expanded_terms: list[str] = []

    for pred_id in sorted(satisfied_predicate_ids):
        mapping = cues_config.cues.get(pred_id)
        if mapping is None:
            continue
        if syndrome_cues_only and not mapping.syndrome_cue:
            continue
        for term in mapping.terms:
            if term not in seen:
                seen.add(term)
                expanded_terms.append(term)

    return expanded_terms
