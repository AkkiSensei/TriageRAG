"""Unit tests for OpenTelemetry instrumentation facade, sanitizer, and non-interference.

Safety & Acceptance Gates Covered:
- Gate 1: Zero-Sensitive-Data Privacy & Schema Enforcement
- Gate 5: Non-Interference on Telemetry Failure & Genuine Error Propagation
- Gate 7: Telemetry Lifecycle, Idempotence & Safe Shutdown
- Gate 9: Fail-Closed Node Mapping (Unknown Node Rejection)
- Gate 10: Standalone No-Op Behavior & Missing SDK Fallback
- Gate 11: Exception-Event Privacy (Zero Exception Message / Stack Trace Leakage)
- Gate 12: Loopback-Only OTLP Endpoint Validation
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from triagerag.orchestration.telemetry import (
    ALLOWED_SPAN_ATTRIBUTES,
    ATTRIBUTE_SCHEMA,
    NODE_NAME_MAP,
    TelemetryManager,
    _NoOpSpan,
    _NoOpTracer,
    map_node_to_operational_stage,
    sanitize_span_attributes,
    trace_node,
    validate_loopback_endpoint,
)


@pytest.fixture(autouse=True)
def reset_telemetry_singleton() -> Generator[None, None, None]:
    """Reset TelemetryManager before and after every test."""
    TelemetryManager.reset_for_testing()
    yield
    TelemetryManager.reset_for_testing()


# ============================================================================
# Gate 1 & Gate 11: Schema Enforcement, Sanitization & Privacy Protection
# ============================================================================


def test_sanitize_span_attributes_strict_allowlist() -> None:
    """Assert that only schema-allowlisted attributes with valid types survive sanitization."""
    raw_dirty = {
        # Valid attributes
        "service.name": "triagerag",
        "service.version": "0.4.0",
        "deployment.environment": "test",
        "triagerag.workflow.name": "triage_state_graph",
        "triagerag.workflow.status": "completed",
        "triagerag.node.name": "normalise",
        "triagerag.node.status": "completed",
        "triagerag.routing.edge": "route_after_retrieve",
        "http.method": "POST",
        "http.route": "/api/triage",
        "http.status_code": 200,
        "error.type": "application_error",
        # Prohibited clinical & patient data
        "patient_name": "John Doe",
        "patient_id": "MRN-12345",
        "patient_hash": "a1b2c3d4e5f6",
        "age": 45,
        "sex": "male",
        "systolic_bp": 85,
        "heart_rate": 120,
        "spo2": 88,
        "news2_score": 7,
        "verdict": "BLOCKED",
        "has_block_alert": True,
        # Prohibited outcome leakage
        "triagerag.retrieval.abstained": True,
        "triagerag.routing.destination": "block_seal",
        "triagerag.retrieval.chunks_count": 5,
        "block_seal": True,
        # Type mismatches (must be dropped, never stringified)
        "http.status_code_bad": "200",
        "triagerag.workflow.name_obj": {"name": "workflow"},
        # Boolean masquerading as integer (Python bool inherits from int)
        "http.status_code_as_bool": True,
        # Out-of-bounds status code
        "http.status_code_invalid": 99,
        # Unpermitted categorical value
        "deployment.environment_invalid": "staging",
    }

    clean = sanitize_span_attributes(raw_dirty)

    assert clean == {
        "service.name": "triagerag",
        "service.version": "0.4.0",
        "deployment.environment": "test",
        "triagerag.workflow.name": "triage_state_graph",
        "triagerag.workflow.status": "completed",
        "triagerag.node.name": "normalise",
        "triagerag.node.status": "completed",
        "triagerag.routing.edge": "route_after_retrieve",
        "http.method": "POST",
        "http.route": "/api/triage",
        "http.status_code": 200,
        "error.type": "application_error",
    }

    # Verify no prohibited keys survive
    for forbidden in (
        "patient_name",
        "patient_id",
        "patient_hash",
        "age",
        "sex",
        "systolic_bp",
        "news2_score",
        "verdict",
        "triagerag.retrieval.abstained",
        "triagerag.routing.destination",
        "triagerag.retrieval.chunks_count",
    ):
        assert forbidden not in clean


def test_allowed_span_attributes_is_frozen_and_minimal() -> None:
    """Assert ALLOWED_SPAN_ATTRIBUTES matches ATTRIBUTE_SCHEMA and excludes outcome metrics."""
    assert isinstance(ALLOWED_SPAN_ATTRIBUTES, frozenset)
    assert frozenset(ATTRIBUTE_SCHEMA.keys()) == ALLOWED_SPAN_ATTRIBUTES
    assert "triagerag.retrieval.chunks_count" not in ALLOWED_SPAN_ATTRIBUTES
    assert "triagerag.retrieval.abstained" not in ALLOWED_SPAN_ATTRIBUTES
    assert "triagerag.routing.destination" not in ALLOWED_SPAN_ATTRIBUTES


def test_exception_event_privacy_sensitive_marker_never_leaked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate 11: Assert sensitive marker in exception message NEVER enters finished span data.

    Inspects span attributes, events, event attributes, status descriptions,
    and resource attributes to prove that no exception message or traceback is exported.
    """
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_EXPORTER", "in_memory")

    manager = TelemetryManager.get_instance()
    manager.initialize()
    manager.clear_in_memory_spans()

    sensitive_marker = "SENSITIVE_PATIENT_SSN_999-88-7777_CONFIDENTIAL_CLINICAL_NOTE"

    with pytest.raises(RuntimeError, match=sensitive_marker), trace_node("normalise"):
        raise RuntimeError(
            f"Clinical intake failed: {sensitive_marker}\nTraceback (most recent call last):\nFile 'secret.py', line 42"
        )

    spans = manager.get_in_memory_spans()
    assert len(spans) == 1
    span = spans[0]

    # 1. Inspect span attributes (keys and values)
    assert span.attributes is not None
    for attr_key, attr_val in span.attributes.items():
        assert sensitive_marker not in str(attr_key)
        assert sensitive_marker not in str(attr_val)
        assert "Traceback" not in str(attr_val)
        assert "secret.py" not in str(attr_val)

    # Verify controlled error classification
    assert span.attributes.get("triagerag.node.status") == "failed"
    assert span.attributes.get("error.type") == "application_error"

    # 2. Inspect span events & event attributes
    assert len(span.events) == 0, f"Expected 0 span events, found {len(span.events)}: {span.events}"
    for ev in span.events:
        assert sensitive_marker not in str(ev.name)
        assert "Traceback" not in str(ev.name)
        if ev.attributes:
            for ev_k, ev_v in ev.attributes.items():
                assert sensitive_marker not in str(ev_k)
                assert sensitive_marker not in str(ev_v)
                assert "Traceback" not in str(ev_v)

    # 3. Inspect status description
    if span.status and span.status.description:
        assert sensitive_marker not in span.status.description
        assert "Traceback" not in span.status.description
        assert "secret.py" not in span.status.description

    # 4. Inspect resource attributes
    if span.resource and span.resource.attributes:
        for r_k, r_v in span.resource.attributes.items():
            assert sensitive_marker not in str(r_k)
            assert sensitive_marker not in str(r_v)
            assert "Traceback" not in str(r_v)


