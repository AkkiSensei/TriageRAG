"""Unit tests for WP9: CLI retrieve --explain, Retrieval Inspector API/UI, ops, and 10k benchmark.

Safety Properties (RAG-16, Rule R12):
1. CLI 'triagerag retrieve --explain' renders full retrieval diagnostics (query, flags, filters,
   BM25 term contributions, AbstainCode, corpus_hash).
2. FastAPI POST /api/triage/explain returns the structured diagnostic trace.
3. 10,000-chunk synthetic scale benchmark executes with p95 lexical latency < 50 ms.
4. Dockerfile, docker-compose.yml, and .devcontainer/devcontainer.json exist.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from triagerag.api.app import app as fastapi_app
from triagerag.cli import app as cli_app
from triagerag.config import get_repo_root
from triagerag.contracts.scenarios import get_preloaded_scenario

runner = CliRunner()
client = TestClient(fastapi_app)


def test_cli_retrieve_explain_command() -> None:
    """RAG-16: 'triagerag retrieve --scenario BLOCK --explain' outputs diagnostic breakdown."""
    res = runner.invoke(cli_app, ["retrieve", "--scenario", "BLOCK", "--explain"])
    assert res.exit_code == 0, f"CLI retrieve failed: {res.stdout}"
    assert "RETRIEVAL INSPECTOR" in res.stdout
    assert "chest_pain" in res.stdout
    assert "NONE" in res.stdout

    # Also test custom syndrome + population flags
    res_custom = runner.invoke(
        cli_app,
        ["retrieve", "--syndrome", "kidney_stone", "--population", "adult", "--explain"],
    )
    assert res_custom.exit_code == 0, f"CLI custom retrieve failed: {res_custom.stdout}"
    assert "UNKNOWN_SYNDROME" in res_custom.stdout


def test_api_triage_explain_endpoint() -> None:
    """RAG-16: POST /api/triage/explain returns structured diagnostic trace."""
    patient, _ = get_preloaded_scenario("BLOCK")
    resp = client.post(
        "/api/triage/explain",
        json={"patient": json.loads(patient.model_dump_json())},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["population"] == "adult"
    assert data["normalized_syndrome"] == "chest_pain"
    assert data["abstain_code"] == "NONE"
    assert len(data["corpus_hash"]) == 64
    assert "bm25_trace" in data


def test_10k_chunk_scale_latency_benchmark() -> None:
    """WP9: 10,000-chunk synthetic scale benchmark verifies lexical p95 latency < 50 ms."""
    from eval.run_latency_benchmark import run_scale_benchmark

    report = run_scale_benchmark(target_chunks=10000, num_queries=100)
    assert report["total_chunks"] >= 10000
    assert report["p95_latency_ms"] < 50.0

    report_path = get_repo_root() / "eval" / "reports" / "latency_benchmark.json"
    assert report_path.exists()


def test_ops_container_and_ui_inspector_artifacts_exist() -> None:
    """WP9 & FG-18: Dockerfile, docker-compose.yml, devcontainer.json, and RetrievalView exist."""
    repo_root = get_repo_root()
    dockerfile_text = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    assert "USER appuser" in dockerfile_text
    assert "HEALTHCHECK" in dockerfile_text

    assert (repo_root / "Dockerfile.web").exists()

    compose_text = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "triagerag-api:" in compose_text
    assert "triagerag-web:" in compose_text

    assert (repo_root / ".devcontainer" / "devcontainer.json").exists()

    rv_text = (repo_root / "web" / "src" / "features" / "results" / "RetrievalView.tsx").read_text(
        encoding="utf-8"
    )
    assert "abstain_code" in rv_text
    assert "corpus_hash" in rv_text
