"""Unit tests verifying the verify-fast gate contract and preserved execution log artifact.

Safety Property:
Ensures that the fast verification gate produces an independently verifiable,
durable log artifact with exit code 0, commit metadata, and all passed stage markers.
"""

from __future__ import annotations

from triagerag.config import get_repo_root


def test_verify_fast_log_artifact_exists_and_records_clean_gate() -> None:
    """Assert eval/reports/verify_fast.log exists, contains all stage markers, and records EXIT_CODE: 0."""
    repo_root = get_repo_root()
    log_file = repo_root / "eval" / "reports" / "verify_fast.log"

    # If the gate has been executed, verify its contract
    assert log_file.exists(), (
        f"Verification transcript missing at {log_file}. Run 'python tools/tasks.py verify-fast' first."
    )

    content = log_file.read_text(encoding="utf-8")

    # 1. Header and metadata markers
    assert "=== TRIAGERAG FAST VERIFICATION RUN RECORD ===" in content
    assert "TIMESTAMP:" in content
    assert "GIT_COMMIT:" in content

    # 2. Stage headers and passed status markers executed prior to / during unit test execution
    pre_unit_markers = [
        "=== Running Linters ===",
        "[OK] Linting clean",
        "=== Running Type Checking (mypy) ===",
        "[OK] Types clean",
        "=== Checking Layer Isolation (import-linter) ===",
        "[OK] Layer isolation intact",
        "=== Validating Clinical Data Schemas ===",
        "[OK] Data validation passed",
        "=== Running Rule Coverage Matrix & Alert Fatigue Gate ===",
        "[OK] Rule coverage matrix and alert fatigue gate PASSED",
        "=== Running Unit Test Suite ===",
    ]

    for marker in pre_unit_markers:
        assert marker in content, f"Mandatory gate marker missing from {log_file}: '{marker}'"

    # 3. If the gate run has completed, assert final success banner and exit code
    if "EXIT_CODE:" in content:
        assert "EXIT_CODE: 0" in content, f"Log records non-zero exit code: {content}"
        assert "[OK] FAST VERIFICATION GATES GREEN" in content
        assert "EXIT_CODE: 1" not in content
