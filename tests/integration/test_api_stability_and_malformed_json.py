"""Regression tests proving API stability, exact malformed JSON handling, and shell pipe artifact reproduction.

Safety & Audit Properties:
1. Explains and proves the root cause of the initial curl failure in PowerShell:
   PowerShell interprets unescaped backslash-quotes inside double-quotes, delivering truncated '{\\'
   which triggers FastAPI's RequestValidationError (HTTP 422 'JSON decode error') at the API boundary.
2. Asserts zero graph node spans are emitted on JSON decode error.
3. Asserts the server remains fully stable and immediately processes subsequent valid requests with HTTP 200.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from triagerag.api.app import app
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.orchestration.telemetry import TelemetryManager

client = TestClient(app)


@pytest.fixture(autouse=True)
def configure_api_telemetry(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Enable in-memory telemetry for API integration tests."""
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_EXPORTER", "in_memory")
    TelemetryManager.reset_for_testing()
    manager = TelemetryManager.get_instance()
    manager.initialize()
    manager.clear_in_memory_spans()
    yield
    TelemetryManager.reset_for_testing()


def test_reproduce_exact_truncated_json_payload_422() -> None:
    """Assert sending the exact truncated body '{\\' received during PowerShell curl triggers HTTP 422 safely."""
    manager = TelemetryManager.get_instance()
    manager.initialize()
    manager.clear_in_memory_spans()

    # The exact raw body transmitted when PowerShell curl strips quotes:
    malformed_body = b"{\\"

    response = client.post(
        "/api/triage",
        content=malformed_body,
        headers={"Content-Type": "application/json"},
    )

    # 1. Assert HTTP 422 Unprocessable Content
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data
    assert any("JSON decode error" in err.get("message", "") for err in data["errors"])

    # 2. Assert safe W3C headers are present
    assert "traceparent" in response.headers
    assert "x-trace-id" in response.headers

    # 3. Assert zero internal LangGraph node spans were emitted
    spans = manager.get_in_memory_spans()
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]
    assert len(node_spans) == 0, f"Expected 0 node spans, found {len(node_spans)}"


def test_server_stability_subsequent_request_succeeds_with_200() -> None:
    """Assert server is completely stable: after handling 422, a valid request succeeds with HTTP 200."""
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    patient, overrides = get_preloaded_scenario("BLOCK")
    valid_payload: dict[str, Any] = {
        "patient": json.loads(patient.model_dump_json()),
        "overrides": overrides or [],
        "retrieval_backend": "bm25",
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }

    response = client.post("/api/triage", json=valid_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["engine"]["verdict"] == "BLOCKED"

    # Verify spans for the successful request
    spans = manager.get_in_memory_spans()
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]
    assert len(node_spans) == 8
