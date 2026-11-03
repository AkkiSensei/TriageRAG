"""Triage decision support endpoint."""

from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
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
from triagerag.orchestration.events import (
    TriageEventSink,
    reset_current_event_sink,
    set_current_event_sink,
)
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


def _prepare_triage_context(
    request: TriageApiRequest,
) -> tuple[
    ClinicalRegistry,
    RetrievalService,
    FakeLLM,
    ProviderMetadata,
    Patient,
    OrchestratorConfig,
]:
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

    return registry, retrieval_service, llm, prov_meta, patient, config


@router.post("", response_model=TriageResponse)
def execute_triage(request: TriageApiRequest) -> TriageResponse:
    registry, retrieval_service, llm, prov_meta, patient, config = _prepare_triage_context(request)
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


@router.post("/stream", response_class=StreamingResponse)
async def stream_triage(request: TriageApiRequest) -> StreamingResponse:
    """Stream request-scoped lifecycle events and final triage report via Server-Sent Events (ADR 0017).

    Safety Properties (Rule R1, Rule R2, Rule R7, Rule R11):
    1. Produces mathematically and clinically identical output to POST /api/triage.
    2. Emits real-time execution events from actual node/router evaluations (zero timers/fakes).
    3. Lifecycle summaries contain zero patient PII, vitals, drugs, allergies, or complaint texts.
    4. Each request runs in an isolated context without cross-talk.
    """
    registry, retrieval_service, llm, prov_meta, patient, config = _prepare_triage_context(request)

    request_id = f"req-{uuid.uuid4().hex[:8]}"
    sink = TriageEventSink(request_id=request_id)

    # Stage 0: Request validation was completed upon successful Pydantic parsing of TriageApiRequest
    sink.emit_completed(
        stage="validation",
        safe_summary="Request payload and clinical schema validated",
    )

    async def event_generator():
        token = set_current_event_sink(sink)
        loop = asyncio.get_running_loop()
        ctx = contextvars.copy_context()

        def _run_in_context() -> TriageResponse:
            return run_triage(
                patient=patient,
                registry=registry,
                llm=llm,
                index=retrieval_service.index,
                overrides=request.overrides or [],
                config=config,
                provider_info=prov_meta,
            )

        async def _execute_pipeline():
            try:
                # Execute blocking clinical pipeline in worker thread with contextvar propagated
                resp = await loop.run_in_executor(None, ctx.run, _run_in_context)
                sink.emit_run_completed(
                    safe_summary=f"Triage evaluation completed successfully; verdict {resp.engine.verdict}",
                    result_dict=resp.model_dump(mode="json"),
                )
            except Exception as exc:
                logger.exception("Streaming triage run failed: %s", exc)
                sink.emit_failed(
                    stage="pipeline",
                    safe_summary="Triage execution failed",
                )
            finally:
                sink.close()

        runner_task = asyncio.create_task(_execute_pipeline())

        try:
            async for event in sink:
                yield f"event: {event.event_type}\ndata: {event.model_dump_json()}\n\n"
            await runner_task
        finally:
            reset_current_event_sink(token)
            sink.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
