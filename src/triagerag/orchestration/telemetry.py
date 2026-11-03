"""OpenTelemetry instrumentation facade, zero-sensitive-data sanitizer, and fail-safe lifecycle.

Safety Properties (Rules R1, R2, R7, R12):
1. Zero PHI / Outcome Privacy: Strict attribute allowlist and fail-closed mapping ensure no
   patient-derived facts, vitals, scores, or clinical outcomes (BLOCKED/UNVERIFIED/VERIFIED)
   enter exported spans, events, or resource metadata.
2. Guaranteed Non-Interference: Telemetry errors in tracer lookup, span creation, attribute
   recording, or exporter operations are caught and suppressed; clinical processing is never interrupted.
3. Transparent Error Propagation: Genuine application and node exceptions propagate cleanly to callers.
4. Automatic Exception Protection: record_exception=False and set_status_on_exception=False prevent
   automatic stack trace or exception message leakage into telemetry spans.
5. Standalone No-Op: Fully operational pure-Python facade with zero dependency on opentelemetry packages
   at module import time.
6. Local-Only Boundary: Exporters support in-memory testing, console output, and loopback-only OTLP;
   all non-loopback endpoints are strictly rejected.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import urllib.parse
from collections.abc import Iterator, Mapping
from typing import Any, Literal

from triagerag.config import (
    get_otlp_endpoint,
    get_telemetry_exporter,
    is_telemetry_enabled,
)

logger = logging.getLogger(__name__)

# Strict mapping of internal LangGraph node names to generalized operational stages.
# Mutually exclusive branches (draft_plan/abstain_fallback and block_seal/unverified_seal/verified_seal)
# map to uniform operational labels to prevent clinical verdict leakage in APM timelines.
NODE_NAME_MAP: dict[str, str] = {
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

# Strict operational schema with exact types and restricted categorical literals.
ATTRIBUTE_SCHEMA: dict[str, dict[str, Any]] = {
    "service.name": {"type": str, "permitted_values": {"triagerag"}},
    "service.version": {"type": str},
    "deployment.environment": {
        "type": str,
        "permitted_values": {"development", "test", "production"},
    },
    "triagerag.workflow.name": {"type": str, "permitted_values": {"triage_state_graph"}},
    "triagerag.workflow.status": {"type": str, "permitted_values": {"completed", "failed"}},
    "triagerag.node.name": {
        "type": str,
        "permitted_values": {
            "normalise",
            "intake_safety_checks",
            "retrieve",
            "form_plan",
            "verify",
            "seal_decision",
            "audit",
            "explain",
        },
    },
    "triagerag.node.status": {"type": str, "permitted_values": {"completed", "failed"}},
    "triagerag.routing.edge": {
        "type": str,
        "permitted_values": {"route_after_retrieve", "route_after_verify"},
    },
    "http.method": {"type": str, "permitted_values": {"GET", "POST", "OPTIONS"}},
    "http.route": {
        "type": str,
        "permitted_values": {
            "/api/health",
            "/api/scenarios",
            "/api/triage",
            "/api/triage/workflow",
            "/api/triage/explain",
            "/api/triage/alert-why",
            "/api/corpus/ask",
            "/api/registry",
            "/api/protocols",
            "/api/audit",
            "/api/eval",
        },
    },
    "http.status_code": {"type": int},
    "error.type": {"type": str, "permitted_values": {"application_error", "telemetry_error"}},
}

ALLOWED_SPAN_ATTRIBUTES: frozenset[str] = frozenset(ATTRIBUTE_SCHEMA.keys())


def map_node_to_operational_stage(node_name: str) -> str | None:
    """Fail-closed mapping of internal LangGraph node names to generalized operational stages.

    Returns None for unknown, unmapped, or fabricated internal node names to ensure
    raw names are never leaked into external telemetry.
    """
    return NODE_NAME_MAP.get(node_name)


def sanitize_span_attributes(attrs: Mapping[str, Any]) -> dict[str, Any]:
    """Filter attributes strictly against ATTRIBUTE_SCHEMA.

    Fail-closed validation rules:
    1. If key is not in ATTRIBUTE_SCHEMA, drop it immediately.
    2. If value is not an instance of schema['type'], drop it immediately (never stringify).
    3. Disallow bool masquerading as int (Python bool inherits from int).
    4. If schema defines permitted_values and value is not in permitted_values, drop it.
    5. If key is http.status_code, validate range 100-599.
    """
    sanitized: dict[str, Any] = {}
    for key, value in attrs.items():
        rule = ATTRIBUTE_SCHEMA.get(key)
        if rule is None:
            continue

        expected_type = rule["type"]
        if expected_type in (int, float) and isinstance(value, bool):
            continue

        if not isinstance(value, expected_type):
            continue

        permitted = rule.get("permitted_values")
        if permitted is not None and value not in permitted:
            continue

        if key == "http.status_code" and not (100 <= value <= 599):
            continue

        sanitized[key] = value

    return sanitized


def validate_loopback_endpoint(url: str) -> bool:
    """Validate that an OTLP endpoint is strictly a local loopback destination.

    Rejects non-loopback hosts to preserve the offline research prototype boundary.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        return hostname.lower() in ("localhost", "127.0.0.1", "::1", "[::1]")
    except Exception:
        return False