# ============================================================================
# Gate 9: Fail-Closed Node Mapping (Unknown Node Rejection)
# ============================================================================


def test_node_name_mapping_all_canonical_nodes() -> None:
    """Assert all 11 registered nodes map to exact operational stage names."""
    expected_mapping = {
        "normalise": "normalise",
        "intake_safety_checks": "intake_safety_checks",
        "retrieve": "retrieve",
        "draft_plan": "form_plan",
        "abstain_fallback": "form_plan",
        "verify": "verify",
        "block_seal": "seal_decision",
        "unverified_seal": "seal_decision",
        "verified_seal": "seal_decision",
        "audit": "audit",
        "explain": "explain",
    }
    assert expected_mapping == NODE_NAME_MAP

    for internal_name, operational_stage in expected_mapping.items():
        assert map_node_to_operational_stage(internal_name) == operational_stage


def test_unknown_node_name_fails_closed_and_emits_no_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate 9: Assert fabricated or unknown node names are rejected and emit zero spans."""
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_EXPORTER", "in_memory")

    manager = TelemetryManager.get_instance()
    manager.initialize()
    manager.clear_in_memory_spans()

    assert map_node_to_operational_stage("fabricated_experimental_node") is None

    executed = False
    with trace_node("fabricated_experimental_node"):
        executed = True

    assert executed is True
    # Fail-closed: zero spans emitted for unmapped node
    spans = manager.get_in_memory_spans()
    assert len(spans) == 0


# ============================================================================
# Gate 12: Loopback-Only OTLP Endpoint Validation
# ============================================================================


def test_validate_loopback_endpoint() -> None:
    """Gate 12: Assert strictly local loopback endpoints are accepted and cloud hosts rejected."""
    # Valid loopback targets
    assert validate_loopback_endpoint("http://localhost:4318/v1/traces") is True
    assert validate_loopback_endpoint("http://127.0.0.1:4318/v1/traces") is True
    assert validate_loopback_endpoint("http://[::1]:4318/v1/traces") is True
    assert validate_loopback_endpoint("http://127.0.0.1:9411") is True

    # Prohibited non-loopback / cloud targets
    assert validate_loopback_endpoint("http://collector.cloud.com:4318/v1/traces") is False
    assert validate_loopback_endpoint("http://192.168.1.100:4318/v1/traces") is False
    assert validate_loopback_endpoint("http://10.0.0.1:4318/v1/traces") is False
    assert validate_loopback_endpoint("https://api.honeycomb.io/v1/traces") is False
    assert validate_loopback_endpoint("not_a_valid_url") is False


# ============================================================================
# Gate 10: Standalone No-Op Behavior & Missing SDK Fallback
# ============================================================================


def test_noop_span_and_tracer_operations() -> None:
    """Gate 10: Assert pure-Python no-op facade works seamlessly without raising."""
    tracer = _NoOpTracer()
    assert isinstance(tracer, _NoOpTracer)

    with tracer.start_as_current_span("test.operation") as span:
        assert isinstance(span, _NoOpSpan)
        assert span.is_recording() is False
        assert span.get_span_context().is_valid is False
        span.set_attribute("key", "value")
        span.add_event("event", {"attr": "val"})
        span.end()


def test_telemetry_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert TelemetryManager defaults to _NoOpTracer when TRIAGERAG_TELEMETRY_ENABLED is false."""
    monkeypatch.delenv("TRIAGERAG_TELEMETRY_ENABLED", raising=False)
    manager = TelemetryManager.get_instance()
    manager.initialize()
    tracer = manager.get_tracer()
    assert isinstance(tracer, _NoOpTracer)


