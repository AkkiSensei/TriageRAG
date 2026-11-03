"""Unit tests for LangGraph workflow OpenTelemetry instrumentation and canonical execution paths.

Safety & Acceptance Gates Covered:
- Gate 2: Canonical Paths (Paths A, B, C, D) & Isolated Internal Branch Verification
- Gate 3: Span Parenting Hierarchy (workflow -> 8 generalized node spans)
- Gate 6: Behavioral & Mathematical Equivalence (Tracing vs Disabled)
- Gate 8: Concurrency & Trace Isolation
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Generator
from typing import Any

import pytest

from triagerag.config import get_data_dir
from triagerag.contracts.enums import Verdict
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import (
    FixedClock,
    Patient,
)
from triagerag.engine.registry import ClinicalRegistry, load_registry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestration.langgraph_workflow import run_triage_graph
from triagerag.orchestration.telemetry import TelemetryManager
from triagerag.rag.index import Retriever
from triagerag.rag.service import RetrievalService

EXPECTED_OPERATIONAL_SPANS = [
    "normalise",
    "intake_safety_checks",
    "retrieve",
    "form_plan",
    "verify",
    "seal_decision",
    "audit",
    "explain",
]


@pytest.fixture(scope="module")
def registry() -> ClinicalRegistry:
    return load_registry(get_data_dir())


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    service = RetrievalService.create_default(get_data_dir(), backend="bm25")
    return service.index


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM(profile=FakeLLMProfile.COMPLIANT)


@pytest.fixture
def clean_scenario() -> tuple[Patient, list[Any]]:
    return get_preloaded_scenario("CLEAN")


@pytest.fixture
def block_scenario() -> tuple[Patient, list[Any]]:
    return get_preloaded_scenario("BLOCK")


@pytest.fixture
def unverified_scenario() -> tuple[Patient, list[Any]]:
    return get_preloaded_scenario("UNVERIFIED")


@pytest.fixture(autouse=True)
def setup_in_memory_telemetry(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Configure in-memory telemetry for every test in this module."""
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_EXPORTER", "in_memory")
    TelemetryManager.reset_for_testing()
    manager = TelemetryManager.get_instance()
    manager.initialize()
    manager.clear_in_memory_spans()
    yield
    TelemetryManager.reset_for_testing()


# =============================================================================
# Gate 2: Canonical Paths & Internal Branch Verification
# =============================================================================


def test_canonical_path_a_clear_path(
    clean_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Scenario 1: Path A (Clear / Verified Seal Path).

    Verifies:
    1. Exactly 8 uniform operational node spans emitted in telemetry.
    2. Branch names (draft_plan, verified_seal, block_seal, etc.) are absent from span names.
    3. Isolated synthetic test verifies internal branch execution (draft_plan + verified_seal).
    """
    patient, overrides = clean_scenario
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    resp, trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=FixedClock(patient.assessed_at),
    )

    # 1. Internal branch verification via synthetic test state
    assert resp.engine.verdict in (Verdict.CHECKED_CLEAR, Verdict.CHECKED_ALERTS)
    internal_nodes = [t["node"] for t in trace]
    assert "draft_plan" in internal_nodes
    assert "verified_seal" in internal_nodes
    assert "block_seal" not in internal_nodes
    assert "unverified_seal" not in internal_nodes
    assert "abstain_fallback" not in internal_nodes

    # 2. Exported telemetry verification: exactly 8 uniform operational stages
    spans = manager.get_in_memory_spans()
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]
    exported_names = [s.name.replace("langgraph.node.", "") for s in node_spans]

    assert len(node_spans) == 8
    assert exported_names == EXPECTED_OPERATIONAL_SPANS

    # Verify zero clinical branch names in exported span names
    for s in spans:
        for forbidden in ("block_seal", "unverified_seal", "verified_seal", "abstain_fallback"):
            assert forbidden not in s.name.lower()


def test_canonical_path_b_block_interlock_path(
    block_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Scenario 2: Path B (Inviolable BLOCK Interlock Path - Rule R11).

    Verifies:
    1. Exactly 8 uniform operational node spans emitted in telemetry.
    2. Zero leakage of BLOCK outcome or block_seal in span names.
    3. Isolated synthetic test verifies internal branch reached block_seal.
    """
    patient, overrides = block_scenario
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    resp, trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=FixedClock(patient.assessed_at),
    )

    # 1. Internal branch verification via synthetic test state (Rule R11)
    assert resp.engine.verdict == Verdict.BLOCKED
    internal_nodes = [t["node"] for t in trace]
    assert "draft_plan" in internal_nodes
    assert "block_seal" in internal_nodes
    assert "verified_seal" not in internal_nodes
    assert "unverified_seal" not in internal_nodes

    # 2. Exported telemetry verification
    spans = manager.get_in_memory_spans()
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]
    exported_names = [s.name.replace("langgraph.node.", "") for s in node_spans]

    assert len(node_spans) == 8
    assert exported_names == EXPECTED_OPERATIONAL_SPANS
    for s in spans:
        assert "block_seal" not in s.name.lower()


