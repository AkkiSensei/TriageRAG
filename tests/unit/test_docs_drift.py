"""Unit tests for documentation metrics generator and drift detection (AUB-DOC-01 / AUB-DOC-02 / T0.6).

Safety Properties (Rule R10, Rule R14):
1. Verifies that all metrics in README, HANDOFF, and ENGINEERING_FINAL_RESULTS match canonical reports.
2. Verifies that manual edits or tampering inside AUTOGEN blocks fail the drift gate.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_docs_metrics_in_sync_with_reports() -> None:
    """T0.6 / AUB-DOC-01 / AUB-DOC-02: Documentation numbers must match eval/reports/*.json exactly."""
    script = REPO_ROOT / "tools" / "gen_docs_metrics.py"
    res = subprocess.run([sys.executable, str(script), "--check"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"Drift detected in documentation metrics:\n{res.stdout}\n{res.stderr}"


def test_docs_drift_detector_catches_tampered_numbers(tmp_path: Path) -> None:
    """T0.6 acceptance: Tampering with a number inside an AUTOGEN block must fail --check."""
    from tools.gen_docs_metrics import update_file_section

    mock_doc = tmp_path / "MOCK_DOC.md"
    mock_doc.write_text(
        "# Mock Document\n\n"
        "<!-- AUTOGEN:start:benchmarks -->\n"
        "original: 100\n"
        "<!-- AUTOGEN:end:benchmarks -->\n",
        encoding="utf-8",
    )

    # When expected is different from actual, check=True must return False (drift detected)
    ok = update_file_section(mock_doc, "benchmarks", "replacement: 999", check=True)
    assert ok is False, "Expected drift detection to flag tampered metric"