class _NoOpSpanContext:
    """Minimal span context object for no-op operation."""

    trace_id: int = 0
    span_id: int = 0
    is_valid: bool = False


class _NoOpSpan:
    """Internal pure-Python no-op span implementing the minimal OpenTelemetry Span protocol."""

    def __init__(self) -> None:
        self._context = _NoOpSpanContext()

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        pass

    def is_recording(self) -> bool:
        return False

    def get_span_context(self) -> Any:
        return self._context

    def end(self, end_time: int | None = None) -> None:
        pass

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        return False


class _NoOpTracer:
    """Internal pure-Python no-op tracer with zero dependencies on opentelemetry.*."""

    @contextlib.contextmanager
    def start_as_current_span(
        self,
        name: str,
        context: Any = None,
        attributes: Mapping[str, Any] | None = None,
        record_exception: bool = False,
        set_status_on_exception: bool = False,
        **kwargs: Any,
    ) -> Iterator[_NoOpSpan]:
        yield _NoOpSpan()

    def start_span(
        self,
        name: str,
        context: Any = None,
        attributes: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> _NoOpSpan:
        return _NoOpSpan()


class TelemetryManager:
    """Thread-safe lifecycle manager for OpenTelemetry provider, tracer, and local exporters."""

    _instance: TelemetryManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._tracer: Any = None
        self._provider: Any = None
        self._in_memory_exporter: Any = None
        self._initialized: bool = False
        self._init_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> TelemetryManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_testing(cls) -> None:
        """Reset singleton state between isolated test executions."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown()
            cls._instance = cls()

    def initialize(self) -> None:
        """Initialize OpenTelemetry TracerProvider and exporter according to configuration.

        Idempotent and thread-safe. Falls back to _NoOpTracer on missing SDK or exporter failure.
        """
        with self._init_lock:
            if self._initialized:
                return

            if not is_telemetry_enabled():
                self._tracer = _NoOpTracer()
                self._initialized = True
                return

            try:
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import (
                    BatchSpanProcessor,
                    ConsoleSpanExporter,
                    SimpleSpanProcessor,
                )

                resource = Resource.create({"service.name": "triagerag"})
                provider = TracerProvider(resource=resource)

                exporter_type = get_telemetry_exporter()
                if exporter_type == "in_memory":
                    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
                        InMemorySpanExporter,
                    )

                    self._in_memory_exporter = InMemorySpanExporter()
                    provider.add_span_processor(SimpleSpanProcessor(self._in_memory_exporter))
                elif exporter_type == "console":
                    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
                elif exporter_type == "otlp_http":
                    endpoint = get_otlp_endpoint()
                    if not validate_loopback_endpoint(endpoint):
                        logger.debug("OTLP endpoint rejected: non-loopback host is prohibited.")
                        self._tracer = _NoOpTracer()
                        self._initialized = True
                        return

                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                        OTLPSpanExporter,
                    )

                    otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
                    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                else:
                    # exporter_type == 'none' or unknown
                    self._tracer = _NoOpTracer()
                    self._initialized = True
                    return

                self._provider = provider
                self._tracer = provider.get_tracer("triagerag.orchestration")
                self._initialized = True
            except ImportError:
                logger.debug("OpenTelemetry SDK not installed; using internal NoOpTracer.")
                self._tracer = _NoOpTracer()
                self._initialized = True
            except Exception:
                logger.debug(
                    "Telemetry initialization failed; falling back to internal NoOpTracer."
                )
                self._tracer = _NoOpTracer()
                self._initialized = True

    def shutdown(self) -> None:
        """Shut down provider and exporters cleanly. Idempotent and thread-safe."""
        with self._init_lock:
            if not self._initialized:
                return

            if self._provider is not None:
                try:
                    if hasattr(self._provider, "force_flush"):
                        self._provider.force_flush()
                except Exception:
                    logger.debug("Telemetry provider force_flush failed.")

                try:
                    if hasattr(self._provider, "shutdown"):
                        self._provider.shutdown()
                except Exception:
                    logger.debug("Telemetry exporter shutdown failed.")

            self._provider = None
            self._tracer = None
            self._in_memory_exporter = None
            self._initialized = False

    def get_tracer(self) -> Any:
        """Return active tracer, initializing on demand if not already configured."""
        if not self._initialized:
            self.initialize()
        if self._tracer is None:
            return _NoOpTracer()
        return self._tracer

    def get_in_memory_spans(self) -> list[Any]:
        """Return finished spans from InMemorySpanExporter for test inspection."""
        if self._in_memory_exporter is not None:
            try:
                return list(self._in_memory_exporter.get_finished_spans())
            except Exception:
                return []
        return []

    def clear_in_memory_spans(self) -> None:
        """Clear recorded spans from the in-memory queue."""
        if self._in_memory_exporter is not None:
            with contextlib.suppress(Exception):
                self._in_memory_exporter.clear()


class TraceNodeContextManager:
    """Fail-safe context manager guaranteeing zero interference with clinical execution.

    Safety Properties:
    1. Clinical Non-Interference: Any failure in tracer lookup, span creation,
       attribute sanitization, context activation, or exporter flush is suppressed
       and logged at DEBUG level. It cannot abort or alter the node's execution.
    2. Transparent Exception Propagation: If the clinical node raises an exception,
       it is never swallowed or replaced. It propagates unmodified to the caller.
    3. Outcome Privacy: Internal node names are mapped via fail-closed NODE_NAME_MAP.
       Unmapped or fabricated internal node names are omitted to prevent leakage.
    4. Exception Protection: Automatic exception recording and status setting are disabled
       (record_exception=False, set_status_on_exception=False) to ensure stack traces and
       exception messages never enter exported span data.
    """

    def __init__(self, node_name: str, attributes: Mapping[str, Any] | None = None) -> None:
        self.node_name = node_name
        self.raw_attributes = attributes
        self._active_span: Any = None
        self._span_cm: Any = None

    def __enter__(self) -> Any:
        try:
            mapped_name = map_node_to_operational_stage(self.node_name)
            if mapped_name is None:
                # Fail-closed: do not emit spans for unmapped/fabricated node names
                self._active_span = _NoOpSpan()
                return self._active_span

            tracer = TelemetryManager.get_instance().get_tracer()
            safe_attrs = sanitize_span_attributes(self.raw_attributes or {})
            safe_attrs["triagerag.node.name"] = mapped_name

            self._span_cm = tracer.start_as_current_span(
                f"langgraph.node.{mapped_name}",
                attributes=safe_attrs,
                record_exception=False,
                set_status_on_exception=False,
            )
            self._active_span = self._span_cm.__enter__()
            return self._active_span
        except Exception:
            logger.debug("Telemetry span creation failed; using no-op instrumentation.")
            self._active_span = _NoOpSpan()
            return self._active_span

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        # 1. Update status safely using controlled categorical vocabulary
        if self._active_span is not None:
            try:
                if hasattr(self._active_span, "is_recording") and self._active_span.is_recording():
                    if exc_type is not None:
                        self._active_span.set_attribute("triagerag.node.status", "failed")
                        self._active_span.set_attribute("error.type", "application_error")
                    else:
                        self._active_span.set_attribute("triagerag.node.status", "completed")
            except Exception:
                logger.debug("Telemetry attribute recording failed.")

        # 2. Close underlying context manager safely with actual exception info
        # (automatic exception recording is disabled)
        if self._span_cm is not None:
            try:
                self._span_cm.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                logger.debug("Telemetry span closure failed.")

        # 3. CRITICAL: Always return False so any genuine clinical exception (exc_val)
        # propagates unmodified to the caller.
        return False


def trace_node(
    node_name: str, attributes: Mapping[str, Any] | None = None
) -> TraceNodeContextManager:
    """Return a fail-safe, non-interfering context manager for LangGraph node execution."""
    return TraceNodeContextManager(node_name, attributes)


def extract_trace_context(carrier: Mapping[str, str]) -> Any:
    """Extract W3C trace context from carrier mapping using standard propagator.

    Returns None if propagation packages are unavailable or extraction fails.
    """
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        return TraceContextTextMapPropagator().extract(carrier=carrier)
    except Exception:
        return None


def inject_trace_context(carrier: dict[str, str], context: Any = None) -> None:
    """Inject active W3C trace context into carrier dictionary using standard propagator."""
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        TraceContextTextMapPropagator().inject(carrier=carrier, context=context)
    except Exception:
        pass


def get_active_trace_id_hex() -> str | None:
    """Return the 32-character hex trace ID of the active span, or None."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx and ctx.trace_id:
                return f"{ctx.trace_id:032x}"
    except Exception:
        pass
    return None
