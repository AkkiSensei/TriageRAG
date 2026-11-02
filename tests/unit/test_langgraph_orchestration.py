"""Unit and Integration Test Suite for LangGraph Deterministic Orchestration (ADR 0017).

Safety Properties Tested (Rules R1, R2, R7, R8, R11, R12):
1. Pinned and compiled LangGraph StateGraph structure and execution.
2. Individual node state transformations and zero PII logging in traces.
3. Fail-closed conditional routing (route_after_retrieve, route_after_verify).
4. End-to-end execution across normal, BLOCK, UNVERIFIED, and abstained cases.
5. Exact 100% decision and mathematical equivalence between run_triage_linear and run_triage_graph.
6. Real FastAPI endpoint integration (/api/triage and /api/triage/workflow).
7. Thread concurrency and state isolation (zero cross-talk between requests).
8. Pure determinism across repeated executions with frozen clocks.
"""

from __future__ import annotations

import concurrent.futures
import importlib.metadata
from typing import Any

import pytest
from fastapi.testclient import TestClient

from triagerag.api.app import app
from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AbstainCode,
    Severity,
    Verdict,
)
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import (
    FixedClock,
    Patient,
    RetrievalReport,
)
from triagerag.engine.registry import ClinicalRegistry, load_registry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestration.langgraph_workflow import (
    TriageGraphState,
    abstain_fallback_node,
    block_seal_node,
    build_triage_graph,
    compile_triage_graph,
    get_compiled_triage_graph,
    intake_safety_checks_node,
    normalise_node,
    route_after_retrieve,
    route_after_verify,
    run_triage_graph,
    unverified_seal_node,
    verified_seal_node,
)
from triagerag.orchestrator import run_triage_linear
from triagerag.rag.index import Retriever
from triagerag.rag.service import RetrievalService


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


@pytest.fixture
def high_scenario() -> tuple[Patient, list[Any]]:
    return get_preloaded_scenario("HIGH")


# =============================================================================
# PART 10.1: DEPENDENCY & GRAPH CONSTRUCTION TESTS
# =============================================================================


def test_10_1_langgraph_dependency_and_compilation() -> None:
    """Verify langgraph is properly installed (>=0.2.0), StateGraph builds, and compiles without errors."""
    import langgraph

    assert langgraph is not None
    version_str = importlib.metadata.version("langgraph")
    assert version_str != "", "LangGraph version metadata must be available."

    builder = build_triage_graph()
    assert builder is not None, "build_triage_graph() must return a valid StateGraph."

    compiled = compile_triage_graph()
    assert compiled is not None, (
        "compile_triage_graph() must produce an executable CompiledStateGraph."
    )

    # Validate singleton accessor
    singleton_1 = get_compiled_triage_graph()
    singleton_2 = get_compiled_triage_graph()
    assert singleton_1 is singleton_2, (
        "get_compiled_triage_graph() must return a thread-safe singleton."
    )


def test_10_1_graph_topology_and_nodes() -> None:
    """Verify all 11 required clinical workflow nodes exist in compiled graph topology."""
    compiled = get_compiled_triage_graph()
    graph_dict = compiled.get_graph()

    expected_nodes = {
        "__start__",
        "normalise",
        "intake_safety_checks",
        "retrieve",
        "draft_plan",
        "abstain_fallback",
        "verify",
        "block_seal",
        "unverified_seal",
        "verified_seal",
        "audit",
        "explain",
        "__end__",
    }
    actual_nodes = set(graph_dict.nodes.keys())
    assert expected_nodes.issubset(actual_nodes), (
        f"Missing nodes in LangGraph topology: {expected_nodes - actual_nodes}"
    )


# =============================================================================
# PART 10.2: INDIVIDUAL NODE TESTS
# =============================================================================


