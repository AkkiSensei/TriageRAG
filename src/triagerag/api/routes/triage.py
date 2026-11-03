"""Triage decision support endpoint."""

from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from triagerag.api.schemas import ExplainApiRequest, TriageApiRequest
from triagerag.config import get_data_dir, get_retrieval_backend
from triagerag.contracts.schemas import (
    Alert,
    OrchestratorConfig,
    Patient,
    ProviderMetadata,
    TriageResponse,
)
from triagerag.engine.registry import ClinicalRegistry, load_registry
from triagerag.llm.fake import FakeLLM
from triagerag.orchestrator import run_triage
from triagerag.rag.alert_why import AlertWhyExplanation, explain_alert
from triagerag.rag.service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["triage"])

_REGISTRY_LOCK = threading.RLock()
_REGISTRY: ClinicalRegistry | None = None


def get_cached_registry() -> ClinicalRegistry:
    """Return thread-safe cached ClinicalRegistry."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None:
            _REGISTRY = load_registry(get_data_dir())
        return _REGISTRY


def get_retrieval_service(backend: str | None = None) -> RetrievalService:
    """Return unified thread-safe RetrievalService instance."""
    eff_backend = backend or get_retrieval_backend()
    return RetrievalService.create_default(get_data_dir(), backend=eff_backend)


@router.post("", response_model=TriageResponse)
def execute_triage(request: TriageApiRequest) -> TriageResponse:
    registry = get_cached_registry()
    raw_backend = (
        request.retrieval_backend.value
        if request.retrieval_backend is not None
        else get_retrieval_backend()
    )
    eff_backend = raw_backend.strip().lower()
    retrieval_service = get_retrieval_service(eff_backend)

    llm = FakeLLM(profile=request.llm_profile)
    req_profile = (
        request.llm_profile.value
        if hasattr(request.llm_profile, "value")
        else str(request.llm_profile)
    )
    prov_meta = ProviderMetadata(
        generation_mode="deterministic_mock",
        requested_profile=req_profile,
        retrieval_backend=eff_backend,
    )

    patient = request.patient
    # Explicit clinician syndrome takes precedence. If empty or "unspecified", normalize to None.
    # Untrusted complaints NEVER silently infer or mutate patient.suspected_syndrome
    # (Rule R7, Finding A). Omitted syndromes proceed to vitals candidate inference (ADR-0007).
    if patient.suspected_syndrome in ("", "unspecified", "None"):
        patient = patient.model_copy(update={"suspected_syndrome": None})

    # Finding B & Rule R7: include_complaint_in_llm is strictly opt-in (default False).
    # Presence of untrusted complaint text alone does NOT enable inclusion.
    include_complaint = bool(request.include_complaint_in_llm)
    config = OrchestratorConfig(
        include_complaint_in_llm=include_complaint,
    )

    response = run_triage(
        patient=patient,
        registry=registry,
        llm=llm,
        index=retrieval_service.index,
        overrides=request.overrides or [],
        config=config,
        provider_info=prov_meta,
    )
    return response


@router.get("/workflow")
def get_workflow_graph_metadata() -> dict[str, Any]:
    """Return LangGraph workflow structure, node inventory, and Mermaid definition."""
    from triagerag.orchestration.langgraph_workflow import get_compiled_triage_graph

    graph = get_compiled_triage_graph()
    mermaid_code = graph.get_graph().draw_mermaid()
    return {
        "framework": "LangGraph",
        "compiled": True,
        "nodes": list(graph.get_graph().nodes.keys()),
        "mermaid": mermaid_code,
    }


@router.post("/explain")
def explain_triage_retrieval(request: ExplainApiRequest) -> dict[str, Any]:
    """Return full Retrieval Inspector diagnostic trace for a patient presentation."""
    raw_backend = (
        request.retrieval_backend.value
        if request.retrieval_backend is not None
        else get_retrieval_backend()
    )
    eff_backend = raw_backend.strip().lower()
    retrieval_service = get_retrieval_service(eff_backend)
    return retrieval_service.explain(request.to_patient())


class AlertWhyRequest(BaseModel):
    alert: Alert
    patient: Patient


@router.post("/alert-why", response_model=AlertWhyExplanation)
def explain_alert_endpoint(request: AlertWhyRequest) -> AlertWhyExplanation:
    """Return structured provenance, matched facts, and severity rationale for an alert."""
    registry = get_cached_registry()
    retrieval_service = get_retrieval_service()
    chunks = retrieval_service.list_chunks()
    return explain_alert(
        alert=request.alert,
        patient=request.patient,
        registry=registry,
        supporting_chunks=chunks,
    )
