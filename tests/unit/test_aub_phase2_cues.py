"""Unit tests for AUB Phase 2 Task T2.3: Synthetic Retrieval Cues.

Safety Properties:
1. Every cue is explicitly synthetic (source_status: SYNTHETIC_AUTHORED).
2. Every cue maps a structured predicate to protocol vocabulary.
3. Every cue key references a valid predicate defined in predicates.yaml.
4. Cues expansion is strictly deterministic and deduplicated.
5. Separation: Clinical rule engine (triagerag.engine) never reads cues.yaml or imports cues.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

from triagerag.contracts.enums import SourceStatus
from triagerag.rag.cues import (
    PredicateCueMapping,
    RetrievalCuesConfig,
    expand_predicates_to_cues,
    load_retrieval_cues,
)
from triagerag.rag.predicates import load_predicate_vocabulary


def test_load_retrieval_cues_from_yaml() -> None:
    """Verify loading canonical data/retrieval/cues.yaml."""
    config = load_retrieval_cues()
    assert isinstance(config, RetrievalCuesConfig)
    assert config.source_status == SourceStatus.SYNTHETIC_AUTHORED
    assert len(config.cues) >= 15

    # Check that key clinical cues exist
    assert "low_systolic_bp" in config.cues
    assert "hypotension" in config.cues["low_systolic_bp"].terms
    assert "beta_blocker_active" in config.cues
    assert "hypoglycemia" in config.cues


def test_all_cues_reference_valid_predicates() -> None:
    """Every cue in cues.yaml must reference a valid predicate from predicates.yaml."""
    cues_cfg = load_retrieval_cues()
    vocab = load_predicate_vocabulary()
    vocab_ids = {p.id for p in vocab.predicates}

    for pred_id in cues_cfg.cues:
        assert pred_id in vocab_ids, f"Cue key '{pred_id}' does not exist in predicate vocabulary"


def test_deterministic_cue_expansion_and_deduplication() -> None:
    """Verify deterministic expansion and absence of duplicate terms."""
    cues_cfg = load_retrieval_cues()
    predicates = ["low_systolic_bp", "tachycardia"]

    terms_1 = expand_predicates_to_cues(predicates, cues_cfg)
    terms_2 = expand_predicates_to_cues(predicates, cues_cfg)
    assert terms_1 == terms_2
    assert len(terms_1) == len(set(terms_1))  # No duplicates
    assert "hypotension" in terms_1
    assert "tachycardia" in terms_1


def test_separation_engine_never_imports_cues() -> None:
    """Strict separation: rule engine must never import from cues.py or read cues.yaml."""
    engine_dir = Path("src/triagerag/engine")
    assert engine_dir.is_dir()
    for py_file in engine_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "cues.yaml" not in content, (
            f"Engine file {py_file} violates isolation by referencing cues.yaml"
        )
        tree = ast.parse(content, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "cues" not in alias.name, (
                        f"Engine file {py_file} violates isolation by importing {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "cues" not in node.module, (
                    f"Engine file {py_file} violates isolation by importing from {node.module}"
                )


def test_cue_mapping_deduplicates_terms() -> None:
    """PredicateCueMapping removes duplicate terms while preserving order."""
    mapping = PredicateCueMapping(
        predicate_id="test_pred",
        terms=("hypotension", "shock", "hypotension", "collapse"),
    )
    assert mapping.terms == ("hypotension", "shock", "collapse")