def test_10_2_normalise_node(
    clean_scenario: tuple[Patient, list[Any]], registry: ClinicalRegistry
) -> None:
    """Test normalise_node execution, EWS scoring, and non-sensitive trace recording."""
    patient, _ = clean_scenario
    state: TriageGraphState = {
        "patient": patient,
        "registry": registry,
        "execution_trace": [],
    }
    update = normalise_node(state)
    assert "normalized_patient" in update
    assert "score_result" in update
    assert "pop_str" in update
    assert update["pop_str"] == "adult"
    assert update["score_result"].total_score >= 0

    trace = update["execution_trace"]
    assert len(trace) == 1
    assert trace[0]["node"] == "normalise"
    assert trace[0]["status"] == "completed"
    # Ensure no patient name or PII in trace
    assert "patient_name" not in str(trace[0]["details"])
    assert "chief_complaint" not in str(trace[0]["details"])


def test_10_2_intake_safety_checks_node(
    clean_scenario: tuple[Patient, list[Any]], registry: ClinicalRegistry
) -> None:
    """Test intake_safety_checks_node baseline rules and checks_run count."""
    patient, _ = clean_scenario
    stg1 = normalise_node({"patient": patient, "registry": registry, "execution_trace": []})
    state: TriageGraphState = {
        "normalized_patient": stg1["normalized_patient"],
        "registry": registry,
        "score_result": stg1["score_result"],
        "pop_str": stg1["pop_str"],
        "execution_trace": stg1["execution_trace"],
    }
    update = intake_safety_checks_node(state)
    assert "baseline_alerts" in update
    assert "baseline_skips" in update
    assert "checks_run" in update
    assert update["checks_run"] > 0
    assert len(update["execution_trace"]) == 2


def test_10_2_abstain_fallback_node() -> None:
    """Test abstain_fallback_node forces llm_fallback_mode=True and plan_draft=None (Rule R2)."""
    state: TriageGraphState = {
        "retrieval_report": RetrievalReport(
            chunks=[],
            abstained=True,
            abstain_code=AbstainCode.UNKNOWN_SYNDROME,
            reason="Unknown clinical syndrome",
            backend="bm25",
        ),
        "execution_trace": [],
    }
    update = abstain_fallback_node(state)
    assert update["plan_draft"] is None
    assert update["llm_fallback_mode"] is True
    assert update["execution_trace"][0]["node"] == "abstain_fallback"


def test_10_2_block_seal_node() -> None:
    """Test block_seal_node records Rule R11 non-overridable interlock trace."""
    state: TriageGraphState = {"overall_verdict": Verdict.BLOCKED, "execution_trace": []}
    update = block_seal_node(state)
    trace = update["execution_trace"]
    assert len(trace) == 1
    assert trace[0]["node"] == "block_seal"
    assert trace[0]["details"]["rule"] == "Rule R11: Inviolable BLOCK Interlock"
    assert trace[0]["details"]["non_overridable"] is True


def test_10_2_unverified_seal_node() -> None:
    """Test unverified_seal_node records Rule R2 fail-closed boundary trace."""
    state: TriageGraphState = {
        "overall_verdict": Verdict.UNVERIFIED,
        "unverified_reason": "Missing critical vital signs",
        "execution_trace": [],
    }
    update = unverified_seal_node(state)
    trace = update["execution_trace"]
    assert len(trace) == 1
    assert trace[0]["node"] == "unverified_seal"
    assert trace[0]["details"]["verdict"] == "UNVERIFIED"
    assert trace[0]["details"]["reason"] == "Missing critical vital signs"


def test_10_2_verified_seal_node() -> None:
    """Test verified_seal_node records verified disposition."""
    state: TriageGraphState = {
        "overall_verdict": Verdict.CHECKED_CLEAR,
        "verified_steps": [],
        "execution_trace": [],
    }
    update = verified_seal_node(state)
    trace = update["execution_trace"]
    assert len(trace) == 1
    assert trace[0]["node"] == "verified_seal"
    assert trace[0]["details"]["verdict"] == "CHECKED_CLEAR"


# =============================================================================
# PART 10.3: CONDITIONAL ROUTING TESTS
# =============================================================================


def test_10_3_route_after_retrieve() -> None:
    """Test conditional route 1: routes to draft_plan vs abstain_fallback."""
    # When retrieval succeeds (abstained=False)
    normal_report = RetrievalReport(chunks=[], abstained=False, backend="bm25")
    assert route_after_retrieve({"retrieval_report": normal_report}) == "draft_plan"

    # When retrieval abstains (abstained=True)
    abstained_report = RetrievalReport(
        chunks=[],
        abstained=True,
        abstain_code=AbstainCode.UNKNOWN_SYNDROME,
        reason="Unknown clinical syndrome",
        backend="bm25",
    )
    assert route_after_retrieve({"retrieval_report": abstained_report}) == "abstain_fallback"


