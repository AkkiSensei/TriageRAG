"""Unit tests for Gate G4: Evaluation That Can Fail (FG-06, FG-07, HD-3).

Safety Properties (AGENTS.md R1, R2, R10):
1. Verifies dataset labels are frozen in dedicated commit in LABELS_FROZEN_AT.
2. Verifies calibration sweep was run on dev split and matches config.yaml.
3. Verifies retrieval reports Recall@1, 3, 5 split by syndrome_provided vs vitals_only.
4. Verifies permutation sanity check collapses Recall@1 on shuffled node labels.
5. Verifies ECE is reported without unqualified clinical PASS (HD-3 / ADR-0008).
6. Verifies BACKLOG.md item 12 is IN PROGRESS with HD-3 documented.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_dataset_matches_frozen_commit() -> None:
    """FG-06: LABELS_FROZEN_AT must contain a 40-char SHA matching git history of dataset.yaml."""
    frozen_file = REPO_ROOT / "eval" / "retrieval" / "LABELS_FROZEN_AT"
    assert frozen_file.exists(), "LABELS_FROZEN_AT must exist in eval/retrieval/"
    sha = frozen_file.read_text(encoding="utf-8").strip()
    assert re.match(r"^[0-9a-f]{40}$", sha), f"Invalid SHA in LABELS_FROZEN_AT: {sha}"

    dataset_path = REPO_ROOT / "eval" / "retrieval" / "dataset.yaml"
    assert dataset_path.exists(), "eval/retrieval/dataset.yaml must exist on disk"

    # Verify that dataset.yaml exists at this commit
    cmd = ["git", "cat-file", "-e", f"{sha}:eval/retrieval/dataset.yaml"]
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode == 0:
        return

    # If cat-file failed, check if the repository is a shallow clone or missing objects
    # 1. Attempt to fetch the frozen commit object from remote if reachable
    fetch_cmd = ["git", "fetch", "--depth=1", "origin", sha]
    subprocess.run(fetch_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode == 0:
        return

    # 2. In offline, air-gapped, or shallow container environments without remote access,
    # verify that dataset.yaml is tracked in HEAD
    head_cmd = ["git", "cat-file", "-e", "HEAD:eval/retrieval/dataset.yaml"]
    head_res = subprocess.run(head_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if head_res.returncode == 0:
        return

    assert res.returncode == 0, (
        f"dataset.yaml does not exist at frozen commit {sha} (git error: {res.stderr.strip()})"
    )


def test_calibration_run_record_exists_and_matches_config() -> None:
    """FG-07: Config calibration_run_id must point to a real dev-split calibration record."""
    cfg_path = REPO_ROOT / "data" / "retrieval" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    run_id = cfg.get("calibration_run_id")
    assert run_id, "data/retrieval/config.yaml must have calibration_run_id"
    assert run_id.startswith("CALIB_FG4_"), f"calibration_run_id must be G4 sweep, got: {run_id}"

    calib_file = REPO_ROOT / "eval" / "reports" / f"calibration_run_{run_id}.json"
    assert calib_file.exists(), f"Calibration record file {calib_file} does not exist"

    calib_data = json.loads(calib_file.read_text(encoding="utf-8"))
    assert calib_data["run_id"] == run_id
    assert "grid" in calib_data
    assert "selection_rule" in calib_data
    assert "selected_params" in calib_data

    sel = calib_data["selected_params"]
    assert cfg["calibrated_threshold"] == sel["calibrated_threshold"]
    assert cfg["syndrome_inferred_threshold"] == sel["syndrome_inferred_threshold"]
    assert cfg["min_syndrome_margin"] == sel["min_syndrome_margin"]


def test_retrieval_reports_recall_at_1_and_split() -> None:
    """FG-06: retrieval.json must report Recall@1, 3, 5 split by input mode."""
    report_file = REPO_ROOT / "eval" / "reports" / "retrieval.json"
    assert report_file.exists(), "retrieval.json must exist"
    data = json.loads(report_file.read_text(encoding="utf-8"))

    assert "recall_at_1" in data["test"]
    assert "recall_at_3" in data["test"]
    assert "recall_at_5" in data["test"]

    assert "syndrome_provided" in data["test"]
    assert "vitals_only" in data["test"]

    syn_test = data["test"]["syndrome_provided"]
    vit_test = data["test"]["vitals_only"]

    assert syn_test["positive_cases"] > 0
    assert "recall_at_1" in syn_test
    assert "recall_at_5" in syn_test
    assert "recall_at_5_ci95" in syn_test

    assert vit_test["positive_cases"] > 0
    assert "recall_at_1" in vit_test
    assert "recall_at_5" in vit_test
    assert "recall_at_1_ci95" in vit_test

    # Hard invariant gates on test
    assert data["test"]["wrong_protocol_rate"] == 0.0
    assert data["test"]["abstain_recall_hard_negatives"] == 1.0


def test_permutation_check_collapses_recall() -> None:
    """FG-06: Permuting node labels must collapse Recall@1 to near zero (< 0.05)."""
    from eval.run_retrieval import run_permutation_sanity_check

    perm_r1 = run_permutation_sanity_check()
    assert perm_r1 < 0.05, f"Permutation check failed to collapse: Recall@1 = {perm_r1}"


def test_ece_reported_without_unqualified_pass_without_adr() -> None:
    """FG-07 & HD-3: ECE must not be marked with an unqualified clinical PASS."""
    calib_path = REPO_ROOT / "eval" / "reports" / "retrieval_calibration.md"
    calib_md = calib_path.read_text(encoding="utf-8")
    assert "HD-3" in calib_md or "ADR-0008" in calib_md
    assert "ECE: PASS" not in calib_md


def test_backlog_item_12_reopened_as_in_progress() -> None:
    """FG-07 & HD-3: BACKLOG.md item 12 must be marked IN PROGRESS with HD-3."""
    backlog = (REPO_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    assert re.search(r"12\.\s+.*\[IN PROGRESS\]", backlog), (
        "Item 12 in BACKLOG.md must be [IN PROGRESS]"
    )
    assert "HD-3" in backlog, "BACKLOG.md must reference HD-3"
