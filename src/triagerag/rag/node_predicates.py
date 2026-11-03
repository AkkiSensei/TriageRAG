"""Structured protocol decision node predicate applicability metadata.

Safety Properties (Rule R3, D2, AUB Task T2.2):
1. Every active IF/THEN decision node declares its predicate requirements, contraindications,
   or an explicit always_applicable designation.
2. Predicates are retrieval ranking signals ONLY and are NOT clinical approval conditions.
3. Every referenced predicate must exist in the structured predicate vocabulary.
4. Node declarations are validated and attached during protocol ingestion without altering
   verbatim protocol text or violating the line-based round-trip invariant.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from triagerag.config import get_data_dir
from triagerag.contracts.enums import SourceStatus
from triagerag.contracts.schemas import Provenance
from triagerag.normalize.yaml_loader import load_yaml_decimal


class NodePredicateDeclaration(BaseModel):
    """Declared predicate applicability conditions for an individual IF/THEN protocol node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    requires_predicates: tuple[str, ...] = Field(default_factory=tuple)
    contraindicated_by: tuple[str, ...] = Field(default_factory=tuple)
    always_applicable: bool = False
    predicate_review_required: bool = False

    @model_validator(mode="after")
    def validate_applicability_semantics(self) -> NodePredicateDeclaration:
        if not self.always_applicable and not self.requires_predicates:
            raise ValueError(
                f"Node '{self.chunk_id}' must declare requires_predicates or always_applicable=True"
            )
        return self


class NodePredicatesConfig(BaseModel):
    """Sidecar mapping of chunk_id to NodePredicateDeclaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "1.0.0"
    source_status: SourceStatus = SourceStatus.SYNTHETIC_AUTHORED
    provenance: Provenance
    nodes: dict[str, NodePredicateDeclaration] = Field(default_factory=dict)


@lru_cache
def load_node_predicates_config(data_dir: Path | None = None) -> NodePredicatesConfig:
    """Load and validate node predicate declarations from data/retrieval/node_predicates.yaml."""
    target_dir = data_dir if data_dir is not None else get_data_dir()
    path = target_dir / "retrieval" / "node_predicates.yaml"
    if not path.exists():
        path = get_data_dir() / "retrieval" / "node_predicates.yaml"
    raw_data: Any = load_yaml_decimal(path)

    # Convert nodes dict entries into NodePredicateDeclaration instances
    nodes_dict: dict[str, Any] = raw_data.get("nodes", {})
    parsed_nodes: dict[str, NodePredicateDeclaration] = {}
    for chunk_id, entry in nodes_dict.items():
        if isinstance(entry, dict):
            entry_copy = dict(entry)
            entry_copy["chunk_id"] = chunk_id
            req = entry_copy.get("requires_predicates", [])
            contra = entry_copy.get("contraindicated_by", [])
            entry_copy["requires_predicates"] = tuple(req)
            entry_copy["contraindicated_by"] = tuple(contra)
            parsed_nodes[chunk_id] = NodePredicateDeclaration.model_validate(entry_copy)

    # Also index declarations by canonical content-addressed ID via alias map (AUB-COR-02)
    try:
        from triagerag.rag.aliases import load_node_aliases

        aliases = load_node_aliases(target_dir)
        for legacy_id, content_id in aliases.items():
            if legacy_id in parsed_nodes and content_id not in parsed_nodes:
                decl = parsed_nodes[legacy_id]
                parsed_nodes[content_id] = decl.model_copy(update={"chunk_id": content_id})
    except Exception:
        pass

    raw_data_copy = dict(raw_data)
    raw_data_copy["nodes"] = parsed_nodes
    return NodePredicatesConfig.model_validate(raw_data_copy)