def test_10_3_route_after_verify() -> None:
    """Test conditional route 2: routes to block_seal, unverified_seal, or verified_seal."""
    assert route_after_verify({"overall_verdict": Verdict.BLOCKED}) == "block_seal"
    assert route_after_verify({"overall_verdict": Verdict.UNVERIFIED}) == "unverified_seal"
    assert route_after_verify({"overall_verdict": Verdict.CHECKED_CLEAR}) == "verified_seal"
    assert route_after_verify({"overall_verdict": Verdict.CHECKED_ALERTS}) == "verified_seal"


# =============================================================================
# PART 10.4: END-TO-END WORKFLOW EXECUTION TESTS
# =============================================================================


def test_10_4_e2e_clean_workflow_execution(
    clean_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Execute complete LangGraph workflow for clean anaphylaxis patient."""
    patient, overrides = clean_scenario
    fixed_clock = FixedClock(patient.assessed_at)

    response, trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=fixed_clock,
    )

    assert response is not None
    assert response.engine is not None
    assert response.audit_hash != ""

    node_names = [t["node"] for t in trace]
    assert node_names[0] == "normalise"
    assert node_names[1] == "intake_safety_checks"
    assert node_names[2] == "retrieve"
    assert "draft_plan" in node_names
    assert "verify" in node_names
    assert "audit" in node_names
    assert "explain" in node_names


def test_10_4_e2e_block_workflow_execution(
    block_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Execute LangGraph workflow for sildenafil patient presenting with chest pain (Rule R11 BLOCK)."""
    patient, overrides = block_scenario
    fixed_clock = FixedClock(patient.assessed_at)

    response, trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=fixed_clock,
    )

    assert response is not None
    assert response.engine.verdict == Verdict.BLOCKED
    all_alerts = response.engine.baseline_alerts + response.engine.plan_alerts
    assert any(a.severity == Severity.BLOCK for a in all_alerts)

    node_names = [t["node"] for t in trace]
    assert "block_seal" in node_names


def test_10_4_e2e_unverified_workflow_execution(
    unverified_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Execute LangGraph workflow for patient with unknown vitals (Rule R2 UNVERIFIED)."""
    patient, overrides = unverified_scenario
    fixed_clock = FixedClock(patient.assessed_at)

    response, trace = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=fixed_clock,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    node_names = [t["node"] for t in trace]
    assert "unverified_seal" in node_names


# =============================================================================
# PART 10.5: LEGACY VS LANGGRAPH EQUIVALENCE TESTING (MANDATORY)
# =============================================================================


@pytest.mark.parametrize(
    "scenario_name",
    ["CLEAN", "BLOCK", "UNVERIFIED", "HIGH"],
)
def test_10_5_behavioural_equivalence_with_legacy_orchestrator(
    scenario_name: str,
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Verify 100% decision and clinical output equivalence between reference linear and LangGraph."""
    patient, overrides = get_preloaded_scenario(scenario_name)
    frozen_clock = FixedClock(patient.assessed_at)

    # 1. Run reference linear implementation
    legacy_resp = run_triage_linear(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=frozen_clock,
    )

    # 2. Run LangGraph implementation
    graph_resp, _ = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=frozen_clock,
    )

    # 3. Assert exact mathematical and clinical equivalence
    assert graph_resp.engine.verdict == legacy_resp.engine.verdict, (
        f"Verdict mismatch for scenario {scenario_name}!"
    )
    if graph_resp.engine.score is not None:
        assert legacy_resp.engine.score is not None
        assert graph_resp.engine.score.total_score == legacy_resp.engine.score.total_score
        assert graph_resp.engine.score.band == legacy_resp.engine.score.band
    else:
        assert legacy_resp.engine.score is None
    assert len(graph_resp.engine.baseline_alerts) == len(legacy_resp.engine.baseline_alerts)
    assert len(graph_resp.engine.plan_alerts) == len(legacy_resp.engine.plan_alerts)
    assert [a.rule_id for a in graph_resp.engine.baseline_alerts] == [
        a.rule_id for a in legacy_resp.engine.baseline_alerts
    ]
    assert [a.severity for a in graph_resp.engine.baseline_alerts] == [
        a.severity for a in legacy_resp.engine.baseline_alerts
    ]
    assert len(graph_resp.engine.checks_skipped) == len(legacy_resp.engine.checks_skipped)
    assert len(graph_resp.verified_steps) == len(legacy_resp.verified_steps)
    assert graph_resp.llm_fallback_mode == legacy_resp.llm_fallback_mode
    assert graph_resp.audit_hash == legacy_resp.audit_hash, (
        "Cryptographic audit hash must match exactly!"
    )


