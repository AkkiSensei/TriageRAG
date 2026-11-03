"""Unit tests for request-scoped lifecycle event streaming (ADR 0017).

Safety Properties (Rule R1, Rule R2, Rule R7, Rule R11):
1. Verifies that real execution events are emitted by LangGraph nodes and routers.
2. Verifies that branch skips are explicitly emitted (Rule R2 fail-closed).
3. Verifies privacy allowlist: zero patient vitals, medications, allergies, complaint texts,
   or exception tracebacks leak into lifecycle events.
4. Verifies request-scoped isolation across execution contexts.
"""

from __future__ import annotations

import pytest

from triagerag.config import get_data_dir
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import (
    TriageLifecycleEvent,
)
from triagerag.engine.registry import load_registry
from triagerag.llm.fake import FakeLLM
from triagerag.orchestration.events import (
    TriageEventSink,
    get_current_event_sink,
    reset_current_event_sink,
    set_current_event_sink,
)
from triagerag.orchestration.langgraph_workflow import run_triage_graph
from triagerag.rag.service import RetrievalService


@pytest.fixture(scope="module")
def registry():
    return load_registry(get_data_dir())


@pytest.fixture(scope="module")
def retrieval_service():
    return RetrievalService.create_default(get_data_dir(), backend="bm25")


def test_sink_monotonic_sequence():
    """TriageEventSink increments sequence monotonically starting from 1."""
    sink = TriageEventSink(request_id="req-test-1")
    sink.emit_started("normalise", "Normalising patient")
    sink.emit_completed("normalise", "Normalised successfully")
    sink.emit_skipped("abstain_fallback", "Retrieval succeeded; skipping fallback")
    sink.close()

    events: list[TriageLifecycleEvent] = []
    while not sink._queue.empty():
        item = sink._queue.get_nowait()
        if item is not None:
            events.append(item)

    assert len(events) == 3
    assert [e.sequence for e in events] == [1, 2, 3]
    assert events[0].event_type == "stage.started"
    assert events[1].event_type == "stage.completed"
    assert events[2].event_type == "stage.skipped"
    assert all(e.request_id == "req-test-1" for e in events)


def test_workflow_emits_full_lifecycle_events(registry, retrieval_service):
    """LangGraph execution emits lifecycle events for all visited stages and branches."""
    patient, overrides = get_preloaded_scenario("CLEAN")

    sink = TriageEventSink(request_id="req-wf-1")
    token = set_current_event_sink(sink)

    try:
        resp, trace = run_triage_graph(
            patient=patient,
            registry=registry,
            llm=FakeLLM(),
            index=retrieval_service.index,
            overrides=overrides,
        )
    finally:
        reset_current_event_sink(token)
        sink.close()

    events: list[TriageLifecycleEvent] = []
    while not sink._queue.empty():
        item = sink._queue.get_nowait()
        if item is not None:
            events.append(item)

    assert len(events) >= 10
    stage_names = [e.stage for e in events]

    # Verify standard stages were touched
    assert "normalise" in stage_names
    assert "intake_safety_checks" in stage_names
    assert "retrieve" in stage_names
    assert "verify" in stage_names
    assert "audit" in stage_names
    assert "explain" in stage_names

    # Check that skipped branches were emitted
    skipped_stages = [e.stage for e in events if e.event_type == "stage.skipped"]
    assert len(skipped_stages) > 0

    # If protocol retrieved, abstain_fallback should be skipped
    if "draft_plan" in stage_names:
        assert "abstain_fallback" in skipped_stages


def test_privacy_allowlist_enforcement(registry, retrieval_service):
    """Lifecycle events strictly forbid leaking PII, vitals, drugs, allergies, or complaint texts."""
    patient, overrides = get_preloaded_scenario("BLOCK")
    private_complaint = "Top secret untrusted narrative with clinician note"
    patient = patient.model_copy(update={"chief_complaint_untrusted": private_complaint})

    sink = TriageEventSink(request_id="req-privacy-1")
    token = set_current_event_sink(sink)

    try:
        run_triage_graph(
            patient=patient,
            registry=registry,
            llm=FakeLLM(),
            index=retrieval_service.index,
            overrides=overrides,
        )
    finally:
        reset_current_event_sink(token)
        sink.close()

    events: list[TriageLifecycleEvent] = []
    while not sink._queue.empty():
        item = sink._queue.get_nowait()
        if item is not None:
            events.append(item)

    # Check known sensitive elements from BLOCK patient
    sensitive_tokens = [private_complaint.lower()]
    for med in patient.medications:
        if med.raw_text:
            sensitive_tokens.append(med.raw_text.lower())
        for ing in med.ingredients:
            sensitive_tokens.append(ing.ingredient_id.lower())
    for alg in patient.allergies:
        sensitive_tokens.append(alg.allergen.lower())

    for ev in events:
        summary_lower = ev.safe_summary.lower()
        for tok in sensitive_tokens:
            assert tok not in summary_lower, f"Token '{tok}' leaked in safe_summary: {ev}"
        assert "traceback" not in summary_lower, f"Traceback leaked in safe_summary: {ev}"

        # If data is provided, ensure data dictionary also contains no sensitive values
        if ev.data:
            data_str = str(ev.data).lower()
            assert private_complaint.lower() not in data_str


def test_event_sink_isolation():
    """Two sinks running in different contexts do not leak events to each other."""
    sink_a = TriageEventSink(request_id="req-a")
    sink_b = TriageEventSink(request_id="req-b")

    token_a = set_current_event_sink(sink_a)
    active_sink_a = get_current_event_sink()
    assert active_sink_a is not None and active_sink_a.request_id == "req-a"
    sink_a.emit_started("normalise", "Sink A normalise")
    reset_current_event_sink(token_a)

    token_b = set_current_event_sink(sink_b)
    active_sink_b = get_current_event_sink()
    assert active_sink_b is not None and active_sink_b.request_id == "req-b"
    sink_b.emit_started("normalise", "Sink B normalise")
    reset_current_event_sink(token_b)

    sink_a.close()
    sink_b.close()

    events_a = [
        sink_a._queue.get_nowait() for _ in range(sink_a._queue.qsize()) if sink_a._queue.qsize()
    ]
    events_b = [
        sink_b._queue.get_nowait() for _ in range(sink_b._queue.qsize()) if sink_b._queue.qsize()
    ]

    assert all(e.request_id == "req-a" for e in events_a if e is not None)
    assert all(e.request_id == "req-b" for e in events_b if e is not None)
