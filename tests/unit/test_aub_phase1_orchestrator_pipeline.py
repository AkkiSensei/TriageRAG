"""Unit tests for AUB Phase 1 Task T1.6: Decompose run_triage (AUB-OPS-02).

Safety Property (T1.6 / AUB-OPS-02):
1. Pipeline is decomposed into 7 typed stages:
   - stage_normalise
   - stage_intake_checks
   - stage_retrieve
   - stage_draft
   - stage_verify
   - stage_audit
   - stage_explain
2. Each stage returns a dedicated typed result dataclass.
3. run_triage composes all stages deterministically without global mutable state.
4. No function in src/triagerag/orchestrator.py exceeds 120 lines.
"""

from __future__ import annotations

import ast

from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import OrchestratorConfig
from triagerag.engine.registry import load_registry
from triagerag.orchestrator import (
    AuditStageResult,
    DraftStageResult,
    ExplainStageResult,
    IntakeChecksStageResult,
    NormaliseStageResult,
    RetrieveStageResult,
    VerifyStageResult,
    run_triage,
    stage_audit,
    stage_draft,
    stage_explain,
    stage_intake_checks,
    stage_normalise,
    stage_retrieve,
    stage_verify,
)
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols


def test_no_function_exceeds_120_lines_in_orchestrator() -> None:
    """Enforce strict AUB acceptance rule: no function in orchestrator > 120 lines."""
    orchestrator_path = get_repo_root() / "src" / "triagerag" / "orchestrator.py"
    assert orchestrator_path.exists()

    tree = ast.parse(orchestrator_path.read_text(encoding="utf-8"))
    functions_checked = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = node.end_lineno or node.lineno
            length = end_lineno - node.lineno + 1
            functions_checked += 1
            assert length <= 120, (
                f"Function '{node.name}' has {length} lines, exceeding the 120-line maximum"
            )

    assert functions_checked >= 15, f"Expected at least 15 functions, found {functions_checked}"


def test_typed_pipeline_stages_individually() -> None:
    """Verify each of the 7 stages produces its expected typed output dataclass."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)
    patient, _ = get_preloaded_scenario("CLEAN")
    chunks = ingest_protocols(data_dir)
    index = BM25ClinicalIndex(chunks)
    cfg = OrchestratorConfig()

    # Stage 1: normalise
    stg1 = stage_normalise(patient=patient, registry=registry)
    assert isinstance(stg1, NormaliseStageResult)
    assert stg1.normalized_patient.age.value == patient.age.value
    assert stg1.pop_str == "adult"

    # Stage 2: intake_checks
    stg2 = stage_intake_checks(
        normalized_patient=stg1.normalized_patient,
        registry=registry,
        score_result=stg1.score_result,
        pop_str=stg1.pop_str,
    )
    assert isinstance(stg2, IntakeChecksStageResult)
    assert stg2.checks_run > 0
    assert isinstance(stg2.allowed_drug_ids, list)

    # Stage 3: retrieve
    stg3 = stage_retrieve(normalized_patient=stg1.normalized_patient, index=index)
    assert isinstance(stg3, RetrieveStageResult)
    assert not stg3.retrieval_report.abstained
    assert len(stg3.retrieval_report.chunks) > 0

    # Stage 4: draft
    stg4 = stage_draft(
        normalized_patient=stg1.normalized_patient,
        allowed_drug_ids=stg2.allowed_drug_ids,
        baseline_alerts=stg2.baseline_alerts,
        retrieval_report=stg3.retrieval_report,
        llm=None,
        config=cfg,
    )
    assert isinstance(stg4, DraftStageResult)
    assert stg4.llm_fallback_mode is True

    # Stage 5: verify
    from triagerag.contracts.schemas import ProviderMetadata

    prov_meta = ProviderMetadata(
        generation_mode="deterministic_mock",
        retrieval_backend=stg3.retrieval_report.backend,
    )
    stg5 = stage_verify(
        normalized_patient=stg1.normalized_patient,
        plan_draft=stg4.plan_draft,
        plan_context=stg4.plan_context,
        llm_fallback_mode=stg4.llm_fallback_mode,
        baseline_alerts=stg2.baseline_alerts,
        baseline_skips=stg2.baseline_skips,
        unverified_rules=stg2.unverified_rules,
        retrieval_report=stg3.retrieval_report,
        registry=registry,
        llm=None,
        overrides_list=[],
        config=cfg,
        prov_meta=prov_meta,
    )
    assert isinstance(stg5, VerifyStageResult)

    # Stage 6: audit
    from triagerag.contracts.schemas import SystemClock

    stg6 = stage_audit(
        normalized_patient=stg1.normalized_patient,
        overall_verdict=stg5.overall_verdict,
        all_alerts=stg2.baseline_alerts + stg5.plan_alerts,
        baseline_skips=stg2.baseline_skips,
        overrides_list=[],
        retrieval_report=stg3.retrieval_report,
        registry=registry,
        llm=None,
        clock=SystemClock(),
        config=cfg,
    )
    assert isinstance(stg6, AuditStageResult)
    assert len(stg6.patient_hash) == 64

    # Stage 7: explain
    stg7 = stage_explain(
        normalized_patient=stg1.normalized_patient,
        overall_verdict=stg5.overall_verdict,
        unverified_reason=stg5.unverified_reason,
        score_result=stg1.score_result,
        baseline_alerts=stg2.baseline_alerts,
        plan_alerts=stg5.plan_alerts,
        baseline_skips=stg2.baseline_skips,
        plan_skips=stg5.plan_skips,
        dose_reports=stg5.dose_reports,
        checks_run=stg2.checks_run,
        unverified_rules=stg2.unverified_rules,
        ruleset_review_state=stg5.ruleset_review_state,
        retrieval_report=stg3.retrieval_report,
        verified_steps=stg5.verified_steps,
        registry=registry,
        provider_info=prov_meta,
        llm_fallback_mode=stg4.llm_fallback_mode,
        config=cfg,
    )
    assert isinstance(stg7, ExplainStageResult)
    assert stg7.engine_report.verdict == stg5.overall_verdict


def test_run_triage_end_to_end_orchestration() -> None:
    """Verify run_triage runs end to end across all 7 stages cleanly."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)
    patient, _ = get_preloaded_scenario("CLEAN")
    chunks = ingest_protocols(data_dir)
    index = BM25ClinicalIndex(chunks)

    resp = run_triage(patient, registry=registry, index=index)
    assert resp.engine is not None
    assert resp.retrieval is not None
    assert resp.explanation is not None
    assert resp.audit_hash is not None

