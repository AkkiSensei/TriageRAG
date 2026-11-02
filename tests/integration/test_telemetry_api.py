"""Integration tests for FastAPI OpenTelemetry ASGI middleware, W3C propagation, and 3-tier hierarchy.

Safety & Acceptance Gates Covered:
- Gate 3: Span Parenting Hierarchy (http.request -> workflow -> 8 node spans)
- Gate 4: Request Correlation & W3C Header Propagation (incoming & response traceparent)
- Gate 5: Telemetry Non-Interference at the API Boundary
- Gate 10: Telemetry Disabled Operation
- Exceptional Request Handling (HTTP 422 & 413 with 0 graph node spans)
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


def get_clean_triage_payload() -> dict[str, Any]:
    """Return serialized JSON payload for clean anaphylaxis patient."""
    patient, overrides = get_preloaded_scenario("CLEAN")
    return {
        "patient": json.loads(patient.model_dump_json()),
        "overrides": overrides or [],
        "retrieval_backend": "bm25",
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }


# =============================================================================
# Gate 3: Three-Tier Hierarchy (http.request -> workflow -> nodes)
# =============================================================================


def test_api_triage_three_tier_parenting_and_trace_correlation() -> None:
    """Gate 3: Assert complete 3-tier hierarchy and shared trace_id across API and LangGraph."""
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    payload = get_clean_triage_payload()
    resp = client.post("/api/triage", json=payload)
    assert resp.status_code == 200
    assert "engine" in resp.json()

    spans = manager.get_in_memory_spans()
    http_spans = [s for s in spans if s.name == "http.request"]
    wf_spans = [s for s in spans if s.name == "langgraph.workflow.execution"]
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]

    assert len(http_spans) == 1
    assert len(wf_spans) == 1
    assert len(node_spans) == 8
    assert len(spans) == 10

    http_span = http_spans[0]
    wf_span = wf_spans[0]

    # 1. Assert identical 128-bit trace_id across entire execution tree
    root_trace_id = http_span.context.trace_id
    assert root_trace_id != 0
    assert wf_span.context.trace_id == root_trace_id
    for ns in node_spans:
        assert ns.context.trace_id == root_trace_id

    # 2. Assert workflow span parent is the HTTP root span
    assert wf_span.parent.span_id == http_span.context.span_id

    # 3. Assert all 8 executed node spans have the workflow span as their parent
    for ns in node_spans:
        assert ns.parent.span_id == wf_span.context.span_id

    # 4. Verify HTTP span attributes
    assert http_span.attributes.get("http.method") == "POST"
    assert http_span.attributes.get("http.route") == "/api/triage"
    assert http_span.attributes.get("http.status_code") == 200

    # 5. Verify response propagation headers
    assert "traceparent" in resp.headers
    assert resp.headers.get("X-Trace-Id") == f"{root_trace_id:032x}"


# =============================================================================
# Gate 4: W3C Trace Context Propagation
# =============================================================================


def test_w3c_incoming_traceparent_propagation() -> None:
    """Gate 4: Assert incoming W3C traceparent anchors root span and returns matching X-Trace-Id."""
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    custom_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    incoming_traceparent = f"00-{custom_trace_id}-00f067aa0ba902b7-01"

    payload = get_clean_triage_payload()
    resp = client.post(
        "/api/triage",
        json=payload,
        headers={"traceparent": incoming_traceparent},
    )
    assert resp.status_code == 200

    # Assert response header correlation
    assert resp.headers.get("X-Trace-Id") == custom_trace_id
    assert "traceparent" in resp.headers

    # Assert root span extracted and retained the incoming trace_id
    spans = manager.get_in_memory_spans()
    http_span = next(s for s in spans if s.name == "http.request")
    assert f"{http_span.context.trace_id:032x}" == custom_trace_id


def test_w3c_malformed_traceparent_fallback() -> None:
    """Assert malformed traceparent does not fail request; generates fresh valid trace_id."""
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    payload = get_clean_triage_payload()
    resp = client.post(
        "/api/triage",
        json=payload,
        headers={"traceparent": "invalid-malformed-w3c-header"},
    )
    assert resp.status_code == 200
    assert "X-Trace-Id" in resp.headers
    assert len(resp.headers["X-Trace-Id"]) == 32


# =============================================================================
# Exceptional / Rejected Requests (0 LangGraph Node Spans)
# =============================================================================


def test_rejected_request_validation_422_emits_zero_graph_spans() -> None:
    """Assert HTTP 422 rejected at API boundary emits 1 HTTP span and ZERO graph spans."""
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    resp = client.post("/api/triage", json={"malformed": "patient_data"})
    assert resp.status_code == 422

    spans = manager.get_in_memory_spans()
    assert len(spans) == 1
    http_span = spans[0]
    assert http_span.name == "http.request"
    assert http_span.attributes.get("http.status_code") == 422

    # Zero workflow or node spans emitted
    assert len([s for s in spans if s.name.startswith("langgraph.")]) == 0


def test_rejected_request_size_413_emits_zero_graph_spans() -> None:
    """Assert HTTP 413 request entity too large emits 1 HTTP span and ZERO graph spans."""
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    resp = client.post(
        "/api/triage",
        content=b"x" * 10,
        headers={"content-length": "3000000", "content-type": "application/json"},
    )
    assert resp.status_code == 413

    spans = manager.get_in_memory_spans()
    assert len(spans) == 1
    http_span = spans[0]
    assert http_span.name == "http.request"
    assert http_span.attributes.get("http.status_code") == 413

    # Zero workflow or node spans emitted
    assert len([s for s in spans if s.name.startswith("langgraph.")]) == 0


# =============================================================================
# Gate 5 & Gate 10: Telemetry Disabled & Non-Interference
# =============================================================================


def test_telemetry_disabled_api_operates_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate 10: Assert application operates cleanly with zero overhead when telemetry disabled."""
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "false")
    TelemetryManager.reset_for_testing()

    payload = get_clean_triage_payload()
    resp = client.post("/api/triage", json=payload)
    assert resp.status_code == 200
    assert "engine" in resp.json()

    manager = TelemetryManager.get_instance()
    assert len(manager.get_in_memory_spans()) == 0


