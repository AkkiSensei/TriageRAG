"""Integration test verifying test suite execution does not mutate tracked repository artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def test_evaluation_functions_support_non_mutating_execution(tmp_path: Path) -> None:
    """P0-1 Regression: Benchmark and report functions must support isolated execution."""
    from eval.run_latency_benchmark import run_scale_benchmark
    from eval.run_retrieval_ablation import run_retrieval_ablation_suite
    from tools.gate_report import generate_gate_report
    from triagerag.config import get_repo_root

    repo_root = get_repo_root()
    latency_orig = (repo_root / "eval" / "reports" / "latency_benchmark.json").read_bytes()
    ablation_orig = (repo_root / "eval" / "reports" / "retrieval_ablation.json").read_bytes()
    postmortem_orig = (repo_root / "Postmortem-Response.MD").read_bytes()

    # 1. Gate report with write_file=False must not mutate Postmortem-Response.MD
    rep_text = generate_gate_report(write_file=False)
    assert len(rep_text) > 100
    assert (repo_root / "Postmortem-Response.MD").read_bytes() == postmortem_orig

    # 2. Scale benchmark with custom output_path must not mutate latency_benchmark.json
    custom_latency = tmp_path / "custom_latency.json"
    rep_dict = run_scale_benchmark(target_chunks=100, num_queries=10, output_path=custom_latency)
    assert rep_dict["total_chunks"] >= 100
    assert custom_latency.exists()
    assert (repo_root / "eval" / "reports" / "latency_benchmark.json").read_bytes() == latency_orig

    # 3. Ablation suite with output_dir=tmp_path must not mutate retrieval_ablation.json
    rc = run_retrieval_ablation_suite(output_dir=tmp_path, write_reports=True)
    assert rc == 0
    assert (tmp_path / "retrieval_ablation.json").exists()
    assert (
        repo_root / "eval" / "reports" / "retrieval_ablation.json"
    ).read_bytes() == ablation_orig


def test_eval_retrieval_leaves_tracked_reports_unmodified(tmp_path: Path) -> None:
    """T0.8 / AUB-EVL-02: run_retrieval_benchmark defaults to write_reports=False and does not dirty git."""
    from eval.run_retrieval import run_retrieval_benchmark
    from triagerag.config import get_repo_root

    repo_root = get_repo_root()
    ret_json_path = repo_root / "eval" / "reports" / "retrieval.json"
    calib_md_path = repo_root / "eval" / "reports" / "retrieval_calibration.md"

    ret_json_orig = ret_json_path.read_bytes()
    calib_md_orig = calib_md_path.read_bytes()

    # 1. Default run_retrieval_benchmark() must not mutate tracked files
    summary = run_retrieval_benchmark(backend="bm25")
    assert summary["status"] == "PASS"
    assert ret_json_path.read_bytes() == ret_json_orig
    assert calib_md_path.read_bytes() == calib_md_orig

    # 2. When write_reports=True with output_dir=tmp_path, writes only to tmp_path
    run_retrieval_benchmark(backend="bm25", write_reports=True, output_dir=tmp_path)
    assert (tmp_path / "retrieval.json").exists()
    assert (tmp_path / "retrieval_calibration.md").exists()
    assert ret_json_path.read_bytes() == ret_json_orig
    assert calib_md_path.read_bytes() == calib_md_orig