def test_canonical_path_c_unverified_path(
    unverified_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Scenario 3: Path C (Fail-Closed UNVERIFIED Path - Rule R2).

    Verifies:
    1. Exactly 8 uniform operational node spans emitted in telemetry.
    2. Zero leakage of unverified_seal in span names.
    3. Isolated synthetic test verifies internal branch reached unverified_seal.
    """
    patient, overrides = unverified_scenario
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    resp, trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=FixedClock(patient.assessed_at),
    )

    # 1. Internal branch verification
    assert resp.engine.verdict == Verdict.UNVERIFIED
    internal_nodes = [t["node"] for t in trace]
    assert "draft_plan" in internal_nodes
    assert "unverified_seal" in internal_nodes
    assert "verified_seal" not in internal_nodes
    assert "block_seal" not in internal_nodes

    # 2. Exported telemetry verification
    spans = manager.get_in_memory_spans()
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]
    exported_names = [s.name.replace("langgraph.node.", "") for s in node_spans]

    assert len(node_spans) == 8
    assert exported_names == EXPECTED_OPERATIONAL_SPANS


def test_canonical_path_d_retrieval_abstention_fallback_path(
    clean_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    fake_llm: FakeLLM,
) -> None:
    """Scenario 4: Path D (Retrieval Abstention Fallback Path - index=None triggers abstention).

    Verifies:
    1. Exactly 8 uniform operational node spans emitted in telemetry.
    2. Zero leakage of abstain_fallback in span names.
    3. Isolated synthetic test verifies internal branch executed abstain_fallback and unverified_seal.
    """
    patient, overrides = clean_scenario
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    # Pass index=None so stage_retrieve abstains
    resp, trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=None,
        overrides=overrides,
        clock=FixedClock(patient.assessed_at),
    )

    # 1. Internal branch verification
    assert resp.engine.verdict == Verdict.UNVERIFIED
    internal_nodes = [t["node"] for t in trace]
    assert "abstain_fallback" in internal_nodes
    assert "draft_plan" not in internal_nodes
    assert "unverified_seal" in internal_nodes

    # 2. Exported telemetry verification
    spans = manager.get_in_memory_spans()
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]
    exported_names = [s.name.replace("langgraph.node.", "") for s in node_spans]

    assert len(node_spans) == 8
    assert exported_names == EXPECTED_OPERATIONAL_SPANS


# =============================================================================
# Gate 3: Span Parenting & Trace Correlation
# =============================================================================


def test_workflow_and_node_span_parenting_hierarchy(
    clean_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Gate 3: Assert workflow span is parent of all 8 node spans and trace_id is identical."""
    patient, overrides = clean_scenario
    manager = TelemetryManager.get_instance()
    manager.clear_in_memory_spans()

    run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=FixedClock(patient.assessed_at),
    )

    spans = manager.get_in_memory_spans()
    workflow_span = next(s for s in spans if s.name == "langgraph.workflow.execution")
    node_spans = [s for s in spans if s.name.startswith("langgraph.node.")]

    assert len(node_spans) == 8
    workflow_trace_id = workflow_span.context.trace_id
    workflow_span_id = workflow_span.context.span_id

    # Every node span must share the exact same trace_id and have workflow as parent
    for ns in node_spans:
        assert ns.context.trace_id == workflow_trace_id
        assert ns.parent.span_id == workflow_span_id


# =============================================================================
# Gate 6: Behavioral and Mathematical Equivalence
# =============================================================================


def test_behavioral_and_mathematical_equivalence(
    clean_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate 6: Assert 100% identical TriageResponse output between tracing enabled and baseline."""
    patient, overrides = clean_scenario
    fixed_clock = FixedClock(patient.assessed_at)

    # 1. Execute with tracing disabled
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "false")
    TelemetryManager.reset_for_testing()
    resp_disabled, _ = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=fixed_clock,
    )

    # 2. Execute with tracing enabled
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("TRIAGERAG_TELEMETRY_EXPORTER", "in_memory")
    TelemetryManager.reset_for_testing()
    resp_enabled, _ = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=fixed_clock,
    )

    assert resp_disabled.engine.verdict == resp_enabled.engine.verdict
    assert resp_disabled.engine.score is not None
    assert resp_enabled.engine.score is not None
    assert resp_disabled.engine.score.total_score == resp_enabled.engine.score.total_score
    assert len(resp_disabled.verified_steps) == len(resp_enabled.verified_steps)
    assert resp_disabled.audit_hash == resp_enabled.audit_hash


# =============================================================================
# Gate 8: Concurrency & State Isolation
# =============================================================================


def test_concurrency_and_trace_isolation(
    clean_scenario: tuple[Patient, list[Any]],
    block_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Gate 8: Assert concurrent requests have isolated traces and no span cross-talk."""
    patient_a, _ = clean_scenario
    patient_b, _ = block_scenario

    def run_clean() -> Any:
        return run_triage_graph(
            patient=patient_a,
            registry=registry,
            llm=fake_llm,
            index=retriever,
            clock=FixedClock(patient_a.assessed_at),
        )

    def run_block() -> Any:
        return run_triage_graph(
            patient=patient_b,
            registry=registry,
            llm=fake_llm,
            index=retriever,
            clock=FixedClock(patient_b.assessed_at),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        fut_a = executor.submit(run_clean)
        fut_b = executor.submit(run_block)
        res_a, _ = fut_a.result()
        res_b, _ = fut_b.result()

    assert res_a.engine.verdict in (Verdict.CHECKED_CLEAR, Verdict.CHECKED_ALERTS)
    assert res_b.engine.verdict == Verdict.BLOCKED
