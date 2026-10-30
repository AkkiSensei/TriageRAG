"""Unit tests for Fix-Gate Report Integrity and Verification Traceability (FG-09..12, G6).

Safety Properties (Rule R1, R10, R12, FG-09, FG-10, FG-11, FG-12):
1. Honesty Rule (FG-09): All metrics in Postmortem-Response.MD are strictly read from committed
   JSON artefacts (eval/reports/*.json); hand-typed or drifted numbers fail this test.
2. Zero Phantom Tests (FG-10): Every test cited in the closure table must exist in pytest suite.
3. Finding ID Preservation (FG-11): 1:1 trace to POSTMORTEM.md (RAG-01..16) and flags (FG-01..20).
4. Zero Phantom Claims (FG-12): No non-existent populations or enums claimed.
"""

from __future__ import annotations

import json

import pytest

from tools.gate_report import (
    FIXGATE_FLAGS,
    POSTMORTEM_FINDINGS,
    collect_pytest_tests,
    generate_gate_report,
)
from triagerag.config import get_repo_root


@pytest.fixture(scope="module")
def report_text() -> str:
    """Generate Postmortem-Response.MD in memory from current artefacts without mutating disk."""
    return generate_gate_report(write_file=False)


def test_all_cited_tests_exist_in_pytest_collection() -> None:
    """FG-10: Every test function cited in closure tables must exist in pytest collection."""
    collected = collect_pytest_tests()
    all_findings = POSTMORTEM_FINDINGS + FIXGATE_FLAGS

    missing_tests: dict[str, list[str]] = {}
    for finding in all_findings:
        missing = [t for t in finding["tests"] if t not in collected]
        if missing:
            missing_tests[finding["id"]] = missing

    assert not missing_tests, f"Found phantom tests cited in report: {missing_tests}"


def test_finding_ids_match_postmortem_and_fixgate_spec(report_text: str) -> None:
    """FG-11: Closure table must preserve RAG-01..16 and FG-01..20 with zero renumbering."""
    # Verify all 16 POSTMORTEM.md IDs exist
    for idx in range(1, 17):
        rag_id = f"RAG-{idx:02d}"
        assert f"**{rag_id}**" in report_text, f"Missing finding ID: {rag_id}"

    # Verify all 20 Fix Gate flag IDs exist
    for idx in range(1, 21):
        fg_id = f"FG-{idx:02d}"
        assert f"**{fg_id}**" in report_text, f"Missing fixgate flag ID: {fg_id}"

    # Verify forbidden fabricated finding 'RAG-09 Decimal' does not exist
    assert "RAG-09 Decimal" not in report_text


def test_report_numbers_match_committed_artefacts(report_text: str) -> None:
    """FG-09: Numbers in Postmortem-Response.MD must match committed JSON reports."""
    repo_root = get_repo_root()
    reports_dir = repo_root / "eval" / "reports"

    retrieval_data = json.loads((reports_dir / "retrieval.json").read_text(encoding="utf-8"))
    mutation_data = json.loads((reports_dir / "mutation.json").read_text(encoding="utf-8"))
    latency_data = json.loads((reports_dir / "latency_benchmark.json").read_text(encoding="utf-8"))

    test_split = retrieval_data["test"]

    # Verify test Recall@5
    r5 = f"{test_split['recall_at_5']:.2f}%"
    assert r5 in report_text, f"Expected test Recall@5 {r5} in report"

    # Verify test MRR
    mrr = f"{test_split['mrr']:.4f}"
    assert mrr in report_text, f"Expected test MRR {mrr} in report"

    # Verify test ECE
    ece = f"{test_split['ece']:.4f}"
    assert ece in report_text, f"Expected test ECE {ece} in report"

    # Verify mutation kill score
    killed = f"{mutation_data['overall_mutants_killed']}/{mutation_data['overall_mutants_total']}"
    assert killed in report_text, f"Expected mutation count {killed} in report"

    # Verify latency benchmark p95
    p95 = f"{latency_data['p95_latency_ms']:.3f} ms"
    assert p95 in report_text, f"Expected latency p95 {p95} in report"


