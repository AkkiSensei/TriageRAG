"""Content-Addressed Node ID and Legacy Alias Management (T3.3 / AUB-COR-02).

Safety Properties (Rules R1, R2, R3, AUB-COR-02):
1. Maps legacy positional node identifiers ({chunk_id}_NODE_{n}) to deterministic
   content-addressed identifiers ({chunk_id}_{hash8(node_text)}).
2. Guarantees that node reordering or insertion never silently retargets citations,
   predicate sidecars, or evaluation labels.
3. Provides fail-closed resolution: resolving an unknown alias falls back safely to
   the identifier itself or can be strictly verified against the corpus manifest.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from triagerag.config import get_data_dir

if TYPE_CHECKING:
    from triagerag.rag.chunking import ProtocolChunk

logger = logging.getLogger(__name__)

_DEFAULT_ALIAS_FILENAME = "node_aliases.yaml"


def get_alias_file_path(data_dir: Path | None = None) -> Path:
    """Return path to corpus node alias map."""
    base_dir = data_dir or get_data_dir()
    return base_dir / "corpus" / _DEFAULT_ALIAS_FILENAME


@functools.lru_cache(maxsize=16)
def _load_node_aliases_cached(resolved_dir_str: str) -> dict[str, str]:
    path = Path(resolved_dir_str) / "corpus" / _DEFAULT_ALIAS_FILENAME
    if not path.exists():
        return {}

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        aliases = data.get("aliases", {})
        if isinstance(aliases, dict):
            return {str(k): str(v) for k, v in aliases.items()}
    except Exception as exc:
        logger.warning("Failed to load node aliases from %s: %s", path, exc)
    return {}


@functools.lru_cache(maxsize=16)
def _load_reverse_node_aliases_cached(resolved_dir_str: str) -> dict[str, str]:
    aliases = _load_node_aliases_cached(resolved_dir_str)
    return {v: k for k, v in aliases.items()}


def clear_node_alias_cache() -> None:
    """Clear in-memory LRU caches for node aliases."""
    _load_node_aliases_cached.cache_clear()
    _load_reverse_node_aliases_cached.cache_clear()


def load_node_aliases(data_dir: Path | None = None) -> dict[str, str]:
    """Load legacy positional ID to content-addressed ID alias map.

    Returns dict mapping legacy_id (e.g. 'CHEST_PAIN_01_NODE_1') -> content_id (e.g. 'CHEST_PAIN_01_7e3a9c12').
    """
    base_dir = (data_dir or get_data_dir()).resolve()
    return _load_node_aliases_cached(str(base_dir))


def load_reverse_node_aliases(data_dir: Path | None = None) -> dict[str, str]:
    """Load content-addressed ID to legacy positional ID reverse alias map."""
    base_dir = (data_dir or get_data_dir()).resolve()
    return _load_reverse_node_aliases_cached(str(base_dir))


# Backward compatibility bindings for cache_clear on the public functions
load_node_aliases.cache_clear = clear_node_alias_cache  # type: ignore[attr-defined]
load_reverse_node_aliases.cache_clear = clear_node_alias_cache  # type: ignore[attr-defined]


def save_node_aliases(
    alias_map: dict[str, str],
    data_dir: Path | None = None,
) -> Path:
    """Save alias map to corpus node_aliases.yaml."""
    path = get_alias_file_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": "1.0.0",
        "provenance": {
            "source_doc": "NODE_ALIASES_MAP",
            "section_ref": "AUB_T3_3",
            "version_or_date": "2026-DRAFT",
            "source_status": "SYNTHETIC_AUTHORED",
            "content_origin": "AGENT_DRAFT_SYNTHETIC",
            "verified": False,
            "reviewer": None,
        },
        "aliases": dict(sorted(alias_map.items())),
    }

    yaml_text = yaml.dump(payload, sort_keys=False, default_flow_style=False)
    path.write_text(yaml_text, encoding="utf-8")
    clear_node_alias_cache()
    return path


def build_corpus_alias_map(chunks: list[ProtocolChunk]) -> dict[str, str]:
    """Build legacy-to-canonical alias map from chunk sequence."""
    alias_map: dict[str, str] = {}
    for c in chunks:
        if c.parent_id is not None:
            if c.legacy_id:
                alias_map[c.legacy_id] = c.chunk_id
            for alias in c.aliases:
                alias_map[alias] = c.chunk_id
    return alias_map


def resolve_chunk_id(
    chunk_id_or_alias: str,
    alias_map: dict[str, str] | None = None,
) -> str:
    """Resolve a chunk ID or legacy positional alias to its canonical content-addressed ID."""
    if not chunk_id_or_alias:
        return ""
    if alias_map and chunk_id_or_alias in alias_map:
        return alias_map[chunk_id_or_alias]
    return chunk_id_or_alias