def test_api_non_interference_when_tracer_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate 5: Assert tracer exception at API layer NEVER breaks or alters clinical HTTP response."""

    class CrashingTracer:
        def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Catastrophic tracer failure")

    monkeypatch.setattr(TelemetryManager.get_instance(), "get_tracer", lambda: CrashingTracer())

    payload = get_clean_triage_payload()
    resp = client.post("/api/triage", json=payload)
    assert resp.status_code == 200
    assert "engine" in resp.json()


def test_http_exception_privacy_sensitive_marker_never_leaked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate 1: Assert HTTP span never captures sensitive exception text or traceback on error."""
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_EXPORTER", "in_memory")
    TelemetryManager.reset_for_testing()
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    sensitive_marker = "SENSITIVE_SECRET_INTERNAL_DATABASE_URL_TOKEN"

    # Mock the triage endpoint or orchestrator to raise an exception containing sensitive_marker
    def mock_run_triage(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            f"Database error: {sensitive_marker}\nTraceback (most recent call last):\nFile 'db.py', line 99"
        )

    from triagerag.api.routes import triage as triage_route_module

    monkeypatch.setattr(triage_route_module, "run_triage", mock_run_triage)

    payload = get_clean_triage_payload()
    with pytest.raises(RuntimeError, match=sensitive_marker):
        client.post("/api/triage", json=payload)

    spans = manager.get_in_memory_spans()
    http_spans = [s for s in spans if s.name == "http.request"]
    assert len(http_spans) == 1
    http_span = http_spans[0]

    # Verify attributes
    for k, v in http_span.attributes.items():
        assert sensitive_marker not in str(k)
        assert sensitive_marker not in str(v)
        assert "Traceback" not in str(v)

    # Verify error classification
    assert http_span.attributes.get("error.type") == "application_error"
    assert http_span.attributes.get("http.status_code") == 500

    # Verify 0 events recorded (record_exception=False)
    assert len(http_span.events) == 0

    # Verify status description
    if http_span.status and http_span.status.description:
        assert sensitive_marker not in http_span.status.description

    # Verify resource attributes
    if http_span.resource and http_span.resource.attributes:
        for r_k, r_v in http_span.resource.attributes.items():
            assert sensitive_marker not in str(r_k)
            assert sensitive_marker not in str(r_v)