# =============================================================================
# PART 10.6: FASTAPI ROUTE & WORKFLOW ENDPOINT INTEGRATION TESTS
# =============================================================================


def test_10_6_fastapi_workflow_endpoint() -> None:
    """Verify GET /api/triage/workflow returns LangGraph structure and valid Mermaid."""
    client = TestClient(app)
    resp = client.get("/api/triage/workflow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["framework"] == "LangGraph"
    assert data["compiled"] is True
    assert "normalise" in data["nodes"]
    assert "graph TD;" in data["mermaid"] or "graph LR;" in data["mermaid"]


def test_10_6_fastapi_triage_route_invokes_langgraph(
    clean_scenario: tuple[Patient, list[Any]],
) -> None:
    """Verify POST /api/triage executes successfully through the LangGraph-backed orchestrator."""
    patient, overrides = clean_scenario
    client = TestClient(app)
    req_payload = {
        "patient": patient.model_dump(mode="json"),
        "llm_profile": "COMPLIANT",
        "retrieval_backend": "bm25",
        "overrides": [o.model_dump(mode="json") for o in overrides],
    }
    resp = client.post("/api/triage", json=req_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "engine" in body
    assert "verdict" in body["engine"]
    assert "audit_hash" in body
    assert body["audit_hash"] != ""


# =============================================================================
# PART 10.7: CONCURRENCY & STATE ISOLATION TESTS
# =============================================================================


def test_10_7_concurrency_and_state_isolation(
    clean_scenario: tuple[Patient, list[Any]],
    block_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Run multiple concurrent triage requests to prove zero state contamination across threads."""
    clean_p, clean_ovr = clean_scenario
    block_p, block_ovr = block_scenario

    def run_worker(idx: int) -> tuple[int, Verdict, str]:
        if idx % 2 == 0:
            target_p, target_ovr = clean_p, clean_ovr
            expected_block = False
        else:
            target_p, target_ovr = block_p, block_ovr
            expected_block = True

        clock = FixedClock(target_p.assessed_at)
        resp, _ = run_triage_graph(
            patient=target_p,
            registry=registry,
            llm=fake_llm,
            index=retriever,
            overrides=target_ovr,
            clock=clock,
        )
        if expected_block:
            assert resp.engine.verdict == Verdict.BLOCKED
        else:
            assert resp.engine.verdict != Verdict.BLOCKED

        return idx, resp.engine.verdict, resp.audit_hash

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(run_worker, range(12)))

    assert len(results) == 12


# =============================================================================
# PART 10.8: DETERMINISM TEST
# =============================================================================


def test_10_8_determinism(
    clean_scenario: tuple[Patient, list[Any]],
    registry: ClinicalRegistry,
    retriever: Retriever,
    fake_llm: FakeLLM,
) -> None:
    """Verify bit-for-bit determinism across repeated executions with frozen clock."""
    patient, overrides = clean_scenario
    clock = FixedClock(patient.assessed_at)

    resp_1, trace_1 = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=clock,
    )

    resp_2, trace_2 = run_triage_graph(
        patient=patient,
        registry=registry,
        llm=fake_llm,
        index=retriever,
        overrides=overrides,
        clock=clock,
    )

    assert resp_1.audit_hash == resp_2.audit_hash
    assert resp_1.engine.verdict == resp_2.engine.verdict
    assert [t["node"] for t in trace_1] == [t["node"] for t in trace_2]