def test_no_phantom_claims_in_report(report_text: str) -> None:
    """FG-12: Zero phantom claims (infant partition, phantom AbstainCodes, fake guarantees)."""
    # Enforce population partition honesty: only adult, paediatric, neonate
    assert "adult, paediatric, infant, neonate partitions" not in report_text.lower()

    # Enforce real AbstainCode enums: NO_SYNDROME and POPULATION_SYNDROME_MISMATCH do not exist
    assert "AbstainCode.NO_SYNDROME" not in report_text
    assert "AbstainCode.POPULATION_SYNDROME_MISMATCH" not in report_text

    # Fail closed defaults documented
    assert "NEEDS_SOURCE, threshold: null" in report_text
    assert "HD-1" in report_text
    assert "HD-2" in report_text
    assert "HD-3" in report_text
    assert "HD-4" in report_text
    assert "HD-5" in report_text


def test_stratified_case_counts_match_retrieval_json(report_text: str) -> None:
    """N3: Stratified table case counts must match retrieval.json positive_cases exactly."""
    repo_root = get_repo_root()
    retrieval_data = json.loads(
        (repo_root / "eval" / "reports" / "retrieval.json").read_text(encoding="utf-8")
    )
    test_split = retrieval_data["test"]
    sp_cases = test_split["syndrome_provided"]["positive_cases"]
    vo_cases = test_split["vitals_only"]["positive_cases"]

    assert f"| **Syndrome Provided** | {sp_cases} |" in report_text
    assert f"| **Vitals Only (Inferred)** | {vo_cases} |" in report_text


def test_error_codes_and_ece_consistency_in_report(report_text: str) -> None:
    """N3: Error codes must cite EMPTY_QUERY for HD-1, and ECE must be identical across sections."""
    repo_root = get_repo_root()
    retrieval_data = json.loads(
        (repo_root / "eval" / "reports" / "retrieval.json").read_text(encoding="utf-8")
    )
    ece_str = f"{retrieval_data['test']['ece']:.4f}"

    # HD-1 must cite EMPTY_QUERY
    assert "AbstainCode.EMPTY_QUERY" in report_text
    # Section 4 cited test ECE must match Section 3 test ECE
    assert f"Observed test ECE = {ece_str}" in report_text
    assert "0.1501" not in report_text


def test_four_distinct_ablation_arms_without_duplicates(report_text: str) -> None:
    """N3: Exactly four distinct ablation arms appear in the report table."""
    repo_root = get_repo_root()
    ablation_data = json.loads(
        (repo_root / "eval" / "reports" / "retrieval_ablation.json").read_text(encoding="utf-8")
    )
    arms = ablation_data["arms"]
    assert len(arms) == 4
    for arm_id in ("bm25", "char_ngram", "hybrid_rrf", "hybrid_rrf_rerank"):
        assert f"| `{arm_id}` |" in report_text
    assert "| `dense` |" not in report_text


def test_finding_statuses_accurate_for_hd_and_container(report_text: str) -> None:
    """N3 / P2: HD-blocked items are marked DEFERRED/PENDING HD, and container is NOT VERIFIED."""
    expected_fg02 = (
        "| **FG-02** | Unsourced paediatric thresholds left ACTIVE; single paediatric band "
        "| CLOSED (FAIL-CLOSED, PENDING HD-1) |"
    )
    expected_fg07 = (
        "| **FG-07** | Calibration not a calibration (no sweep, uncommitted ID, unverified ECE) "
        "| DEFERRED (FAIL-CLOSED, PENDING HD-3) |"
    )
    expected_fg18 = (
        "| **FG-18** | Ops (multi-stage non-root Dockerfile, compose web+api, drop rank_bm25) "
        "| NOT VERIFIED (SMOKE-TESTED IN CI) |"
    )
    assert expected_fg02 in report_text
    assert expected_fg07 in report_text
    assert expected_fg18 in report_text