# ============================================================================
# Gate 7: Telemetry Lifecycle, Idempotence & Safe Shutdown
# ============================================================================


def test_telemetry_lifecycle_idempotent() -> None:
    """Gate 7: Assert initialization and shutdown are thread-safe and idempotent."""
    manager = TelemetryManager.get_instance()

    # Repeated initialization
    manager.initialize()
    manager.initialize()
    assert manager._initialized is True

    # Repeated shutdown
    manager.shutdown()
    manager.shutdown()
    assert manager._initialized is False


def test_shutdown_before_initialization_does_not_raise() -> None:
    """Assert shutdown called on uninitialized manager exits cleanly."""
    manager = TelemetryManager()
    manager.shutdown()
    assert manager._initialized is False


# ============================================================================
# Gate 5: Non-Interference on Telemetry Failure & Genuine Error Propagation
# ============================================================================


def test_instrumentation_non_interference_on_telemetry_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate 5: Assert tracer/exporter failures NEVER disrupt or abort clinical node execution."""

    class BrokenTracer:
        def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Simulated OTel network/exporter crash")

    monkeypatch.setattr(TelemetryManager.get_instance(), "get_tracer", lambda: BrokenTracer())

    executed = False
    with trace_node("normalise"):
        executed = True
    assert executed is True


def test_genuine_node_failure_propagates_correctly() -> None:
    """Gate 5: Assert actual application exceptions propagate cleanly and are not swallowed."""
    with pytest.raises(ValueError, match="Genuine clinical failure"), trace_node("verify"):
        raise ValueError("Genuine clinical failure")


def test_mixed_failure_node_exception_and_telemetry_closure_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert genuine application exception propagates even when telemetry cleanup fails."""

    class BrokenSpanContextManager:
        def __enter__(self) -> Any:
            return _NoOpSpan()

        def __exit__(self, *args: Any) -> Any:
            raise RuntimeError("Telemetry exporter network drop on exit")

    class BrokenSpanTracer:
        def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
            return BrokenSpanContextManager()

    monkeypatch.setattr(TelemetryManager.get_instance(), "get_tracer", lambda: BrokenSpanTracer())

    with pytest.raises(ValueError, match="Original application error"), trace_node("normalise"):
        raise ValueError("Original application error")


def test_all_span_creation_call_sites_disable_exception_recording() -> None:
    """Statically verify every start_as_current_span call site passes record_exception=False and set_status_on_exception=False."""
    import ast
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    target_files = [
        repo_root / "src/triagerag/api/app.py",
        repo_root / "src/triagerag/orchestration/langgraph_workflow.py",
        repo_root / "src/triagerag/orchestration/telemetry.py",
    ]

    call_sites: list[tuple[str, int]] = []
    for target in target_files:
        assert target.exists(), f"Target file missing: {target}"
        tree = ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id

                if func_name == "start_as_current_span":
                    kw_dict = {kw.arg: kw.value for kw in node.keywords}
                    assert "record_exception" in kw_dict, (
                        f"Missing record_exception keyword argument at {target.name}:{node.lineno}"
                    )
                    assert (
                        isinstance(kw_dict["record_exception"], ast.Constant)
                        and kw_dict["record_exception"].value is False
                    ), f"record_exception must be explicitly False at {target.name}:{node.lineno}"

                    assert "set_status_on_exception" in kw_dict, (
                        f"Missing set_status_on_exception keyword argument at {target.name}:{node.lineno}"
                    )
                    assert (
                        isinstance(kw_dict["set_status_on_exception"], ast.Constant)
                        and kw_dict["set_status_on_exception"].value is False
                    ), (
                        f"set_status_on_exception must be explicitly False at {target.name}:{node.lineno}"
                    )

                    call_sites.append((target.name, node.lineno))

    # Assert all three architectural tiers are verified
    assert len(call_sites) == 3, (
        f"Expected 3 start_as_current_span call sites, found {len(call_sites)}: {call_sites}"
    )
    file_names = {cs[0] for cs in call_sites}
    assert file_names == {"app.py", "langgraph_workflow.py", "telemetry.py"}
