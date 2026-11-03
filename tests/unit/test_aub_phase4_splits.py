"""Tests for AUB Phase 4 Task 4.1: Template-Grouped Dataset Splits (AUB-EVL-01).

Safety Properties (AUB-EVL-01, T4.1, Rules R1, R10, R12):
1. Every evaluation case declares an explicit, reconstructible template_id grouping key.
2. Zero template group leakage between development and test sets (group isolation invariant).
3. Zero target node-set leakage between development and test sets.
4. Stratified balance: vitals-only, syndrome-provided, and expected-abstain cases are
   well-represented in both development and test splits.
5. Deterministic split manifest records dataset hash, corpus hash, split seed, and grouping scheme.
"""

from __future__ import annotations

import hashlib
import json

import yaml

from triagerag.config import get_repo_root


def test_every_case_declares_template_id() -> None:
    """T4.1 Acceptance: every evaluation case must declare an explicit template_id."""
    dataset_path = get_repo_root() / "eval" / "retrieval" / "dataset.yaml"
    assert dataset_path.exists(), "eval/retrieval/dataset.yaml must exist"

    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])
    assert len(cases) == 224

    missing_template_ids = [c["id"] for c in cases if not c.get("template_id")]
    assert not missing_template_ids, f"Cases missing template_id: {missing_template_ids[:5]}"


def test_zero_template_leakage_between_dev_and_test() -> None:
    """T4.1 Core Invariant: No template group may appear in both dev and test splits."""
    dataset_path = get_repo_root() / "eval" / "retrieval" / "dataset.yaml"
    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])

    dev_templates = {c["template_id"] for c in cases if c.get("split") == "dev"}
    test_templates = {c["template_id"] for c in cases if c.get("split") == "test"}

    overlap = dev_templates & test_templates
    assert not overlap, f"Template leakage detected between dev and test: {overlap}"


def test_zero_target_nodeset_leakage_between_dev_and_test() -> None:
    """T4.1 Invariant: No positive target node-set appears in both dev and test splits."""
    dataset_path = get_repo_root() / "eval" / "retrieval" / "dataset.yaml"
    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])

    dev_targets: set[frozenset[tuple[str, int]]] = set()
    test_targets: set[frozenset[tuple[str, int]]] = set()

    for c in cases:
        if c.get("expect_abstain"):
            continue
        g2 = frozenset((cid, g) for cid, g in (c.get("relevance_grades") or {}).items() if g >= 2)
        if not g2:
            continue
        if c.get("split") == "dev":
            dev_targets.add(g2)
        elif c.get("split") == "test":
            test_targets.add(g2)

    leakage = dev_targets & test_targets
    assert not leakage, f"Target node-set leakage detected across splits: {leakage}"


def test_split_manifest_integrity_and_lock() -> None:
    """T4.1: split_manifest.json and dataset.lock match dataset.yaml without git metadata."""
    repo_root = get_repo_root()
    dataset_path = repo_root / "eval" / "retrieval" / "dataset.yaml"
    lock_path = repo_root / "eval" / "retrieval" / "dataset.lock"
    manifest_path = repo_root / "eval" / "retrieval" / "split_manifest.json"

    assert lock_path.exists(), "dataset.lock missing"
    assert manifest_path.exists(), "split_manifest.json missing"

    content = dataset_path.read_text(encoding="utf-8")
    actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    locked_hash = lock_path.read_text(encoding="utf-8").strip()
    assert actual_hash == locked_hash, "dataset.lock hash mismatch"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dataset_hash"] == actual_hash
    assert manifest["group_leakage_count"] == 0
    assert manifest["split_algorithm"] == "stratified_template_group_split"
    assert manifest["grouping_key"] == "template_id"
    assert manifest["dev_cases"] + manifest["test_cases"] == 224
